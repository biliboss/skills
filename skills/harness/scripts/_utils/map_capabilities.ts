#!/usr/bin/env bun
// map_capabilities.ts: mapa de capacidades dos CLIs de agente, gerado do --help de cada um.
//
// Uso:
//   bun map_capabilities.ts                  gera resources/map_capabilities.jsonl (spawna os CLIs)
//   bun map_capabilities.ts --out <arq>      grava em outro arquivo
//   bun map_capabilities.ts --harness a,b    so esses CLIs (exige --out)
//   bun map_capabilities.ts --matrix [arq]   imprime capacidade x harness lendo o JSONL (nao spawna nada)
//
// Seguranca: o unico argv que este script spawna e `<cli> --version`, `<cli> --help` e
// `<cli> <sub> [<sub2>] --help`, com timeout de 10 s, stdin fechado e NO_COLOR=1.
// Subcomando com nome que altera estado (DENY) nunca e invocado: entra no mapa pela
// listagem do pai. Todo argv spawnado vai para o stderr, uma linha `spawn ...`.
// Saida deterministica: ordenada, sem timestamp, $HOME trocado por `~`.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const HERE = import.meta.dir;
const DEFAULT_OUT = join(HERE, "..", "..", "resources", "map_capabilities.jsonl");
const HOME = process.env.HOME ?? "";
const TIMEOUT_MS = 10_000;
const MAX_DEPTH = 2; // cli sub sub2 --help
const CONCURRENCY = 3;
const ABOUT_MAX = 400;

const HARNESSES = ["claude", "codex", "devin", "hermes", "opencode", "pi", "prime-agent"];

// ---------------------------------------------------------------- seguranca

// Nomes que alteram estado. Compara por palavra inteira (separando por - _ . :), sem caixa.
const DENY = new Set([
  "update", "install", "uninstall", "remove", "rm", "delete", "archive", "unarchive",
  "login", "logout", "apply", "queue", "setup", "migrate",
  "upgrade", "reset", "clear", "prune", "kill", "stop", "restart", "add", "create", "new",
  "import", "sync", "publish", "deploy", "unlink", "link", "auth", "set", "unset",
  "purge", "respawn", "restore", "rollback", "revert", "wipe", "destroy", "cleanup",
  "start", "serve", "web", "daemon", "shutdown", "pause",
]);

// CLIs onde a gente nao confia que `<sub> --help` seja inerte: so desce nestes subcomandos.
const ONLY_DESCEND: Record<string, Set<string>> = {
  "prime-agent": new Set(["model", "mcp", "list", "sessions", "status"]),
};
// CLIs em que nunca se desce (help plano).
const NEVER_DESCEND = new Set(["pi"]);

// Extras por CLI: verbos que disparam execucao no hermes (cron tick, gateway run/ensure).
const DENY_BY_HARNESS: Record<string, Set<string>> = {
  hermes: new Set(["run", "tick", "trigger", "ensure"]),
};

export function isDenied(name: string, harness = ""): boolean {
  const extra = DENY_BY_HARNESS[harness];
  return name
    .toLowerCase()
    .split(/[-_.:|/]+/)
    .some((w) => DENY.has(w) || (extra?.has(w) ?? false));
}

const SUB_RE = /^[A-Za-z][A-Za-z0-9_-]*$/;

// Guarda central: so deixa passar os formatos de argv permitidos.
function assertSafeArgs(bin: string, args: string[]): void {
  const last = args[args.length - 1];
  if (args.length === 1 && (last === "--version" || last === "--help")) return;
  if (last !== "--help") throw new Error(`argv recusado: ${args.join(" ")}`);
  const subs = args.slice(0, -1);
  if (subs.length > MAX_DEPTH) throw new Error(`profundidade recusada: ${args.join(" ")}`);
  for (const s of subs) {
    if (!SUB_RE.test(s)) throw new Error(`subcomando invalido: ${s}`);
    if (isDenied(s, bin)) throw new Error(`subcomando negado: ${s}`);
  }
}

// ---------------------------------------------------------------- spawn

type RunResult = { ok: boolean; code: number | null; timedOut: boolean; text: string };

