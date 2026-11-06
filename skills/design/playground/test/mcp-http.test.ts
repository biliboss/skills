import { afterEach, describe, expect, test } from "bun:test";
import { criarGuarda, resolverTailnet } from "../src/mcp-http.ts";
import { FERRAMENTAS, ate, estado, ligarHttp, ligarMcp, mensagensDe, postar, rascunho, subirApp, textoDe } from "./ajuda.ts";

const INICIAR = {
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "cru", version: "0" } },
};

/** Um POST cru no /mcp, com os cabeçalhos pedidos. */
function postCru(url: string, headers: Record<string, string>, corpo: unknown = INICIAR): Promise<Response> {
  return fetch(`${url}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream", ...headers },
    body: JSON.stringify(corpo),
  });
}

describe("MCP por Streamable HTTP em /mcp", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  function app(opcoes: Parameters<typeof subirApp>[0] = {}) {
    const a = subirApp(opcoes);
    limpar.push(a.encerrar);
    return a;
  }

  test("lista as ferramentas, manda as instruções, e chat_aguardar acorda com um POST", async () => {
    const a = app();
    const { client, fechar } = await ligarHttp(a.url);
    limpar.push(fechar);
    expect(a.mcpHttp.sessoes).toBe(1);

    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(FERRAMENTAS);
    expect(client.getInstructions()).toContain("componente_definir");
    expect(client.getServerVersion()?.name).toBe("design-playground");
    await ate(() => a.chat.motor === "ocupado", 2000, "motor ocupado após o initialize");

    const inicio = performance.now();
    const espera = client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    await ate(async () => (await estado(a.url)).motor === "ouvindo", 2000, "motor ouvindo");
    const postada = await postar(a.url, "monta a busca", ["shape:x"]);
    expect(mensagensDe(await espera)).toEqual([postada]);
    expect(performance.now() - inicio).toBeLessThan(2000);

    const r = await client.callTool({ name: "chat_responder", arguments: { texto: "feito" } });
    expect(r.isError).toBeFalsy();
    expect((await estado(a.url)).mensagens.map((m) => m.texto)).toEqual(["monta a busca", "feito"]);
  });

  test("DELETE /mcp fecha a sessão; o id antigo leva 404", async () => {
    const a = app();
    const { client, transporte, fechar } = await ligarHttp(a.url);
    await client.callTool({ name: "chat_historico", arguments: {} });
    const id = transporte.sessionId!;
    expect(id).toBeString();
    await fechar();
    await ate(() => a.mcpHttp.sessoes === 0, 2000, "a sessão fechar");
    expect(a.chat.motor).toBe("sem-agente");
    const r = await fetch(`${a.url}/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": id },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" }),
    });
    expect(r.status).toBe(404);
    // Sem sessão e sem initialize: 400, e nada fica aberto.
    const semSessao = await postCru(a.url, {}, { jsonrpc: "2.0", id: 2, method: "tools/list" });
    expect(semSessao.status).toBe(400);
    expect((await fetch(`${a.url}/mcp`)).status).toBe(400);
    expect(a.mcpHttp.sessoes).toBe(0);
  });

  test("a guarda: Host e Origin de fora levam 403; os permitidos passam", async () => {
    const a = app({ tailnetIp: "100.64.0.7" });
    const porta = a.porta;
    for (const host of ["evil.com", `evil.com:${porta}`, "127.0.0.1.evil.com", "localhost.evil.com", "ts.net", "x.ts.net.evil.com", "[::1]", "0.0.0.0", "192.168.0.10"]) {
      const r = await postCru(a.url, { host });
      expect({ host, status: r.status }).toEqual({ host, status: 403 });
    }
    for (const origin of ["http://evil.com", "https://127.0.0.1.evil.com", "null", "file://x"]) {
      const r = await postCru(a.url, { origin });
      expect({ origin, status: r.status }).toEqual({ origin, status: 403 });
    }
    // A guarda é só do /mcp: a Web segue servida.
    expect((await fetch(`${a.url}/api/estado`, { headers: { host: "evil.com" } })).status).toBe(200);
    expect(a.mcpHttp.sessoes).toBe(0);

    const permitidos: Record<string, string>[] = [
      {},
      { host: `localhost:${porta}` },
      { host: "localhost" },
      { host: `100.64.0.7:${porta}` },
      { host: "mac.tail1234.ts.net" },
      { origin: `http://127.0.0.1:${porta}` },
      { origin: "https://mac.tail1234.ts.net" },
      { origin: `http://100.64.0.7:${porta}` },
    ];
    for (const headers of permitidos) {
      const r = await postCru(a.url, headers);
      expect({ headers, status: r.status }).toEqual({ headers, status: 200 });
      await r.body?.cancel();
    }
    await ate(() => a.mcpHttp.sessoes === permitidos.length, 2000, "as sessões abrirem");
  });

  test("com token, o /mcp exige Authorization: Bearer", async () => {
    const a = app({ token: "segredo-123" });
    expect((await postCru(a.url, {})).status).toBe(401);
    expect((await postCru(a.url, { authorization: "Bearer errado" })).status).toBe(401);
    expect((await postCru(a.url, { authorization: "segredo-123" })).status).toBe(401);
    expect(a.mcpHttp.sessoes).toBe(0);

    const { client, fechar } = await ligarHttp(a.url, { headers: { authorization: "Bearer segredo-123" } });
    limpar.push(fechar);
    expect((await client.listTools()).tools).toHaveLength(FERRAMENTAS.length);
    // A Web não pede token.
    expect((await fetch(`${a.url}/api/estado`)).status).toBe(200);
  });

  test("criarGuarda e resolverTailnet", () => {
    const g = criarGuarda({});
    const req = (headers: Record<string, string>) => new Request("http://127.0.0.1/mcp", { headers });
    expect(g.conferir(req({ host: "127.0.0.1:5317" }))).toBeNull();
    expect(g.conferir(req({ host: "100.64.0.7:5317" }))?.status).toBe(403); // sem tailnet configurada
    expect(g.conferir(req({ host: "Mac.Tail1234.TS.NET:5317" }))).toBeNull();

    expect(resolverTailnet({ DP_TAILNET: "0", DP_TAILNET_IP: "100.64.0.7" })).toBeNull();
    expect(resolverTailnet({ DP_TAILNET_IP: "100.64.0.7" })).toBe("100.64.0.7");
    expect(resolverTailnet({ DP_TAILNET_IP: "0.0.0.0" })).toBeNull();
    expect(resolverTailnet({ DP_TAILNET_IP: "127.0.0.1" })).toBeNull();
    expect(resolverTailnet({ DP_TAILNET_IP: "não é ip" })).toBeNull();
  });
});

