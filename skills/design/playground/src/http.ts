/**
 * As rotas HTTP do CONTRATO.md: a página e os estáticos de web/, o estado,
 * o envio de mensagens, o SSE, o espelho do canvas e os componentes. O /mcp
 * fica no mcp-http.ts (o app.ts junta os dois no mesmo Bun.serve).
 */
import { resolve, sep } from "node:path";
import type { Server } from "bun";
import type { Canvas, Registros } from "./canvas.ts";
import type { Chat } from "./chat.ts";
import type { Componentes } from "./componentes.ts";
import type { Operacoes } from "./operacoes.ts";
import { log, type Evento } from "./tipos.ts";

export const PING_MS = 15_000;

export type OpcoesHttp = {
  chat: Chat;
  canvas: Canvas;
  operacoes?: Operacoes;
  /** As definições dos componentes (/api/componentes). */
  componentes?: Componentes;
  webDir: string;
  /** Intervalo do `: ping` do SSE (testes podem encurtar). */
  pingMs?: number;
};

const SEM_CACHE = { "cache-control": "no-store" };

function json(dados: unknown, status = 200): Response {
  return Response.json(dados, { status, headers: SEM_CACHE });
}

function erro(status: number, mensagem: string): Response {
  return json({ erro: mensagem }, status);
}

async function lerJson(req: Request): Promise<unknown> {
  try {
    return await req.json();
  } catch {
    return undefined;
  }
}

function ehListaDeTextos(valor: unknown): valor is string[] {
  return Array.isArray(valor) && valor.every((v) => typeof v === "string");
}

function ehObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