// Le o stream aos poucos para o buffer: se um processo neto herdar o pipe e segurar,
// o que ja chegou nao se perde.
function drain(stream: ReadableStream<Uint8Array> | null | undefined, buf: { s: string }): Promise<void> {
  if (!stream) return Promise.resolve();
  const dec = new TextDecoder();
  return (async () => {
    try {
      for await (const chunk of stream) buf.s += dec.decode(chunk, { stream: true });
    } catch {}
  })();
}

async function run(bin: string, args: string[]): Promise<RunResult> {
  // Ate 3 tentativas, so em caso de timeout (maquina carregada); o argv e o mesmo e tambem vai para o log.
  let r = await runOnce(bin, args);
  for (let n = 1; r.timedOut && n < 3; n++) r = await runOnce(bin, args);
  return r;
}

async function runOnce(bin: string, args: string[]): Promise<RunResult> {
  assertSafeArgs(bin, args);
  const path = Bun.which(bin);
  console.error(`spawn ${[bin, ...args].join(" ")}`);
  if (!path) return { ok: false, code: null, timedOut: false, text: `${bin}: nao encontrado no PATH` };
  let timedOut = false;
  const proc = Bun.spawn([path, ...args], {
    stdin: "ignore",
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env, NO_COLOR: "1" },
    cwd: "/", // padroes que dependem do cwd (ex.: opencode) ficam estaveis entre execucoes
  });
  const timer = setTimeout(() => {
    timedOut = true;
    try {
      proc.kill("SIGKILL");
    } catch {}
  }, TIMEOUT_MS);
  const outBuf = { s: "" };
  const errBuf = { s: "" };
  const pipes = Promise.all([drain(proc.stdout, outBuf), drain(proc.stderr, errBuf)]);
  const code = await proc.exited; // o timeout conta ate o PROCESSO sair, nao ate o pipe fechar
  clearTimeout(timer);
  // depois da saida, da no maximo 2 s para o pipe esvaziar (neto pode segura-lo aberto)
  await Promise.race([pipes, new Promise<void>((r) => setTimeout(r, 2000))]);
  const out = outBuf.s;
  const err = errBuf.s;
  const text = out.trim() ? out : err;
  return { ok: !timedOut && (code === 0 || text.trim().length > 0), code, timedOut, text };
}

// ---------------------------------------------------------------- normalizacao

function clean(s: string): string {
  let t = s.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, "").replace(/\r/g, "");
  if (HOME) t = t.split(HOME).join("~");
  return t;
}

function squash(s: string): string {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > ABOUT_MAX ? t.slice(0, ABOUT_MAX - 1) + "…" : t;
}

// ---------------------------------------------------------------- parser

export type Item = {
  harness: string;
  version: string;
  kind: "flag" | "command" | "arg" | "env" | "entry" | "raw";
  path: string[];
  name: string | null;
  aliases: string[];
  value: string | null;
  env: string | null;
  about: string | null;
  capability: string | null;
};

type Draft = Omit<Item, "harness" | "version" | "capability">;

const indentOf = (l: string) => l.length - l.trimStart().length;

const FLAG_RE = /^(--?[A-Za-z0-9][\w.-]*)(?:\[=[^\]]*\])?/;
const VALUE_RE = /^(?:[ =](<[^>]+>|\[[^\]]+\]|\{[^}]+\}|[A-Z][A-Z0-9_.-]*(?:\.\.\.)?(?=$|[,\s]))|(<[^>]+>|\[[^\]]+\]))/;

// "-m MODEL, --model MODEL  about", "--name, -n <name>", "--export <file> [output]"
function parseFlagLine(s: string): { names: string[]; values: string[]; rest: string } | null {
  const names: string[] = [];
  const values: string[] = [];
  let i = 0;
  for (;;) {
    const m = FLAG_RE.exec(s.slice(i));
    if (!m) break;
    names.push(m[1]);
    i += m[0].length;
    for (;;) {
      const v = VALUE_RE.exec(s.slice(i));
      if (!v) break;
      values.push(v[1] ?? v[2]);
      i += v[0].length;
    }
    const sep = /^,\s*/.exec(s.slice(i));
    if (!sep) break;
    i += sep[0].length;
  }
  if (!names.length) return null;
  return { names, values, rest: s.slice(i).trim() };
}

