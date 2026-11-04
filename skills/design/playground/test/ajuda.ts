/**
 * Ajudantes dos testes: pasta temporária, app em porta aleatória, cliente MCP
 * por InMemoryTransport, leitor de SSE e espera por condição.
 */
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { criarApp, type App, type OpcoesApp } from "../src/app.ts";
import type { Mensagem } from "../src/tipos.ts";

export const RAIZ = join(import.meta.dir, "..");

// O log do servidor (stderr) só polui a saída dos testes; LOG=1 mostra.
if (process.env.LOG !== "1") {
  const original = console.error.bind(console);
  console.error = (...partes: unknown[]) => {
    if (partes[0] === "[design-playground]") return;
    original(...partes);
  };
}

export function pastaTemporaria(): { dir: string; apagar: () => void } {
  const dir = mkdtempSync(join(tmpdir(), "design-playground-teste-"));
  return { dir, apagar: () => rmSync(dir, { recursive: true, force: true }) };
}

/** Sobe um app em porta aleatória, sem navegador, numa pasta temporária. */
export function subirApp(opcoes: OpcoesApp = {}): App & { dadosDir: string; encerrar: () => Promise<void> } {
  const pasta = opcoes.dadosDir ? undefined : pastaTemporaria();
  const dadosDir = opcoes.dadosDir ?? pasta!.dir;
  const app = criarApp({ porta: 0, abrirWeb: false, pingMs: 60_000, progressoMs: 60_000, ...opcoes, dadosDir });
  return {
    ...app,
    dadosDir,
    encerrar: async () => {
      await app.parar();
      pasta?.apagar();
    },
  };
}

/** Liga um Client do SDK ao app por InMemoryTransport. */
export async function ligarMcp(app: App): Promise<{ client: Client; fechar: () => Promise<void> }> {
  const mcp = app.criarMcp();
  const [ladoCliente, ladoServidor] = InMemoryTransport.createLinkedPair();
  await mcp.connect(ladoServidor);
  const client = new Client({ name: "teste", version: "0.0.0" });
  await client.connect(ladoCliente);
  return {
    client,
    fechar: async () => {
      await client.close();
      await mcp.close();
    },
  };
}

/** Liga um Client do SDK ao /mcp por Streamable HTTP. `fechar` encerra a sessão (DELETE) e o cliente. */
export async function ligarHttp(
  url: string,
  opcoes: { headers?: Record<string, string>; nome?: string } = {},
): Promise<{ client: Client; transporte: StreamableHTTPClientTransport; fechar: () => Promise<void> }> {
  const transporte = new StreamableHTTPClientTransport(new URL(`${url}/mcp`), { requestInit: { headers: opcoes.headers ?? {} } });
  const client = new Client({ name: opcoes.nome ?? "teste-http", version: "0.0.0" });
  await client.connect(transporte);
  let fechado = false;
  return {
    client,
    transporte,
    fechar: async () => {
      if (fechado) return;
      fechado = true;
      await transporte.terminateSession().catch(() => {});
      await client.close();
    },
  };
}

export function textoDe(resultado: unknown): string {
  const r = resultado as CallToolResult;
  const primeiro = r.content[0];
  if (!primeiro || primeiro.type !== "text") throw new Error("resultado sem texto: " + JSON.stringify(r));
  return primeiro.text;
}

export function mensagensDe(resultado: unknown): Mensagem[] {
  return (JSON.parse(textoDe(resultado)) as { mensagens: Mensagem[] }).mensagens;
}

export async function postar(url: string, texto: string, selecao?: string[]): Promise<Mensagem> {
  const r = await fetch(`${url}/api/mensagens`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(selecao === undefined ? { texto } : { texto, selecao }),
  });
  if (r.status !== 201) throw new Error(`POST /api/mensagens: ${r.status} ${await r.text()}`);
  return ((await r.json()) as { mensagem: Mensagem }).mensagem;
}

export async function estado(url: string): Promise<{ motor: string; digitando: boolean; mensagens: Mensagem[] }> {
  const r = await fetch(`${url}/api/estado`);
  return (await r.json()) as { motor: string; digitando: boolean; mensagens: Mensagem[] };
}

/** Espera `cond()` ficar verdadeira, olhando a cada 10 ms. */
export async function ate(cond: () => boolean | Promise<boolean>, timeoutMs = 2000, o_que = "condição"): Promise<void> {
  const fim = Date.now() + timeoutMs;
  while (Date.now() < fim) {
    if (await cond()) return;
    await Bun.sleep(10);
  }
  throw new Error(`tempo esgotado esperando ${o_que}`);
}

/** Uma porta livre agora (pede uma ao sistema e solta). */
export async function portaLivre(): Promise<number> {
  const s = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response() });
  const porta = s.port!;
  await s.stop(true);
  return porta;
}

// ---------- SSE ----------

export type EventoSSE = { evento: string; dados: unknown } | { comentario: string };