export function criarRotas(opcoes: OpcoesHttp) {
  const { chat, canvas } = opcoes;
  const webDir = resolve(opcoes.webDir);
  const pingMs = opcoes.pingMs ?? PING_MS;
  /** Os SSE abertos, para fechar com calma ao encerrar. */
  const abertos = new Set<() => void>();

  /** Um arquivo de `raiz` (absoluta), sem sair dela. */
  async function servir(raiz: string, relativo: string): Promise<Response> {
    let caminho: string;
    try {
      caminho = decodeURIComponent(relativo);
    } catch {
      return erro(400, "caminho inválido");
    }
    if (caminho.includes("\0") || caminho.split(/[\\/]/).includes("..")) {
      return erro(400, "caminho inválido");
    }
    const absoluto = resolve(raiz, caminho);
    if (!absoluto.startsWith(raiz + sep)) return erro(400, "caminho inválido");
    const arquivo = Bun.file(absoluto);
    if (!(await arquivo.exists())) return erro(404, "não encontrado");
    return new Response(arquivo, { headers: SEM_CACHE });
  }

  const estatico = (relativo: string) => servir(webDir, relativo);

  function eventos(req: Request, servidor: Server<unknown>): Response {
    // O SSE fica aberto indefinidamente: sem o tempo ocioso do Bun.serve.
    servidor.timeout(req, 0);
    const codificador = new TextEncoder();
    let soltar = () => {};

    const corpo = new ReadableStream<Uint8Array>({
      start(controle) {
        let aberto = true;
        const escrever = (texto: string) => {
          if (!aberto) return;
          try {
            controle.enqueue(codificador.encode(texto));
          } catch {
            fechar();
          }
        };
        const enviar = (evento: string, dados: unknown) =>
          escrever(`event: ${evento}\ndata: ${JSON.stringify(dados)}\n\n`);

        const desassinar = chat.assinar((e: Evento) => enviar(e.tipo, e.dados));
        const ping = setInterval(() => escrever(": ping\n\n"), pingMs);
        const fechar = () => {
          if (!aberto) return;
          aberto = false;
          abertos.delete(fechar);
          clearInterval(ping);
          desassinar();
          try {
            controle.close();
          } catch {
            // já fechado
          }
        };
        soltar = fechar;
        abertos.add(fechar);
        req.signal.addEventListener("abort", fechar, { once: true });

        escrever("retry: 2000\n\n");
        enviar("ola", chat.estado());
      },
      cancel() {
        soltar();
      },
    });

    return new Response(corpo, {
      headers: {
        "content-type": "text/event-stream; charset=utf-8",
        "cache-control": "no-store",
        connection: "keep-alive",
        "x-accel-buffering": "no",
      },
    });
  }

  async function rota(req: Request, servidor: Server<unknown>): Promise<Response> {
    const url = new URL(req.url);
    const { pathname } = url;
    const metodo = req.method;

    try {
      if (pathname === "/" || pathname === "/index.html") {
        if (metodo !== "GET" && metodo !== "HEAD") return erro(405, "método não permitido");
        return estatico("index.html");
      }

      if (pathname.startsWith("/web/")) {
        if (metodo !== "GET" && metodo !== "HEAD") return erro(405, "método não permitido");
        return estatico(pathname.slice("/web/".length));
      }

      if (pathname === "/api/componentes") {
        if (metodo !== "GET") return erro(405, "método não permitido");
        return json({ componentes: opcoes.componentes?.todos() ?? [] });
      }

      if (pathname === "/api/estado") {
        if (metodo !== "GET") return erro(405, "método não permitido");
        return json(chat.estado());
      }

      if (pathname === "/api/mensagens") {
        if (metodo !== "POST") return erro(405, "método não permitido");
        const corpo = await lerJson(req);
        if (!ehObjeto(corpo)) return erro(400, "corpo precisa ser JSON { texto, selecao? }");
        const { texto, selecao } = corpo;
        if (typeof texto !== "string" || texto.trim() === "") return erro(400, "texto vazio");
        if (selecao !== undefined && !ehListaDeTextos(selecao)) {
          return erro(400, "selecao precisa ser uma lista de ids");
        }
        const mensagem = chat.receberDaPessoa(texto, selecao);
        return json({ mensagem }, 201);
      }

      if (pathname === "/api/eventos") {
        if (metodo !== "GET") return erro(405, "método não permitido");
        return eventos(req, servidor);
      }

      if (pathname === "/api/canvas") {
        if (metodo !== "GET") return erro(405, "método não permitido");
        return json({ registros: canvas.ler() });
      }

      if (pathname === "/api/canvas/diff") {
        if (metodo !== "POST") return erro(405, "método não permitido");
        const corpo = await lerJson(req);
        if (!ehObjeto(corpo)) return erro(400, "corpo precisa ser JSON { put?, remove? }");
        const { put, remove } = corpo;
        if (put !== undefined && !ehObjeto(put)) return erro(400, "put precisa ser um objeto id → registro");
        if (remove !== undefined && !ehListaDeTextos(remove)) return erro(400, "remove precisa ser uma lista de ids");
        canvas.aplicar({ put: put as Registros | undefined, remove });
        return new Response(null, { status: 204 });
      }

      if (pathname === "/api/canvas/resposta") {
        if (metodo !== "POST") return erro(405, "método não permitido");
        const corpo = await lerJson(req);
        if (!ehObjeto(corpo) || typeof corpo.pedido !== "string") return erro(400, "corpo precisa ser { pedido, ok, resultado?, erro? }");
        const achou = opcoes.operacoes?.responder(
          corpo.pedido,
          corpo.ok === true,
          corpo.resultado,
          typeof corpo.erro === "string" ? corpo.erro : undefined,
        );
        return achou ? new Response(null, { status: 204 }) : erro(404, "pedido desconhecido ou vencido");
      }

      return erro(404, "não encontrado");
    } catch (e) {
      log("erro na rota", metodo, pathname, e);
      return erro(500, "erro interno");
    }
  }

  /** Fecha os SSE abertos (o que já foi enfileirado sai antes). */
  function fecharEventos(): void {
    for (const fechar of [...abertos]) fechar();
  }

  return { rota, fecharEventos };
}
