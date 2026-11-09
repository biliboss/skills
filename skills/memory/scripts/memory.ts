#!/usr/bin/env bun
/**
 * Reduces an agent (a folder, all its sessions) or one session to facts.jsonl, window by window.
 * Usage: memory.ts [folder | session id | .jsonl] [--last N] [--out DIR] [--every N] [--model ID] [--rules FILE] [--limit N]
 */
import { LocalDevin } from "@cognition-ai/sdk@0.0.1-beta.7";
import { existsSync, mkdirSync, readFileSync, realpathSync, renameSync, statSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { Glob } from "bun";
import {
  OWNER_ONLY_TYPES,
  type Cursor,
  type ExtractionRequest,
  type Fact,
  type FactExtractor,
  type MemoryStore,
  type Message,
  type Proposal,
  type AgentMemory,
  type Transcript,
  type TranscriptReader,
  type Violation,
  type Window,
} from "./interface.ts";

const PROMPT = join(import.meta.dir, "..", "resources", "prompt.md");
const PROJECTS = join(process.env.HOME ?? "", ".claude", "projects");
const MAX_REPAIRS = 2;
const TURN_TIMEOUT_MS = 20 * 60 * 1000;

const NOT_OWNER = ["<hc", "[agente", "<task-notification", "<cross-session", "<local-command", "<command-", "<system-reminder", "Caveat:"];
const TYPES = ["decisao", "preferencia", "correcao", "fato", "pendencia"];
const KEYS = ["fact", "source", "supersedes", "title", "ts", "type"];
const AGING = /\b[0-9a-f]{7,40}\b|\bPR ?#?\d+|#\d{2,}|\bv?\d+\.\d+\.\d+\b/;
const SECRETS: ReadonlyArray<readonly [string, RegExp]> = [
  ["anthropic_openai_key", /\bsk-[A-Za-z0-9_-]{16,}/g],
  ["github_token", /\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{16,}/g],
  ["slack_token", /\bxox[abprs]-[A-Za-z0-9-]{10,}/g],
  ["aws_key", /\bAKIA[0-9A-Z]{16}\b/g],
  ["google_key", /\bAIza[0-9A-Za-z_-]{30,}/g],
  ["jwt", /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}/g],
  ["bearer", /\bbearer\s+[A-Za-z0-9._~+/=-]{16,}/gi],
  ["private_key", /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g],
  ["assignment", /\b(?:api[_-]?key|secret|token|password|senha)\s*[=:]\s*['"]?[A-Za-z0-9._~+/-]{12,}/gi],
  ["email", /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g],
  ["telefone", /\+?55\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b/g],
  ["cpf", /\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/g],
  ["cep_endereco", /\b\d{5}-\d{3}\b/g],
];

const mask = (text: string) => SECRETS.reduce((t, [name, rx]) => t.replace(rx, `[REDACTED:${name}]`), text);

const textOf = (content: unknown): string =>
  typeof content === "string"
    ? content
    : Array.isArray(content)
      ? content.filter((b) => b?.type === "text").map((b) => b.text ?? "").join("\n")
      : "";

const isOwnerText = (text: string) => !NOT_OWNER.some((prefix) => text.startsWith(prefix));

class TranscriptValue implements Transcript {
  constructor(readonly messages: readonly Message[]) {}

  last(ownerMessages: number): Transcript {
    let seen = 0;
    for (let i = this.messages.length - 1; i >= 0; i--) {
      if (this.messages[i]!.fromOwner && ++seen === ownerMessages) return new TranscriptValue(this.messages.slice(i));
    }
    return this;
  }

  windows(from: Cursor, every: number): readonly Window[] {
    const result: Window[] = [];
    let start = from;
    let owners = 0;
    this.messages.slice(from).forEach((message, offset) => {
      const position = from + offset + 1;
      if (message.fromOwner) owners++;
      const closes = message.fromOwner && owners === every;
      const tail = position === this.messages.length && owners > 0;
      if (!closes && !tail) return;
      result.push({
        index: result.length + 1,
        end: position,
        messages: this.messages.slice(start, position),
        history: new TranscriptValue(this.messages.slice(0, position)),
      });
      start = position;
      owners = 0;
    });
    return result;
  }
}

function checkFact(fact: Fact, bySource: Map<string, Message>): Violation[] {
  const title = String(fact.title);
  const bad = (code: Violation["code"], detail: string): Violation => ({ code, title, detail });
  const problems: Violation[] = [];
  if (Object.keys(fact).sort().join() !== KEYS.join()) problems.push(bad("invalid-shape", `use exatamente as chaves ${KEYS.join(", ")}`));
  if (!TYPES.includes(fact.type)) problems.push(bad("invalid-shape", `tipo inválido: ${fact.type}`));
  const origin = bySource.get(fact.source);
  if (!origin) problems.push(bad("unknown-source", `source inexistente: ${fact.source}`));
  else {
    if (origin.ts !== fact.ts) problems.push(bad("ts-mismatch", `use o ts ${origin.ts}`));
    if (OWNER_ONLY_TYPES.includes(fact.type) && !origin.fromOwner) problems.push(bad("needs-owner-source", `${fact.type} precisa de source em fala do dono`));
  }
  if (fact.supersedes !== null && !bySource.has(fact.supersedes)) problems.push(bad("unknown-supersedes", "use null ou um source real"));
  const body = `${fact.title} ${fact.fact}`;
  if (AGING.test(body)) problems.push(bad("aging-reference", "tire hash, PR ou versão"));
  if (body.includes("REDACTED")) problems.push(bad("redacted-content", "tire o valor mascarado"));
  return problems;
}

function proposalOf(window: Window, lines: string): Proposal {
  const bySource = new Map(window.history.messages.map((m) => [m.source, m]));
  const facts: Fact[] = [];
  const violations: Violation[] = [];
  lines.split("\n").forEach((line, i) => {
    if (!line.trim()) return;
    try {
      const fact = JSON.parse(line) as Fact;
      facts.push(fact);
      violations.push(...checkFact(fact, bySource));
    } catch {
      violations.push({ code: "invalid-shape", title: `linha ${i + 1}`, detail: "JSON inválido" });
    }
  });
  return { window, facts, violations };
}

class Memory implements AgentMemory {
  constructor(readonly scope: string, readonly cursor: Cursor, readonly facts: readonly Fact[]) {}

  absorb(proposal: Proposal): AgentMemory {
    const { window, facts, violations } = proposal;
    if (violations.length) throw new Error(`proposta com ${violations.length} violações`);
    if (window.end - window.messages.length !== this.cursor) throw new Error("janela fora de ordem");
    const live = facts.filter((f) => !facts.some((g) => g !== f && g.supersedes === f.source));
    return new Memory(this.scope, window.end, live);
  }
}

const render = (messages: readonly Message[]) => messages.map((m) => `=== ${m.ts} | ${m.role} | ${m.source}\n${m.text}\n\n`).join("");
const toLines = (facts: readonly Fact[]) => facts.map((f) => JSON.stringify(f)).join("\n") + (facts.length ? "\n" : "");

function writeAtomic(path: string, content: string) {
  const temp = `${path}.tmp`;
  writeFileSync(temp, content);
  renameSync(temp, path);
}

const isFolder = (input: string) => existsSync(input) && statSync(input).isDirectory();

function scopeOf(input: string): string {
  if (isFolder(input)) return basename(resolve(input));
  return (input.endsWith(".jsonl") ? basename(input) : input).slice(0, 8);
}

class JsonlTranscriptReader implements TranscriptReader {
  async read(input: string): Promise<Transcript> {
    const messages = this.files(input).flatMap((path) => this.parse(path));
    return new TranscriptValue(messages.sort((a, b) => a.ts.localeCompare(b.ts)));
  }

  private files(input: string): string[] {
    if (input.endsWith(".jsonl")) return [resolve(input)];
    if (isFolder(input)) {
      const project = join(PROJECTS, resolve(input).replace(/[^a-zA-Z0-9]/g, "-"));
      if (!existsSync(project)) throw new Error(`nenhuma sessão para a pasta ${input}`);
      return [...new Glob("*.jsonl").scanSync({ cwd: project, absolute: true })];
    }
    const found = [...new Glob(`*/${input}*.jsonl`).scanSync({ cwd: PROJECTS, absolute: true })];
    if (found.length !== 1) throw new Error(`sessão ${input}: ${found.length} arquivos encontrados`);
    return found;
  }

  private parse(path: string): Message[] {
    const short = basename(path).slice(0, 8);
    const messages: Message[] = [];
    for (const line of readFileSync(path, "utf8").split("\n")) {
      if (!line.trim()) continue;
      let e: any;
      try {
        e = JSON.parse(line);
      } catch {
        continue;
      }
      if (e.isSidechain || e.isMeta || e.isCompactSummary) continue;
      const queued = e.type === "attachment" && e.attachment?.type === "queued_command" && e.attachment?.commandMode === "prompt";
      if (e.type !== "user" && e.type !== "assistant" && !queued) continue;
      const text = textOf(queued ? e.attachment.prompt : e.message?.content).trim();
      if (!text) continue;
      const role = queued || e.type === "user" ? "user" : "assistant";
      messages.push({ source: `${short}:${e.uuid}`, ts: e.timestamp, role, fromOwner: role === "user" && isOwnerText(text), text: mask(text) });
    }
    return messages;
  }
}

class FileStore implements MemoryStore {
  constructor(private readonly dir: string) {}

  async load(scope: string): Promise<AgentMemory> {
    const state = join(this.dir, "memory.json");
    if (!existsSync(state)) return new Memory(scope, 0, []);
    const { cursor } = JSON.parse(readFileSync(state, "utf8"));
    const facts = readFileSync(join(this.dir, "facts.jsonl"), "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l) as Fact);
    return new Memory(scope, cursor, facts);
  }

  async save(memory: AgentMemory): Promise<void> {
    writeAtomic(join(this.dir, "facts.jsonl"), toLines(memory.facts));
    writeAtomic(join(this.dir, "memory.json"), JSON.stringify({ scope: memory.scope, cursor: memory.cursor }) + "\n");
  }
}

/** Decides each tool call: reading stays inside the work folder, writing only touches facts.jsonl, the shell only runs rg. */
function policy(work: string, call: any): { allow: boolean; why: string } {
  const raw = call?.rawInput ?? {};
  const paths = Object.entries(raw)
    .filter(([key, value]) => /path|file|target/i.test(key) && typeof value === "string")
    .map(([, value]) => resolve(work, value as string));
  const inside = paths.every((p) => p === work || p.startsWith(`${work}/`));
  switch (call?.kind) {
    case "read":
    case "search":
      return { allow: inside, why: inside ? "leitura na pasta" : "leitura fora da pasta" };
    case "edit": {
      const ok = paths.length > 0 && paths.every((p) => p === join(work, "facts.jsonl"));
      return { allow: ok, why: ok ? "facts.jsonl" : "escrita fora de facts.jsonl" };
    }
    case "execute": {
      const command = String(raw.command ?? raw.cmd ?? "").trim();
      const ok = /^rg\s[^;|&`$<>\n]*$/.test(command);
      return { allow: ok, why: ok ? "rg" : `shell recusado: ${command.slice(0, 80)}` };
    }
    case "think":
      return { allow: true, why: "pensar" };
    default:
      return { allow: false, why: `tipo não previsto: ${call?.kind}` };
  }
}

class DevinExtractor implements FactExtractor {
  private readonly prompt = readFileSync(PROMPT, "utf8");

  private constructor(private readonly devin: LocalDevin, private readonly work: string, private readonly model: string) {}

  static async open(work: string, model: string): Promise<DevinExtractor> {
    const cli = Bun.which(process.env.DEVIN_BIN ?? "devin");
    if (!cli) throw new Error("Devin CLI não encontrado");
    const devin = await LocalDevin.spawn(cli, {
      cwd: work,
      model,
      onPermission: (request) => {
        const verdict = policy(work, request.call);
        console.error(`  ${verdict.allow ? "ok" : "NEGADO"} ${request.call?.kind} :: ${verdict.why}`);
        const kind = verdict.allow ? "allow_once" : "reject_once";
        const option = request.options.find((o) => o.kind === kind);
        if (!option) throw new Error(`sem opção ${kind}`);
        return { optionId: option.optionId };
      },
    });
    return new DevinExtractor(devin, work, model);
  }

  async extract({ window, current, rules, rejected }: ExtractionRequest): Promise<Proposal> {
    const put = (name: string, content: string) => writeFileSync(join(this.work, name), content);
    put("janela.txt", render(window.messages));
    put("falas-janela.txt", render(window.messages.filter((m) => m.fromOwner)));
    put("input.txt", render(window.history.messages));
    if (rules !== null) put("regras-atuais.md", rules);
    if (!rejected) put("facts.jsonl", toLines(current));

    const repair = rejected
      ? `\n\n## Correção\n\nO validador recusou o facts.jsonl atual. Corrija só isto:\n${rejected.violations.map((v) => `- [${v.title}] ${v.code}: ${v.detail}`).join("\n")}\n`
      : "";
    const session = await this.devin.createSession({ cwd: this.work, model: this.model });
    let timer: Timer | undefined;
    try {
      const timeout = new Promise<never>((_, fail) => {
        timer = setTimeout(() => fail(new Error("turno excedeu o tempo")), TURN_TIMEOUT_MS);
      });
      await Promise.race([session.send(this.prompt + repair), timeout]);
    } finally {
      clearTimeout(timer);
    }
    return proposalOf(window, readFileSync(join(this.work, "facts.jsonl"), "utf8"));
  }

  close() {
    this.devin.close();
  }
}

async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      out: { type: "string" },
      every: { type: "string", default: process.env.MEMORY_EVERY ?? "20" },
      model: { type: "string", default: process.env.MEMORY_MODEL ?? "swe-2-high" },
      rules: { type: "string" },
      limit: { type: "string" },
      last: { type: "string" },
    },
  });
  const input = positionals[0] ?? process.cwd();
  const scope = scopeOf(input);
  const last = values.last ? Number(values.last) : null;
  const whole = await new JsonlTranscriptReader().read(input);
  const transcript = last ? whole.last(last) : whole;
  if (!transcript.messages.length) throw new Error("nenhuma mensagem encontrada");
  const out = resolve(values.out ?? join(".memory", last ? `${scope}-last` : scope));
  mkdirSync(join(out, "work"), { recursive: true });
  const work = realpathSync(join(out, "work"));

  const store = new FileStore(out);
  const rules = values.rules ? readFileSync(values.rules, "utf8") : null;
  let memory = last ? new Memory(scope, 0, []) : await store.load(scope);
  const windows = transcript.windows(memory.cursor, Number(values.every));
  const todo = values.limit ? windows.slice(0, Number(values.limit)) : windows;
  console.error(`${scope}: ${transcript.messages.length} mensagens, cursor ${memory.cursor}, ${todo.length} janelas`);
  if (!todo.length) return;

  const extractor = await DevinExtractor.open(work, values.model!);
  try {
    for (const window of todo) {
      const started = Date.now();
      let proposal = await extractor.extract({ window, current: memory.facts, rules, rejected: null });
      for (let attempt = 0; proposal.violations.length && attempt < MAX_REPAIRS; attempt++) {
        console.error(`  janela ${window.index}: ${proposal.violations.length} violações, corrigindo`);
        proposal = await extractor.extract({ window, current: memory.facts, rules, rejected: proposal });
      }
      if (proposal.violations.length) {
        for (const v of proposal.violations) console.error(`  - [${v.title}] ${v.code}: ${v.detail}`);
        process.exitCode = 1;
        throw new Error(`janela ${window.index} recusada; a memória continua no cursor ${memory.cursor}`);
      }
      memory = memory.absorb(proposal);
      await store.save(memory);
      console.error(`janela ${window.index}/${todo.length}: ${memory.facts.length} fatos, ${Math.round((Date.now() - started) / 1000)}s`);
    }
  } finally {
    extractor.close();
  }
  console.log(join(out, "facts.jsonl"));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
