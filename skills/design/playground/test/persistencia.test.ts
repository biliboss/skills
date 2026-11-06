import { afterEach, describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Mensagem } from "../src/tipos.ts";
import { estado, ligarMcp, mensagensDe, pastaTemporaria, postar, subirApp, textoDe } from "./ajuda.ts";

describe("persistência em dadosDir", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  test("o histórico volta depois de reiniciar e só a não entregue fica pendente", async () => {
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);

    // Primeira vida: duas mensagens da pessoa, uma entregue, uma resposta.
    const app1 = subirApp({ dadosDir: pasta.dir });
    const mcp1 = await ligarMcp(app1);
    const entregue = await postar(app1.url, "primeira", ["shape:a"]);
    expect(mensagensDe(await mcp1.client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 5 } }))).toHaveLength(1);
    const r = await mcp1.client.callTool({ name: "chat_responder", arguments: { texto: "ok, primeira" } });
    const resposta = (JSON.parse(textoDe(r)) as { mensagem: Mensagem }).mensagem;
    const pendente = await postar(app1.url, "segunda");
    const historico1 = (await estado(app1.url)).mensagens;
    await mcp1.fechar();
    await app1.parar();

    expect(existsSync(join(pasta.dir, "conversa.jsonl"))).toBe(true);
    // Cada linha é JSON.
    for (const linha of readFileSync(join(pasta.dir, "conversa.jsonl"), "utf8").split("\n").filter(Boolean)) {
      expect(() => JSON.parse(linha)).not.toThrow();
    }

    // Segunda vida, na mesma pasta.
    const app2 = subirApp({ dadosDir: pasta.dir });
    limpar.push(() => app2.parar());
    const e = await estado(app2.url);
    expect(e.mensagens).toEqual(historico1);
    expect(e.mensagens.map((m) => m.id)).toEqual([entregue.id, resposta.id, pendente.id]);
    expect(e.mensagens[0]!.selecao).toEqual(["shape:a"]);
    expect(app2.chat.naoEntregues().map((m) => m.id)).toEqual([pendente.id]);

    // Pelo MCP: chat_aguardar volta na hora só com a pendente.
    const mcp2 = await ligarMcp(app2);
    limpar.push(mcp2.fechar);
    const inicio = performance.now();
    const mensagens = mensagensDe(await mcp2.client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } }));
    expect(performance.now() - inicio).toBeLessThan(500);
    expect(mensagens.map((m) => m.id)).toEqual([pendente.id]);

    // E a entrega também persiste numa terceira vida.
    await mcp2.fechar();
    await app2.parar();
    const app3 = subirApp({ dadosDir: pasta.dir });
    limpar.push(() => app3.parar());
    expect(app3.chat.naoEntregues()).toEqual([]);
    expect((await estado(app3.url)).mensagens).toHaveLength(3);
  });

  test("o canvas sobrevive a reiniciar", async () => {
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);

    const app1 = subirApp({ dadosDir: pasta.dir });
    const registros = { "shape:a": { id: "shape:a", typeName: "shape", x: 3 } };
    const r = await fetch(`${app1.url}/api/canvas/diff`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ put: registros }),
    });
    expect(r.status).toBe(204);
    await app1.parar();

    const app2 = subirApp({ dadosDir: pasta.dir });
    limpar.push(() => app2.parar());
    expect(await (await fetch(`${app2.url}/api/canvas`)).json()).toEqual({ registros });
  });

  test("linhas estragadas no conversa.jsonl são ignoradas sem derrubar o app", async () => {
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);
    const app1 = subirApp({ dadosDir: pasta.dir });
    const m = await postar(app1.url, "boa");
    await app1.parar();

    const arquivo = join(pasta.dir, "conversa.jsonl");
    await Bun.write(arquivo, readFileSync(arquivo, "utf8") + "{quebrada\n" + JSON.stringify({ x: 1 }) + "\n");

    const app2 = subirApp({ dadosDir: pasta.dir });
    limpar.push(() => app2.parar());
    expect((await estado(app2.url)).mensagens.map((x) => x.id)).toEqual([m.id]);
  });
});