type SectionKind = "none" | "usage" | "opt" | "cmd" | "arg" | "env" | "example" | "other";

function classify(title: string): SectionKind {
  const t = title.toLowerCase();
  if (/^usage/.test(t)) return "usage";
  if (/example/.test(t)) return "example";
  if (/environment|env var/.test(t)) return "env";
  if (/command/.test(t)) return "cmd";
  if (/option|flag/.test(t)) return "opt";
  if (/argument|positional/.test(t)) return "arg";
  return "other";
}

const HEADER_RE = /^([A-Za-z][A-Za-z0-9 ()/_-]*):\s*$/;

export function parseHelp(harness: string, path: string[], rawText: string): Draft[] {
  const lines = clean(rawText).split("\n").map((l) => l.replace(/\s+$/, "").replace(/\t/g, "    "));
  const out: Draft[] = [];
  let section: SectionKind = "none";
  let title = "";
  let base = -1; // indentacao dos itens da secao
  let metaSub = false; // secao argparse com `{a,b}` / `<command>` e comandos mais fundos
  let cur: Draft | null = null;
  const aboutParts: string[] = [];

  const flush = () => {
    if (cur) {
      const a = squash(aboutParts.join(" "));
      cur.about = a || null;
      if (cur.kind === "flag" && cur.about) {
        const e = /\[env: ([A-Z][A-Z0-9_]*)/.exec(cur.about);
        if (e) cur.env = e[1];
      }
      out.push(cur);
    }
    cur = null;
    aboutParts.length = 0;
  };
  const start = (d: Partial<Draft> & Pick<Draft, "kind">, about: string) => {
    flush();
    cur = { path: [...path], name: null, aliases: [], value: null, env: null, about: null, ...d };
    if (about) aboutParts.push(about);
  };
  const raw = (text: string) => {
    flush();
    // linhas de prosa seguidas viram um raw so
    const last = out[out.length - 1];
    if (last && last.kind === "raw" && last.path.join(" ") === path.join(" ")) {
      last.about = squash(`${last.about ?? ""} ${text}`);
      return;
    }
    out.push({ kind: "raw", path: [...path], name: null, aliases: [], value: null, env: null, about: squash(text), });
  };

  // Item de comando ou argumento: "name [value]  about" (separador = 2+ espacos).
  const nameLine = (body: string, kind: "command" | "arg") => {
    const parts = body.split(/\s{2,}/);
    let spec = parts[0];
    let about = parts.slice(1).join(" ");
    // yargs / pi: "opencode run [message..]" -> tira o nome do CLI
    const toks0 = spec.split(/\s+/);
    for (const pre of [harness, ...path]) if (toks0.length > 1 && toks0[0] === pre) toks0.shift();
    spec = toks0.join(" ");
    const toks = spec.split(/\s+/);
    const first = toks[0];
    const valueStr = toks.slice(1).join(" ") || null;
    if (kind === "command" && /^[<\[{]/.test(first)) {
      start({ kind: "arg", name: first, value: valueStr }, about);
      return;
    }
    const names = first.split("|");
    start({ kind, name: names[0], aliases: names.slice(1), value: valueStr }, about);
  };

  for (const line of lines) {
    if (!line.trim()) continue;
    const ind = indentOf(line);
    const body = line.trim();

    // argparse: "usage: ..." com continuacao indentada
    if (/^usage:/i.test(body) && ind === 0) {
      flush();
      section = "usage";
      continue;
    }
    if (/^examples?:$/i.test(body) && (ind === 0 || (base >= 0 && ind <= base))) {
      flush();
      section = "example";
      title = body.slice(0, -1);
      continue;
    }
    const h = ind === 0 ? HEADER_RE.exec(body) : null;
    if (h) {
      flush();
      title = h[1];
      section = classify(title);
      base = -1;
      metaSub = false;
      continue;
    }
    if (section === "none" || section === "usage" || section === "example") continue;
    if (section === "usage") continue;

    if (base < 0) base = ind;

    if (section === "opt") {
      const isFlagLine = /^-{1,2}[A-Za-z0-9]/.test(body) && ind <= base + 4;
      if (isFlagLine) {
        const f = parseFlagLine(body);
        if (f) {
          const long = f.names.find((n) => n.startsWith("--")) ?? f.names[0];
          start(
            { kind: "flag", name: long, aliases: f.names.filter((n) => n !== long), value: f.values.join(" ") || null },
            f.rest,
          );
          continue;
        }
        raw(body);
        continue;
      }
      if (cur && ind > base) {
        aboutParts.push(body);
        continue;
      }
      // pi: "--" sozinho e bem-formado
      if (/^--\s{2,}/.test(body)) {
        const parts = body.split(/\s{2,}/);
        start({ kind: "flag", name: "--" }, parts.slice(1).join(" "));
        continue;
      }
      raw(body);
      continue;
    }

    if ((section === "cmd" || section === "arg") && base > 0 && ind < base) {
      raw(body); // prosa fora da lista (ex.: 'Run "x help <command>" ...')
      continue;
    }

    if (section === "cmd" || section === "arg") {
      // meta argparse: "{a,b,c}" ou "<command>" abre a lista de comandos mais funda
      if (/^(\{[^}]*\}|<command>)/.test(body) && ind <= base + 2 && !metaSub) {
        const toks = body.split(/\s{2,}/);
        flush();
        metaSub = true;
        base = -2; // o proximo item define a indentacao dos comandos
        if (section === "arg") {
          // fica registrado como argumento posicional, nada some
          start({ kind: "arg", name: toks[0].split(/\s+/)[0] }, toks.slice(1).join(" "));
        }
        continue;
      }
      if (base === -2) base = ind;
      if (ind <= base && !/^[-]{1,2}\s/.test(body)) {
        // flags dentro de secao de comandos (raro): trate como flag
        if (/^-{1,2}[A-Za-z0-9]/.test(body)) {
          const f = parseFlagLine(body);
          if (f) {
            const long = f.names.find((n) => n.startsWith("--")) ?? f.names[0];
            start({ kind: "flag", name: long, aliases: f.names.filter((n) => n !== long), value: f.values.join(" ") || null }, f.rest);
            continue;
          }
        }
        nameLine(body, metaSub || section === "cmd" ? "command" : "arg");
        continue;
      }
      if (cur && ind > base) {
        aboutParts.push(body);
        continue;
      }
      raw(body);
      continue;
    }

    if (section === "env") {
      const m = /^([A-Z][A-Z0-9_]*)\s*(?:[-:]\s+|\s{2,})?(.*)$/.exec(body);
      if (ind <= base && m && /^[A-Z][A-Z0-9_]*$/.test(m[1])) {
        start({ kind: "env", name: m[1] }, m[2]);
        continue;
      }
      if (cur && ind > base) {
        aboutParts.push(body);
        continue;
      }
      raw(body);
      continue;
    }

    // outras secoes ("Built-in Tool Names", "Help", ...): "nome - texto" ou "nome  texto"
    {
      const m = /^(\S+(?:, \S+)*)\s+(?:-\s+)?(\S.*)$/.exec(body);
      if (ind <= base && m && (/\s-\s/.test(body) || /\s{2,}/.test(body))) {
        const f = /^-{1,2}[A-Za-z0-9]/.test(body) ? parseFlagLine(body) : null;
        if (f) {
          const long = f.names.find((n) => n.startsWith("--")) ?? f.names[0];
          start({ kind: "flag", name: long, aliases: f.names.filter((n) => n !== long), value: f.values.join(" ") || null }, f.rest);
        } else {
          start({ kind: "entry", name: m[1], value: title }, m[2]);
        }
        continue;
      }
      if (cur && ind > base) {
        aboutParts.push(body);
        continue;
      }
      raw(body);
    }
  }
  flush();
  return out;
}

// ---------------------------------------------------------------- regras de capacidade
//
// A unica fonte do campo `capability`. Cada regra: harness ("*" = todos), kind,
// path ([] = raiz) e os nomes (flag ou comando) que ela cobre.

type Rule = { h: string; kind: "flag" | "command" | "arg"; path: string[]; names: string[]; cap: string };

const R = (h: string, kind: "flag" | "command" | "arg", path: string[], names: string[], cap: string): Rule => ({ h, kind, path, names, cap });

const F = "flag" as const;
const C = "command" as const;
const A = "arg" as const;
const ALL = "*";

export const RULES: Rule[] = [
  // prompt.initial: prompt posicional, ou a flag que o recebe
  R("claude", A, [], ["prompt"], "prompt.initial"),
  R("codex", A, [], ["[PROMPT]"], "prompt.initial"),
  R("codex", A, ["exec"], ["[PROMPT]"], "prompt.initial"),
  R("devin", A, [], ["[PROMPT]..."], "prompt.initial"),
  R("opencode", F, [], ["--prompt"], "prompt.initial"),
  R("opencode", A, ["run"], ["message"], "prompt.initial"),
  R("hermes", F, ["chat"], ["--query"], "prompt.initial"),
  // prompt.file
  R("devin", F, [], ["--prompt-file"], "prompt.file"),
  R("hermes", F, ["chat"], ["--query-file"], "prompt.file"),
  // run.noninteractive
  R("claude", F, [], ["--print"], "run.noninteractive"),
  R("devin", F, [], ["--print"], "run.noninteractive"),
  R("pi", F, [], ["--print"], "run.noninteractive"),
  R("prime-agent", F, [], ["--print"], "run.noninteractive"),
  R("codex", C, [], ["exec"], "run.noninteractive"),
  R("opencode", C, [], ["run"], "run.noninteractive"),
  R("hermes", F, [], ["--oneshot"], "run.noninteractive"),
  R("hermes", F, ["chat"], ["--oneshot"], "run.noninteractive"),
  // session.resume
  R("claude", F, [], ["--resume"], "session.resume"),
  R("devin", F, [], ["--resume"], "session.resume"),
  R("pi", F, [], ["--resume", "--session"], "session.resume"),
  R("prime-agent", F, [], ["--resume"], "session.resume"),
  R("hermes", F, [], ["--resume"], "session.resume"),
  R("hermes", C, [], ["resume"], "session.resume"),
  R("codex", C, [], ["resume"], "session.resume"),
  R("opencode", F, [], ["--session"], "session.resume"),
  // session.continue
  R(ALL, F, [], ["--continue"], "session.continue"),
  R("codex", F, ["resume"], ["--last"], "session.continue"),
  // session.fork
  R("claude", F, [], ["--fork-session"], "session.fork"),
  R("pi", F, [], ["--fork"], "session.fork"),
  R("prime-agent", F, [], ["--fork"], "session.fork"),
  R("opencode", F, [], ["--fork"], "session.fork"),
  R("codex", C, [], ["fork"], "session.fork"),
  // session.name
  R("claude", F, [], ["--name"], "session.name"),
  R("pi", F, [], ["--name"], "session.name"),
  // sessions.list
  R("devin", C, [], ["list"], "sessions.list"),
  R("opencode", C, ["session"], ["list"], "sessions.list"),
  R("hermes", C, [], ["sessions"], "sessions.list"),
  R("prime-agent", C, [], ["list", "sessions"], "sessions.list"),
  R("claude", C, [], ["agents"], "sessions.list"),
  // model.select
  R(ALL, F, [], ["--model"], "model.select"),
  R("codex", F, ["exec"], ["--model"], "model.select"),
  R("opencode", F, ["run"], ["--model"], "model.select"),
  R("devin", C, [], ["models"], "model.select"),
  R("opencode", C, [], ["models"], "model.select"),
  R("prime-agent", C, [], ["model"], "model.select"),
  R("hermes", C, [], ["model"], "model.select"),
  // reasoning.level
  R("claude", F, [], ["--effort"], "reasoning.level"),
  R("pi", F, [], ["--thinking"], "reasoning.level"),
  R("prime-agent", F, [], ["--thinking"], "reasoning.level"),
  R("hermes", F, [], ["--reasoning"], "reasoning.level"),
  R("opencode", F, ["run"], ["--thinking", "--variant"], "reasoning.level"),
  // prompt.system
  R("claude", F, [], ["--system-prompt", "--append-system-prompt"], "prompt.system"),
  R("pi", F, [], ["--system-prompt", "--append-system-prompt"], "prompt.system"),
  R("prime-agent", F, [], ["--system-prompt", "--append-system-prompt"], "prompt.system"),
  // permission.mode
  R("claude", F, [], ["--permission-mode"], "permission.mode"),
  R("codex", F, [], ["--ask-for-approval"], "permission.mode"),
  R("devin", F, [], ["--permission-mode"], "permission.mode"),
  // permission.bypass
  R("claude", F, [], ["--dangerously-skip-permissions", "--allow-dangerously-skip-permissions"], "permission.bypass"),
  R("codex", F, [], ["--dangerously-bypass-approvals-and-sandbox"], "permission.bypass"),
  R("codex", F, ["exec"], ["--dangerously-bypass-approvals-and-sandbox"], "permission.bypass"),
  R("opencode", F, [], ["--auto"], "permission.bypass"),
  R("opencode", F, ["run"], ["--auto"], "permission.bypass"),
  R("hermes", F, [], ["--yolo"], "permission.bypass"),
  // tools.restrict
  R("claude", F, [], ["--tools", "--allowedTools", "--disallowedTools"], "tools.restrict"),
  R("pi", F, [], ["--tools", "--exclude-tools", "--no-tools", "--no-builtin-tools"], "tools.restrict"),
  R("hermes", F, [], ["--toolsets"], "tools.restrict"),
  // config.override
  R("claude", F, [], ["--settings", "--setting-sources"], "config.override"),
  R("codex", F, [], ["--config", "--profile"], "config.override"),
  R("codex", F, ["exec"], ["--config", "--profile"], "config.override"),
  R("devin", F, [], ["--config"], "config.override"),
  R("hermes", F, [], ["--ignore-user-config"], "config.override"),
  R("hermes", C, [], ["config"], "config.override"),
  R("prime-agent", C, [], ["config"], "config.override"),
  R("pi", C, [], ["config"], "config.override"),
  // rules.manage
  R("devin", C, [], ["rules"], "rules.manage"),
  R("hermes", F, [], ["--ignore-rules"], "rules.manage"),
  R("pi", F, [], ["--no-context-files"], "rules.manage"),
  R("prime-agent", F, [], ["--no-context-files"], "rules.manage"),
  // hooks.manage
  R("hermes", C, [], ["hooks"], "hooks.manage"),
  R("hermes", F, [], ["--accept-hooks"], "hooks.manage"),
  R("codex", F, [], ["--dangerously-bypass-hook-trust"], "hooks.manage"),
  // mcp.manage
  R(ALL, C, [], ["mcp"], "mcp.manage"),
  R("claude", F, [], ["--mcp-config", "--strict-mcp-config"], "mcp.manage"),
  R("pi", F, [], ["--mcp-config", "--no-mcp"], "mcp.manage"),
  // output.format
  R("claude", F, [], ["--output-format", "--input-format", "--json-schema"], "output.format"),
  R("codex", F, ["exec"], ["--json", "--output-schema"], "output.format"),
  R("opencode", F, ["run"], ["--format"], "output.format"),
  R("pi", F, [], ["--mode"], "output.format"),
  R("prime-agent", F, [], ["--mode"], "output.format"),
  // sandbox
  R("codex", F, [], ["--sandbox"], "sandbox"),
  R("codex", F, ["exec"], ["--sandbox"], "sandbox"),
  R("codex", C, [], ["sandbox"], "sandbox"),
  R("devin", F, [], ["--sandbox"], "sandbox"),
  R("devin", C, [], ["sandbox"], "sandbox"),
  // workdir.add, worktree
  R("claude", F, [], ["--add-dir"], "workdir.add"),
  R("codex", F, [], ["--add-dir"], "workdir.add"),
  R(ALL, F, [], ["--worktree"], "worktree"),
];

function capabilityOf(harness: string, d: Draft): string | null {
  if (d.kind !== "flag" && d.kind !== "command" && d.kind !== "arg") return null;
  for (const r of RULES) {
    if (r.h !== "*" && r.h !== harness) continue;
    if (r.kind !== d.kind) continue;
    if (r.path.join(" ") !== d.path.join(" ")) continue;
    if (d.name !== null && r.names.includes(d.name)) return r.cap;
  }
  return null;
}

// ---------------------------------------------------------------- coleta

function versionOf(text: string): string | null {
  const first = clean(text).split("\n").map((l) => l.trim()).find((l) => l);
  if (!first) return null;
  const m = /\bv?(\d+(?:\.\d+)+(?:[-+.][\w.]+)*)/.exec(first);
  return m ? m[1] : first.slice(0, 80);
}

type Collected = { version: string; drafts: Draft[] };

async function collect(harness: string): Promise<Collected> {
  const drafts: Draft[] = [];
  const rawAt = (path: string[], text: string) =>
    drafts.push({ kind: "raw", path, name: null, aliases: [], value: null, env: null, about: squash(text) });

  const v = await run(harness, ["--version"]);
  let version = "unknown";
  if (v.ok && v.text.trim()) version = versionOf(v.text) ?? "unknown";
  else rawAt([], `--version falhou: ${v.timedOut ? "timeout" : (v.text.trim() || `codigo ${v.code}`)}`);

  const top = await run(harness, ["--help"]);
  if (!top.ok || !top.text.trim()) {
    rawAt([], `--help falhou: ${top.timedOut ? "timeout" : (top.text.trim() || `codigo ${top.code}`)}`);
    return { version, drafts };
  }
  if (top.timedOut) rawAt([], "--help estourou o timeout; saida parcial");
  const results = new Map<string, string>(); // path -> texto (para detectar help identico ao do pai)
  results.set("", top.text);
  const topItems = parseHelp(harness, [], top.text);
  drafts.push(...topItems);
  if (NEVER_DESCEND.has(harness)) return { version, drafts };

  type Job = { path: string[]; parentKey: string };
  let level: Job[] = [];
  const enqueue = (items: Draft[], parentPath: string[]) => {
    const seen = new Set<string>();
    for (const it of items) {
      if (it.kind !== "command" || !it.name) continue;
      if (parentPath.length >= MAX_DEPTH) continue;
      if (it.name === "help" || !SUB_RE.test(it.name)) continue;
      const names = [it.name, ...it.aliases];
      if (names.some((n) => isDenied(n, harness))) {
        console.error(`skip-deny ${[harness, ...parentPath, it.name].join(" ")}`);
        continue;
      }
      const allow = ONLY_DESCEND[harness];
      if (allow && parentPath.length === 0 && !allow.has(it.name)) {
        console.error(`skip-nao-listado ${[harness, ...parentPath, it.name].join(" ")}`);
        continue;
      }
      if (allow && parentPath.length > 0) continue;
      const key = [...parentPath, it.name].join(" ");
      if (seen.has(key)) continue;
      seen.add(key);
      level.push({ path: [...parentPath, it.name], parentKey: parentPath.join(" ") });
    }
  };
  enqueue(topItems, []);

  while (level.length) {
    const jobs = level;
    level = [];
    const next: Array<{ path: string[]; items: Draft[] }> = [];
    let idx = 0;
    const worker = async () => {
      for (;;) {
        const j = jobs[idx++];
        if (!j) return;
        const r = await run(harness, [...j.path, "--help"]);
        const key = j.path.join(" ");
        if (!r.ok || !r.text.trim()) {
          rawAt(j.path, `--help falhou: ${r.timedOut ? "timeout" : (r.text.trim() || `codigo ${r.code}`)}`);
          continue;
        }
        if (r.timedOut) rawAt(j.path, "--help estourou o timeout; saida parcial");
        if (clean(r.text) === clean(results.get(j.parentKey) ?? "\u0000")) {
          rawAt(j.path, "help identico ao do pai (sem help proprio)");
          continue;
        }
        results.set(key, r.text);
        const items = parseHelp(harness, j.path, r.text);
        if (!items.length) rawAt(j.path, `nada parseado: ${r.text}`);
        next.push({ path: j.path, items });
      }
    };
    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, jobs.length) }, worker));
    for (const n of next) {
      drafts.push(...n.items);
    }
    // proximo nivel: ordem deterministica
    next.sort((a, b) => (a.path.join(" ") < b.path.join(" ") ? -1 : 1));
    for (const n of next) enqueue(n.items, n.path);
  }
  return { version, drafts };
}

