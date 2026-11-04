import { afterEach, describe, expect, test } from "bun:test";
import { LeitorSSE, estado, ligarMcp, subirApp, textoDe } from "./ajuda.ts";

type Pedido = { pedido: string; op: Record<string, unknown> };

describe("atividade, apagar e operações do canvas", () => {
  const limpar: (() => Promise<void>)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  async function preparar(opcoes = {}) {
    const app = subirApp(opcoes);
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    limpar.push(fechar);
    return { app, client };
  }

  test("chat_atividade fica na conversa como atividade e vira o texto do digitando", async () => {
    const { app, client } = await preparar();
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");
    const r = await client.callTool({ name: "chat_atividade", arguments: { texto: "criando a tela Calendário" } });
    expect(r.isError).toBeFalsy();
    const m = await sse.evento<{ tipo?: string; texto: string }>("mensagem");
    expect(m).toMatchObject({ tipo: "atividade", texto: "criando a tela Calendário" });
    expect(await sse.evento<unknown>("digitando")).toEqual({ ativo: true, texto: "criando a tela Calendário" });
    const e = (await (await fetch(`${app.url}/api/estado`)).json()) as { atividade?: string };
    expect(e.atividade).toBe("criando a tela Calendário");
    await client.callTool({ name: "chat_responder", arguments: { texto: "pronto" } });
    expect(await sse.evento("digitando", (d: { ativo: boolean }) => !d.ativo)).toEqual({ ativo: false });
  });

  test("chat_apagar tira a mensagem, avisa a página e continua apagada depois de reiniciar", async () => {
    const { app, client } = await preparar();
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    const r = await client.callTool({ name: "chat_responder", arguments: { texto: "não consigo" } });
    const { mensagem } = JSON.parse(textoDe(r)) as { mensagem: { id: string } };
    const a = await client.callTool({ name: "chat_apagar", arguments: { id: mensagem.id } });
    expect(a.isError).toBeFalsy();
    expect(await sse.evento<unknown>("apagada")).toEqual({ id: mensagem.id });
    expect((await estado(app.url)).mensagens).toHaveLength(0);
    expect((await client.callTool({ name: "chat_apagar", arguments: { id: "nada" } })).isError).toBe(true);

    await app.chat.descarregar();
    const depois = subirApp({ dadosDir: app.dadosDir });
    limpar.push(depois.encerrar);
    expect(depois.chat.todas()).toHaveLength(0);
  });

  test("tela_criar vai à página pelo SSE e volta com o que a página respondeu", async () => {
    const { app, client } = await preparar();
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");

    const chamada = client.callTool({
      name: "tela_criar",
      arguments: { nome: "Calendário", html: "<p>oi</p>", largura: "celular" },
    });
    const p = await sse.evento<Pedido>("canvas");
    expect(p.op).toMatchObject({ tipo: "tela_criar", nome: "Calendário", html: "<p>oi</p>", w: 393, h: 852 });
    const resp = await fetch(`${app.url}/api/canvas/resposta`, {
      method: "POST",
      body: JSON.stringify({ pedido: p.pedido, ok: true, resultado: { id: "shape:abc" } }),
    });
    expect(resp.status).toBe(204);
    const r = await chamada;
    expect(r.isError).toBeFalsy();
    expect(JSON.parse(textoDe(r))).toEqual({ id: "shape:abc" });

    // a mesma resposta de novo: o pedido já não existe
    const de_novo = await fetch(`${app.url}/api/canvas/resposta`, {
      method: "POST",
      body: JSON.stringify({ pedido: p.pedido, ok: true }),
    });
    expect(de_novo.status).toBe(404);
  });

  test("o erro da página vira isError, e sem página aberta a ferramenta recusa na hora", async () => {
    const { app, client } = await preparar({ operacaoMs: 300 });
    const semPagina = await client.callTool({ name: "canvas_ler", arguments: {} });
    expect(semPagina.isError).toBe(true);
    expect(textoDe(semPagina)).toContain("web_abrir");

    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");
    const chamada = client.callTool({ name: "tela_mudar", arguments: { id: "shape:x", html: "<p/>" } });
    const p = await sse.evento<Pedido>("canvas");
    await fetch(`${app.url}/api/canvas/resposta`, {
      method: "POST",
      body: JSON.stringify({ pedido: p.pedido, ok: false, erro: "não achei a forma shape:x" }),
    });
    const r = await chamada;
    expect(r.isError).toBe(true);
    expect(textoDe(r)).toContain("não achei a forma");

    // a página não responde: vence o tempo limite
    const t0 = performance.now();
    const vencida = await client.callTool({ name: "canvas_apagar", arguments: { ids: ["shape:y"] } });
    expect(vencida.isError).toBeFalsy();
    expect(textoDe(vencida)).toContain("NÃO reenvie");
    expect(performance.now() - t0).toBeLessThan(2000);
  });
});
