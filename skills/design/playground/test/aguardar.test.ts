import { afterEach, describe, expect, test } from "bun:test";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import type { Progress } from "@modelcontextprotocol/sdk/types.js";
import { ate, estado, ligarMcp, mensagensDe, postar, subirApp } from "./ajuda.ts";

type AppTeste = ReturnType<typeof subirApp>;

describe("chat_aguardar (espera longa pelo MCP)", () => {
  const limpar: (() => Promise<void>)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  async function preparar(opcoes: Parameters<typeof subirApp>[0] = {}): Promise<{ app: AppTeste; client: Client }> {
    const app = subirApp(opcoes);
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    limpar.push(fechar);
    return { app, client };
  }

  const aguardar = (client: Client, timeout_s: number, onprogress?: (p: Progress) => void) =>
    client.callTool({ name: "chat_aguardar", arguments: { timeout_s } }, undefined, onprogress ? { onprogress } : undefined);

  test("sem mensagem, volta {mensagens: []} quando timeout_s acaba", async () => {
    const { client } = await preparar();
    const inicio = performance.now();
    const r = await aguardar(client, 1);
    const ms = performance.now() - inicio;
    expect(r.isError).toBeFalsy();
    expect(JSON.parse((r.content as { text: string }[])[0]!.text)).toEqual({ mensagens: [] });
    expect(ms).toBeGreaterThanOrEqual(950);
    expect(ms).toBeLessThan(2000);
  });

  test("uma mensagem postada durante a espera a acorda na hora, com a selecao", async () => {
    const { app, client } = await preparar();
    const inicio = performance.now();
    const espera = aguardar(client, 30);
    await ate(() => app.chat.esperando === 1, 2000, "a espera começar");
    const postada = await postar(app.url, "muda isso", ["shape:a", "shape:b"]);
    const mensagens = mensagensDe(await espera);
    const ms = performance.now() - inicio;

    expect(ms).toBeLessThan(1000); // o timeout era 30 s
    expect(mensagens).toEqual([postada]);
    expect(mensagens[0]!.selecao).toEqual(["shape:a", "shape:b"]);
    expect(mensagens[0]!.autor).toBe("pessoa");
  });

  test("mensagens postadas antes voltam na hora, todas juntas", async () => {
    const { app, client } = await preparar();
    const a = await postar(app.url, "um");
    const b = await postar(app.url, "dois");
    const inicio = performance.now();
    const mensagens = mensagensDe(await aguardar(client, 30));
    expect(performance.now() - inicio).toBeLessThan(500);
    expect(mensagens.map((m) => m.id)).toEqual([a.id, b.id]);
  });

  test("mensagens já entregues não voltam; as do agente nunca voltam", async () => {
    const { app, client } = await preparar();
    const a = await postar(app.url, "primeira");
    expect(mensagensDe(await aguardar(client, 30)).map((m) => m.id)).toEqual([a.id]);

    await client.callTool({ name: "chat_responder", arguments: { texto: "resposta" } });
    // Só a resposta do agente é nova: a espera não volta com ela, nem com a já entregue.
    expect(mensagensDe(await aguardar(client, 1))).toEqual([]);

    const b = await postar(app.url, "segunda");
    expect(mensagensDe(await aguardar(client, 30)).map((m) => m.id)).toEqual([b.id]);
    expect(app.chat.naoEntregues()).toEqual([]);
  });

  test("manda notifications/progress quando o cliente passa onprogress", async () => {
    const { app, client } = await preparar({ progressoMs: 50 });
    const avisos: Progress[] = [];
    const espera = aguardar(client, 30, (p) => avisos.push(p));
    await ate(() => avisos.length >= 3, 2000, "3 avisos de progresso");
    await postar(app.url, "pronto");
    const mensagens = mensagensDe(await espera);
    expect(mensagens).toHaveLength(1);
    expect(avisos.map((p) => p.progress)).toEqual(avisos.map((_, i) => i + 1));
    expect(avisos[0]!.message).toBeString();

    // Depois de voltar, o intervalo foi limpo: não chega mais nada.
    const quantos = avisos.length;
    await Bun.sleep(200);
    expect(avisos.length).toBe(quantos);
  });

  test("o progresso reinicia o tempo limite do cliente (resetTimeoutOnProgress)", async () => {
    const { app, client } = await preparar({ progressoMs: 50 });
    const avisos: Progress[] = [];
    // Tempo limite do cliente de 300 ms, mas a espera dura ~600 ms: só passa se o progresso reinicia o prazo.
    const espera = client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } }, undefined, {
      timeout: 300,
      resetTimeoutOnProgress: true,
      onprogress: (p) => avisos.push(p),
    });
    await Bun.sleep(600);
    await postar(app.url, "ainda aqui");
    expect(mensagensDe(await espera)).toHaveLength(1);
    expect(avisos.length).toBeGreaterThanOrEqual(5);
  });

  test("o motor fica ouvindo durante a espera e ocupado depois", async () => {
    const app = subirApp();
    limpar.push(app.encerrar);
    expect(app.chat.motor).toBe("sem-agente");
    expect((await estado(app.url)).motor).toBe("sem-agente");

    const { client, fechar } = await ligarMcp(app);
    await ate(() => app.chat.motor === "ocupado", 2000, "motor ocupado após o initialize");
    expect((await estado(app.url)).motor).toBe("ocupado");

    const espera = aguardar(client, 30);
    await ate(() => app.chat.motor === "ouvindo", 2000, "motor ouvindo");
    expect((await estado(app.url)).motor).toBe("ouvindo");

    await postar(app.url, "oi");
    await espera;
    expect(app.chat.motor).toBe("ocupado");
    expect((await estado(app.url)).motor).toBe("ocupado");

    // Também volta a ocupado quando a espera acaba no timeout.
    const vazia = aguardar(client, 1);
    await ate(() => app.chat.motor === "ouvindo", 2000, "motor ouvindo de novo");
    await vazia;
    expect(app.chat.motor).toBe("ocupado");

    await fechar();
    await ate(() => app.chat.motor === "sem-agente", 2000, "motor sem-agente após fechar");
  });

  test("o cliente cancelar a chamada solta a espera", async () => {
    const { app, client } = await preparar();
    const controle = new AbortController();
    const espera = client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } }, undefined, {
      signal: controle.signal,
    });
    await ate(() => app.chat.esperando === 1, 2000, "a espera começar");
    controle.abort();
    await expect(espera).rejects.toThrow();
    await ate(() => app.chat.esperando === 0, 2000, "a espera sair do servidor");
    expect(app.chat.motor).toBe("ocupado");

    // A mensagem seguinte não se perde numa espera cancelada.
    const m = await postar(app.url, "depois do cancelamento");
    expect(mensagensDe(await aguardar(client, 30)).map((x) => x.id)).toEqual([m.id]);
  });

  test("o agente cair durante a espera não engole a próxima mensagem", async () => {
    const app = subirApp();
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    const espera = client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } }).catch(() => "caiu");
    await ate(() => app.chat.esperando === 1, 2000, "a espera começar");
    await fechar();
    expect(await espera).toBe("caiu");
    await ate(() => app.chat.esperando === 0, 2000, "a espera sair do servidor");
    expect(app.chat.motor).toBe("sem-agente");

    // A mensagem fica pendente para o próximo agente.
    const m = await postar(app.url, "ninguém ouvindo");
    expect(app.chat.naoEntregues().map((x) => x.id)).toEqual([m.id]);
    const outro = await ligarMcp(app);
    limpar.push(outro.fechar);
    expect(mensagensDe(await aguardar(outro.client, 30)).map((x) => x.id)).toEqual([m.id]);
  });

  test("parar o app solta a espera com []", async () => {
    const app = subirApp();
    const { client, fechar } = await ligarMcp(app);
    const espera = aguardar(client, 30);
    await ate(() => app.chat.esperando === 1, 2000, "a espera começar");
    const inicio = performance.now();
    await app.encerrar();
    expect(mensagensDe(await espera)).toEqual([]);
    expect(performance.now() - inicio).toBeLessThan(1000);
    await fechar();
  });
});