// ---------------------------------------------------------------- saida

const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

function finalize(harness: string, c: Collected): Item[] {
  const items: Item[] = [];
  const seen = new Set<string>();
  for (const d of c.drafts) {
    if (d.kind !== "raw") {
      const key = [d.kind, d.path.join(" "), d.name].join("\u0000");
      if (seen.has(key)) continue;
      seen.add(key);
    }
    items.push({ harness, version: c.version, ...d, capability: capabilityOf(harness, d) });
  }
  return items;
}

function sortItems(items: Item[]): Item[] {
  return items.sort(
    (a, b) =>
      cmp(a.harness, b.harness) ||
      cmp(a.path.join(" "), b.path.join(" ")) ||
      cmp(a.kind, b.kind) ||
      cmp(a.name ?? "", b.name ?? "") ||
      cmp(a.about ?? "", b.about ?? ""),
  );
}

function toLine(i: Item): string {
  return JSON.stringify({
    harness: i.harness,
    version: i.version,
    kind: i.kind,
    path: i.path,
    name: i.name,
    aliases: i.aliases,
    value: i.value,
    env: i.env,
    about: i.about,
    capability: i.capability,
  });
}

// ---------------------------------------------------------------- matriz

function matrix(items: Item[]): string {
  const hs = [...new Set(items.map((i) => i.harness))].sort(cmp);
  const caps = [...new Set(items.map((i) => i.capability).filter((c): c is string => !!c))].sort(cmp);
  const cell = new Map<string, string[]>();
  for (const i of items) {
    if (!i.capability || !i.name) continue;
    const label = [...i.path, i.name].join(" ");
    const k = `${i.capability}\u0000${i.harness}`;
    const arr = cell.get(k) ?? [];
    arr.push(label);
    cell.set(k, arr);
  }
  const rows: string[][] = [["capability", ...hs]];
  for (const c of caps) rows.push([c, ...hs.map((h) => (cell.get(`${c}\u0000${h}`) ?? []).sort(cmp).join(", ") || "—")]);
  const w = rows[0].map((_, ci) => Math.max(...rows.map((r) => [...r[ci]].length)));
  const pad = (s: string, n: number) => s + " ".repeat(n - [...s].length);
  const fmt = (r: string[]) => "| " + r.map((x, ci) => pad(x, w[ci])).join(" | ") + " |";
  return [fmt(rows[0]), "|" + w.map((n) => "-".repeat(n + 2)).join("|") + "|", ...rows.slice(1).map(fmt)].join("\n") + "\n";
}