/** Lê /api/eventos com fetch e um leitor, guardando cada evento na ordem. */
export class LeitorSSE {
  readonly eventos: EventoSSE[] = [];
  private readonly usados = new Set<number>();
  private avisar: (() => void)[] = [];
  private fechado = false;
  private readonly controle = new AbortController();
  private laco: Promise<void> = Promise.resolve();
  status = 0;
  tipo = "";

  static async abrir(url: string): Promise<LeitorSSE> {
    const leitor = new LeitorSSE();
    const r = await fetch(`${url}/api/eventos`, { signal: leitor.controle.signal });
    leitor.status = r.status;
    leitor.tipo = r.headers.get("content-type") ?? "";
    leitor.laco = leitor.ler(r.body!.getReader());
    return leitor;
  }

  private async ler(reader: { read(): Promise<{ value?: Uint8Array; done: boolean }> }): Promise<void> {
    const decodificador = new TextDecoder();
    let buffer = "";
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decodificador.decode(value, { stream: true });
        let fim: number;
        while ((fim = buffer.indexOf("\n\n")) >= 0) {
          const bloco = buffer.slice(0, fim);
          buffer = buffer.slice(fim + 2);
          this.analisar(bloco);
        }
      }
    } catch {
      // abortado
    } finally {
      this.fechado = true;
      this.notificar();
    }
  }

  private analisar(bloco: string): void {
    let evento = "message";
    const dados: string[] = [];
    let comentario: string | undefined;
    let temCampo = false;
    for (const linha of bloco.split("\n")) {
      if (linha.startsWith(":")) {
        comentario = linha.slice(1).trim();
        continue;
      }
      const i = linha.indexOf(":");
      const campo = i < 0 ? linha : linha.slice(0, i);
      const valor = i < 0 ? "" : linha.slice(i + 1).replace(/^ /, "");
      if (campo === "event") {
        evento = valor;
        temCampo = true;
      } else if (campo === "data") {
        dados.push(valor);
        temCampo = true;
      }
    }
    if (dados.length > 0) this.eventos.push({ evento, dados: JSON.parse(dados.join("\n")) });
    else if (comentario !== undefined && !temCampo) this.eventos.push({ comentario });
    this.notificar();
  }

  private notificar(): void {
    const avisos = this.avisar;
    this.avisar = [];
    for (const a of avisos) a();
  }

  /** Os eventos nomeados (sem comentários nem `retry`). */
  nomeados(): { evento: string; dados: unknown }[] {
    return this.eventos.filter((e): e is { evento: string; dados: unknown } => "evento" in e);
  }

  /** Espera o próximo evento ainda não consumido que satisfaz `pred` e o consome. */
  async esperar(pred: (e: EventoSSE) => boolean, timeoutMs = 2000): Promise<EventoSSE> {
    const fim = Date.now() + timeoutMs;
    for (;;) {
      const i = this.eventos.findIndex((e, n) => !this.usados.has(n) && pred(e));
      if (i >= 0) {
        this.usados.add(i);
        return this.eventos[i]!;
      }
      const falta = fim - Date.now();
      if (falta <= 0 || this.fechado) {
        throw new Error(`SSE: evento não chegou; recebidos: ${JSON.stringify(this.eventos)}`);
      }
      await new Promise<void>((resolve) => {
        const t = setTimeout(resolve, falta);
        this.avisar.push(() => {
          clearTimeout(t);
          resolve();
        });
      });
    }
  }

  async evento<T = unknown>(nome: string, filtro: (dados: T) => boolean = () => true, timeoutMs = 2000): Promise<T> {
    const e = await this.esperar((e) => "evento" in e && e.evento === nome && filtro(e.dados as T), timeoutMs);
    return (e as { dados: T }).dados;
  }

  /** Resolve quando o stream termina (pelo servidor ou por fechar()). */
  terminou(): Promise<void> {
    return this.laco;
  }

  async fechar(): Promise<void> {
    this.controle.abort();
    await this.laco;
  }
}

/** Um rascunho válido do formato do CONTRATO (sem versao). */
export function rascunho(id = "loja/aviso-cliente"): Record<string, unknown> {
  return {
    id,
    nome: "Aviso da cliente",
    descricao: "O aviso no topo quando a corretora busca para uma cliente.",
    estado: "rascunho",
    html: '<div class="aviso"><b class="titulo">Buscando para</b><span class="nome">Vera</span></div>',
    css: ".aviso{padding:8px}",
    w: 393,
    h: 64,
    slots: [
      { chave: "titulo", seletor: ".titulo", como: "texto" },
      { chave: "nome", seletor: ".nome", como: "texto" },
      { chave: "cor", seletor: ".aviso", como: "estilo:background" },
    ],
    dados: { titulo: "Buscando para", nome: "Vera" },
  };
}

/** As ferramentas do MCP, em ordem alfabética. */
export const FERRAMENTAS = ["canvas_agrupar","canvas_apagar","canvas_criar","canvas_focar","canvas_ler","canvas_mudar","chat_aguardar","chat_apagar","chat_atividade","chat_digitando","chat_historico","chat_responder","componente_definir","componente_ler","componente_listar","componentes_conferir","instancia_inserir","instancia_mudar","tela_criar","tela_ler","tela_montar","tela_mudar","web_abrir"];
