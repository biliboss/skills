import { afterEach, describe, expect, test } from "bun:test";
import { LeitorSSE, ate, ligarMcp, postar, subirApp } from "./ajuda.ts";
import type { Mensagem } from "../src/tipos.ts";

type AppTeste = ReturnType<typeof subirApp>;

describe("SSE /api/eventos", () => {
  const limpar: (() => Promise<void>)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  async function preparar(opcoes: Parameters<typeof subirApp>[0] = {}): Promise<{ app: AppTeste; sse: LeitorSSE }> {
    const app = subirApp(opcoes);
    limpar.push(app.encerrar);
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    return { app, sse };
  }

  test("é text/event-stream e manda `ola` primeiro, com o estado atual", async () => {
    const app = subirApp();
    limpar.push(app.encerrar);
    const antes = await postar(app.url, "já estava aqui");

    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    expect(sse.status).toBe(200);
    expect(sse.tipo).toContain("text/event-stream");

    const ola = await sse.evento<{ motor: string; digitando: boolean; mensagens: Mensagem[] }>("ola");
    expect(sse.nomeados()[0]!.evento).toBe("ola");
    expect(ola.motor).toBe("sem-agente");
    expect(ola.digitando).toBe(false);
    expect(ola.mensagens.map((m) => m.id)).toEqual([antes.id]);
  });

  test("manda `mensagem` quando a pessoa posta", async () => {
    const { app, sse } = await preparar();
    await sse.evento("ola");
    const postada = await postar(app.url, "oi", ["shape:1"]);
    const recebida = await sse.evento<Mensagem>("mensagem");
    expect(recebida).toEqual(postada);
  });

  test("manda `motor` e `digitando` quando as ferramentas os mudam", async () => {
    const { app, sse } = await preparar();
    await sse.evento("ola");

    const { client, fechar } = await ligarMcp(app);
    expect(await sse.evento<{ estado: string }>("motor")).toEqual({ estado: "ocupado" });

    await client.callTool({ name: "chat_digitando", arguments: { ativo: true } });
    expect(await sse.evento<{ ativo: boolean }>("digitando")).toEqual({ ativo: true });
    await client.callTool({ name: "chat_digitando", arguments: { ativo: false } });
    expect(await sse.evento<{ ativo: boolean }>("digitando")).toEqual({ ativo: false });

    // chat_aguardar: ouvindo enquanto espera, ocupado quando volta.
    const espera = client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    expect(await sse.evento<{ estado: string }>("motor")).toEqual({ estado: "ouvindo" });
    await postar(app.url, "acorda");
    await espera;
    expect(await sse.evento<{ estado: string }>("motor")).toEqual({ estado: "ocupado" });

    // chat_responder esconde o digitando.
    await client.callTool({ name: "chat_digitando", arguments: { ativo: true } });
    await sse.evento("digitando", (d: { ativo: boolean }) => d.ativo);
    await client.callTool({ name: "chat_responder", arguments: { texto: "pronto" } });
    expect(await sse.evento<{ ativo: boolean }>("digitando")).toEqual({ ativo: false });

    // Fechar o transporte volta a "sem-agente".
    await fechar();
    expect(await sse.evento<{ estado: string }>("motor")).toEqual({ estado: "sem-agente" });
  });

  test("manda `: ping` no intervalo pingMs", async () => {
    const { sse } = await preparar({ pingMs: 40 });
    await sse.evento("ola");
    await sse.esperar((e) => "comentario" in e && e.comentario === "ping", 1000);
    await sse.esperar((e) => "comentario" in e && e.comentario === "ping", 1000);
    expect(sse.eventos.filter((e) => "comentario" in e).length).toBeGreaterThanOrEqual(2);
  });

  test("vários leitores recebem o mesmo evento; um leitor fechado sai dos assinantes", async () => {
    const { app, sse } = await preparar();
    const outro = await LeitorSSE.abrir(app.url);
    await sse.evento("ola");
    await outro.evento("ola");
    const assinantes = () => (app.chat as unknown as { assinantes: Set<unknown> }).assinantes.size;
    expect(assinantes()).toBe(2);
    await outro.fechar();
    await ate(() => assinantes() === 1, 2000, "o leitor fechado sair dos assinantes");

    const m = await postar(app.url, "para todos");
    expect((await sse.evento<Mensagem>("mensagem")).id).toBe(m.id);
    // O servidor não quebra por escrever num leitor que foi embora.
    expect((await fetch(`${app.url}/api/estado`)).status).toBe(200);
  });

  test("parar o app fecha o stream", async () => {
    const app = subirApp();
    const sse = await LeitorSSE.abrir(app.url);
    await sse.evento("ola");
    await app.encerrar();
    // Sem abortar do lado do cliente: quem fecha é o servidor.
    let fechou = false;
    void sse.terminou().then(() => (fechou = true));
    await ate(() => fechou, 2000, "o servidor fechar o SSE");
    await sse.fechar();
  });
});