// ---------------------------------------------------------------- main

function readJsonl(path: string): Item[] {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as Item);
}

async function main() {
  const argv = process.argv.slice(2);
  const arg = (f: string) => {
    const i = argv.indexOf(f);
    return i >= 0 ? argv[i + 1] : undefined;
  };
  if (argv.includes("--matrix")) {
    const mi = argv.indexOf("--matrix");
    const file = argv[mi + 1] && !argv[mi + 1].startsWith("--") ? argv[mi + 1] : DEFAULT_OUT;
    if (!existsSync(file)) {
      console.error(`recusado: ${file} nao existe; rode sem --matrix primeiro`);
      process.exit(2);
    }
    process.stdout.write(matrix(readJsonl(file)));
    return;
  }
  const only = arg("--harness")?.split(",").filter(Boolean);
  const out = arg("--out") ?? DEFAULT_OUT;
  if (only && !arg("--out")) {
    console.error("recusado: --harness exige --out (nao sobrescreve o mapa completo com um parcial)");
    process.exit(2);
  }
  const list = (only ?? HARNESSES).filter((h) => HARNESSES.includes(h));
  const all: Item[] = [];
  for (const h of list) all.push(...finalize(h, await collect(h)));
  sortItems(all);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, all.map(toLine).join("\n") + "\n");
  const by = new Map<string, { n: number; raw: number; nul: number }>();
  for (const i of all) {
    const s = by.get(i.harness) ?? { n: 0, raw: 0, nul: 0 };
    s.n++;
    if (i.kind === "raw") s.raw++;
    if (i.capability === null) s.nul++;
    by.set(i.harness, s);
  }
  for (const [h, s] of [...by].sort((a, b) => cmp(a[0], b[0]))) console.error(`count ${h} itens=${s.n} raw=${s.raw} capability_null=${s.nul}`);
}

if (import.meta.main) await main();