describe("um motor por vez, entre transportes", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  test("o primeiro que chama vira o motor; o outro (em memória) é recusado até o HTTP fechar", async () => {
    const a = subirApp();
    limpar.push(a.encerrar);
    const http = await ligarHttp(a.url, { nome: "claude-http" });
    limpar.push(http.fechar);
    const memoria = await ligarMcp(a);
    limpar.push(memoria.fechar);

    // Conectar não toma a vez: só chamar uma ferramenta.
    expect(a.chat.donoDoMotor).toBeNull();
    expect((await http.client.callTool({ name: "chat_historico", arguments: {} })).isError).toBeFalsy();
    expect(a.chat.donoDoMotor).toBe("http (claude-http)");

    for (const [name, args] of [
      ["chat_historico", {}],
      ["chat_aguardar", { timeout_s: 30 }],
      ["componente_definir", { componente: rascunho() }],
    ] as const) {
      const inicio = performance.now();
      const r = await memoria.client.callTool({ name, arguments: args });
      expect({ name, erro: r.isError }).toEqual({ name, erro: true });
      expect(textoDe(r)).toContain("outra sessão já é o motor");
      expect(textoDe(r)).toContain("claude-http");
      expect(performance.now() - inicio).toBeLessThan(500);
    }
    expect(a.componentes.todos()).toEqual([]);
    // O motor segue funcionando.
    expect((await http.client.callTool({ name: "chat_responder", arguments: { texto: "sou eu" } })).isError).toBeFalsy();

    // O HTTP fecha a sessão: a vez fica livre, e o outro assume.
    await http.fechar();
    await ate(() => a.chat.donoDoMotor === null, 2000, "o motor soltar");
    const r = await memoria.client.callTool({ name: "chat_historico", arguments: {} });
    expect(r.isError).toBeFalsy();
    expect(a.chat.donoDoMotor).toBe("stdio (teste)");
  });

  test("o motor em memória recusa o HTTP; o estado segue o motor", async () => {
    const a = subirApp();
    limpar.push(a.encerrar);
    const memoria = await ligarMcp(a);
    limpar.push(memoria.fechar);
    const espera = memoria.client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    await ate(() => a.chat.motor === "ouvindo", 2000, "motor ouvindo");

    const http = await ligarHttp(a.url);
    limpar.push(http.fechar);
    const r = await http.client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    expect(r.isError).toBe(true);
    expect(textoDe(r)).toContain("outra sessão já é o motor (stdio (teste))");
    expect(a.chat.motor).toBe("ouvindo");

    await postar(a.url, "oi");
    expect(mensagensDe(await espera)).toHaveLength(1);
    expect(a.chat.motor).toBe("ocupado");

    // O motor em memória cai: o HTTP, conectado e ativo, deixa o estado em "ocupado"; ele assume ao chamar.
    await memoria.fechar();
    expect(a.chat.donoDoMotor).toBeNull();
    expect(a.chat.motor).toBe("ocupado");
    const espera2 = http.client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    await ate(() => a.chat.motor === "ouvindo", 2000, "o HTTP ouvindo");
    expect(a.chat.donoDoMotor).toBe("http (teste-http)");
    await postar(a.url, "agora o http");
    expect(mensagensDe(await espera2).map((m) => m.texto)).toEqual(["agora o http"]);
  });

  test("o motor HTTP solta a vez por ociosidade, mas não com um chat_aguardar pendente", async () => {
    const a = subirApp({ motorOciosoMs: 200 });
    limpar.push(a.encerrar);
    const http = await ligarHttp(a.url);
    limpar.push(http.fechar);
    const memoria = await ligarMcp(a);
    limpar.push(memoria.fechar);

    // Uma espera longa (mais que o tempo ocioso) segura a vez.
    const espera = http.client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    await ate(() => a.chat.motor === "ouvindo", 2000, "motor ouvindo");
    await Bun.sleep(500);
    expect(a.chat.donoDoMotor).toBe("http (teste-http)");
    expect((await memoria.client.callTool({ name: "chat_historico", arguments: {} })).isError).toBe(true);
    await postar(a.url, "acorda");
    await espera;

    // Sem chamar nada, passa o tempo ocioso: a vez fica livre e o estado vai a "sem-agente"
    // (o em memória, recusado há pouco, também ficou ocioso? não: sessão sem ociosoMs segue ativa).
    await ate(() => a.chat.donoDoMotor === null, 2000, "o motor HTTP soltar por ociosidade");
    expect(a.chat.motor).toBe("ocupado"); // o em memória segue conectado
    const r = await memoria.client.callTool({ name: "chat_historico", arguments: {} });
    expect(r.isError).toBeFalsy();
    expect(a.chat.donoDoMotor).toBe("stdio (teste)");

    // Agora quem é recusado é o HTTP.
    const recusado = await http.client.callTool({ name: "chat_historico", arguments: {} });
    expect(recusado.isError).toBe(true);
    expect(textoDe(recusado)).toContain("stdio (teste)");
  });

  test("só um HTTP ocioso: o estado volta a sem-agente", async () => {
    const a = subirApp({ motorOciosoMs: 150 });
    limpar.push(a.encerrar);
    const http = await ligarHttp(a.url);
    limpar.push(http.fechar);
    await http.client.callTool({ name: "chat_historico", arguments: {} });
    expect(a.chat.motor).toBe("ocupado");
    await ate(() => a.chat.motor === "sem-agente", 2000, "sem-agente por ociosidade");
    // Voltar a chamar retoma a vez.
    await http.client.callTool({ name: "chat_historico", arguments: {} });
    expect(a.chat.motor).toBe("ocupado");
    expect(a.chat.donoDoMotor).toBe("http (teste-http)");
  });
});

describe("cliente que sai sem DELETE", () => {
  test("o GET de notificações cai e a vaga de motor se solta em segundos, não pelo tempo ocioso", async () => {
    const app = subirApp({ adeusMs: 150, motorOciosoMs: 60_000 });
    try {
      const a = await ligarHttp(app.url, { nome: "a" });
      expect((await a.client.callTool({ name: "chat_historico", arguments: {} })).isError).toBeFalsy();
      const b = await ligarHttp(app.url, { nome: "b" });
      const recusa = await b.client.callTool({ name: "chat_historico", arguments: {} });
      expect(recusa.isError).toBe(true);
      // "a" some como um processo que acabou: fecha as conexões sem DELETE.
      await a.client.close();
      await Bun.sleep(600);
      const depois = await b.client.callTool({ name: "chat_historico", arguments: {} });
      expect(depois.isError).toBeFalsy();
      await b.fechar();
    } finally {
      await app.encerrar();
    }
  });
});
