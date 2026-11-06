import { FERRAMENTAS } from "./ajuda.ts";
import { afterEach, describe, expect, test } from "bun:test";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import type { Mensagem } from "../src/tipos.ts";
import { LeitorSSE, estado, ligarMcp, mensagensDe, postar, subirApp, textoDe } from "./ajuda.ts";

type AppTeste = ReturnType<typeof subirApp>;

describe("ferramentas do MCP", () => {
  const limpar: (() => Promise<void>)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  async function preparar(): Promise<{ app: AppTeste; client: Client }> {
    const app = subirApp();
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    limpar.push(fechar);
    return { app, client };
  }

  test("lista as ferramentas e manda as instruções no initialize", async () => {
    const { client } = await preparar();
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(FERRAMENTAS);
    for (const t of tools) expect(t.description?.length ?? 0).toBeGreaterThan(20);
    const instrucoes = client.getInstructions() ?? "";
    expect(instrucoes).toContain("chat_aguardar");
    expect(instrucoes).toContain("chat_responder");
    expect(client.getServerVersion()?.name).toBe("design-playground");
  });

  test("web_abrir devolve a URL e não abre navegador com abrirWeb false", async () => {
    const { app, client } = await preparar();
    const r = await client.callTool({ name: "web_abrir", arguments: {} });
    expect(r.isError).toBeFalsy();
    expect(textoDe(r)).toContain(app.url);
    expect(textoDe(r)).toContain("não abri o navegador");
  });

  test("chat_responder aparece no SSE e no /api/estado com autor agente", async () => {
    const { app, client } = await preparar();
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");

    const r = await client.callTool({ name: "chat_responder", arguments: { texto: "**feito**: um botão" } });
    expect(r.isError).toBeFalsy();
    const { mensagem } = JSON.parse(textoDe(r)) as { mensagem: Mensagem };
    expect(mensagem.autor).toBe("agente");
    expect(mensagem.texto).toBe("**feito**: um botão");

    const doSse = await sse.evento<Mensagem>("mensagem");
    expect(doSse).toEqual(mensagem);

    const e = await estado(app.url);
    expect(e.mensagens).toEqual([mensagem]);
    expect(e.mensagens[0]!.autor).toBe("agente");
  });

  test("chat_responder com texto vazio é erro e não publica", async () => {
    const { app, client } = await preparar();
    const r = await client.callTool({ name: "chat_responder", arguments: { texto: "  " } });
    expect(r.isError).toBe(true);
    expect((await estado(app.url)).mensagens).toEqual([]);
  });

  test("chat_historico respeita o limite, da mais antiga para a mais nova, com os dois autores", async () => {
    const { app, client } = await preparar();
    const ids: string[] = [];
    for (let i = 1; i <= 4; i++) {
      ids.push((await postar(app.url, `pessoa ${i}`)).id);
      const r = await client.callTool({ name: "chat_responder", arguments: { texto: `agente ${i}` } });
      ids.push((JSON.parse(textoDe(r)) as { mensagem: Mensagem }).mensagem.id);
    }

    const tres = mensagensDe(await client.callTool({ name: "chat_historico", arguments: { limite: 3 } }));
    expect(tres.map((m) => m.id)).toEqual(ids.slice(-3));
    expect(tres.map((m) => m.texto)).toEqual(["agente 3", "pessoa 4", "agente 4"]);

    const todas = mensagensDe(await client.callTool({ name: "chat_historico", arguments: {} }));
    expect(todas.map((m) => m.id)).toEqual(ids);

    const mais = mensagensDe(await client.callTool({ name: "chat_historico", arguments: { limite: 100 } }));
    expect(mais).toHaveLength(8);

    // chat_historico não marca nada como entregue.
    expect(app.chat.naoEntregues()).toHaveLength(4);
  });

  test("chat_historico usa 50 por padrão", async () => {
    const { app, client } = await preparar();
    for (let i = 0; i < 55; i++) app.chat.receberDaPessoa(`m${i}`);
    const padrao = mensagensDe(await client.callTool({ name: "chat_historico", arguments: {} }));
    expect(padrao).toHaveLength(50);
    expect(padrao[0]!.texto).toBe("m5");
    expect(padrao[49]!.texto).toBe("m54");
  });

  test("chat_historico recusa limite inválido", async () => {
    const { client } = await preparar();
    for (const limite of [0, -1, 1.5]) {
      let recusou = false;
      try {
        const r = await client.callTool({ name: "chat_historico", arguments: { limite } });
        recusou = r.isError === true;
      } catch {
        recusou = true;
      }
      expect({ limite, recusou }).toEqual({ limite, recusou: true });
    }
  });

  test("chat_digitando muda o estado; chat_aguardar e chat_responder o escondem", async () => {
    const { app, client } = await preparar();
    expect((await estado(app.url)).digitando).toBe(false);

    await client.callTool({ name: "chat_digitando", arguments: { ativo: true } });
    expect((await estado(app.url)).digitando).toBe(true);
    expect(app.chat.digitando).toBe(true);

    await client.callTool({ name: "chat_digitando", arguments: { ativo: false } });
    expect((await estado(app.url)).digitando).toBe(false);

    await client.callTool({ name: "chat_digitando", arguments: { ativo: true } });
    await client.callTool({ name: "chat_responder", arguments: { texto: "ok" } });
    expect((await estado(app.url)).digitando).toBe(false);

    await client.callTool({ name: "chat_digitando", arguments: { ativo: true } });
    await postar(app.url, "pendente");
    await client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 5 } });
    expect((await estado(app.url)).digitando).toBe(false);
  });

  test("fechar o transporte com o digitando ligado o desliga", async () => {
    const app = subirApp();
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    await client.callTool({ name: "chat_digitando", arguments: { ativo: true } });
    expect(app.chat.digitando).toBe(true);
    await fechar();
    expect(app.chat.digitando).toBe(false);
    expect(app.chat.motor).toBe("sem-agente");
  });
});
