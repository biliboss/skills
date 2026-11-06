/**
 * Ponta a ponta: o processo de verdade (`bun run src/main.ts`), com o MCP no
 * stdio e a Web numa porta livre.
 */
import { FERRAMENTAS } from "./ajuda.ts";
import { afterEach, describe, expect, test } from "bun:test";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import type { Mensagem } from "../src/tipos.ts";
import { RAIZ, ate, estado, mensagensDe, pastaTemporaria, portaLivre, postar, textoDe } from "./ajuda.ts";

function ambiente(porta: number, dadosDir: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [k, v] of Object.entries(process.env)) if (v !== undefined) env[k] = v;
  return { ...env, PORT: String(porta), ABRIR_WEB: "0", DADOS_DIR: dadosDir, DP_TAILNET: "0" };
}

function vivo(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function portaFechada(porta: number): Promise<boolean> {
  try {
    await fetch(`http://127.0.0.1:${porta}/api/estado`, { signal: AbortSignal.timeout(500) });
    return false;
  } catch {
    return true;
  }
}

describe("ponta a ponta por stdio", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  test("lista as ferramentas, chat_aguardar acorda com um POST, responde, e encerra limpo", async () => {
    const porta = await portaLivre();
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);
    const url = `http://127.0.0.1:${porta}`;

    const transporte = new StdioClientTransport({
      command: process.execPath,
      args: ["run", join(RAIZ, "src/main.ts")],
      cwd: RAIZ,
      env: ambiente(porta, pasta.dir),
      stderr: "pipe",
    });
    let stderr = "";
    transporte.stderr?.on("data", (d: Buffer) => (stderr += d.toString()));

    // Qualquer linha no stdout que não seja JSON-RPC vira erro do transporte.
    const erros: Error[] = [];
    const client = new Client({ name: "teste-stdio", version: "0.0.0" });
    client.onerror = (e) => erros.push(e);
    let fechado = false;
    limpar.push(async () => {
      if (!fechado) await client.close();
    });

    await client.connect(transporte);
    const pid = transporte.pid!;
    expect(pid).toBeNumber();

    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(FERRAMENTAS);

    // A Web está no ar na porta pedida, com o motor ocupado (initialize feito).
    await ate(async () => (await estado(url)).motor === "ocupado", 3000, "motor ocupado");

    // chat_aguardar enquanto um fetch posta.
    const inicio = performance.now();
    const espera = client.callTool({ name: "chat_aguardar", arguments: { timeout_s: 30 } });
    await ate(async () => (await estado(url)).motor === "ouvindo", 3000, "motor ouvindo");
    const postada = await postar(url, "desenha uma tela de login", ["shape:x"]);
    const mensagens = mensagensDe(await espera);
    expect(performance.now() - inicio).toBeLessThan(5000);
    expect(mensagens).toEqual([postada]);

    // E responde.
    const r = await client.callTool({ name: "chat_responder", arguments: { texto: "Feito: **login**." } });
    expect(r.isError).toBeFalsy();
    const resposta = (JSON.parse(textoDe(r)) as { mensagem: Mensagem }).mensagem;
    const e = await estado(url);
    expect(e.mensagens.map((m) => [m.autor, m.texto])).toEqual([
      ["pessoa", "desenha uma tela de login"],
      ["agente", "Feito: **login**."],
    ]);
    expect(e.mensagens[1]!.id).toBe(resposta.id);

    const web = await client.callTool({ name: "web_abrir", arguments: {} });
    expect(textoDe(web)).toContain(url);

    // O stdout só teve MCP: nenhum erro de parse no cliente.
    expect(erros).toEqual([]);
    // O log foi para o stderr.
    expect(stderr).toContain("[design-playground]");

    // Encerrar: fechar o cliente fecha o stdin; o processo sai e solta a porta.
    await client.close();
    fechado = true;
    await ate(() => !vivo(pid), 5000, "o processo sair");
    await ate(() => portaFechada(porta), 3000, "a porta ser solta");
  }, 20_000);

  test("o stdout cru só tem linhas JSON-RPC, e fechar o stdin encerra o processo", async () => {
    const porta = await portaLivre();
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);

    const proc = Bun.spawn([process.execPath, "run", join(RAIZ, "src/main.ts")], {
      cwd: RAIZ,
      env: ambiente(porta, pasta.dir),
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    });
    limpar.push(() => {
      if (proc.exitCode === null) proc.kill("SIGKILL");
    });

    const enviar = (msg: unknown) => {
      proc.stdin.write(JSON.stringify(msg) + "\n");
      proc.stdin.flush();
    };
    enviar({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "cru", version: "0" } },
    });
    enviar({ jsonrpc: "2.0", method: "notifications/initialized" });
    enviar({ jsonrpc: "2.0", id: 2, method: "tools/list" });
    enviar({ jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "chat_historico", arguments: {} } });

    // Lê o stdout até ter as 3 respostas.
    const leitor = proc.stdout.getReader();
    const decodificador = new TextDecoder();
    let saida = "";
    const respostas = new Map<number, Record<string, unknown>>();
    const prazo = Date.now() + 10_000;
    while (respostas.size < 3 && Date.now() < prazo) {
      const { value, done } = await leitor.read();
      if (done) break;
      saida += decodificador.decode(value, { stream: true });
      for (const linha of saida.split("\n").slice(0, -1)) {
        const msg = JSON.parse(linha) as Record<string, unknown>;
        if (typeof msg.id === "number") respostas.set(msg.id, msg);
      }
    }
    expect([...respostas.keys()].sort()).toEqual([1, 2, 3]);

    // Fecha o stdin: o processo tem que sair sozinho, sem sinal.
    proc.stdin.end();
    const codigo = await Promise.race([proc.exited, Bun.sleep(5000).then(() => "travou" as const)]);
    expect(codigo).toBe(0);

    // O resto do stdout, até o fim.
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      saida += decodificador.decode(value, { stream: true });
    }
    const linhas = saida.split("\n").filter((l) => l.length > 0);
    expect(linhas.length).toBeGreaterThanOrEqual(3);
    for (const linha of linhas) {
      const msg = JSON.parse(linha) as { jsonrpc?: string };
      expect(msg.jsonrpc).toBe("2.0");
    }

    const r1 = respostas.get(1)!.result as { serverInfo: { name: string }; instructions?: string };
    expect(r1.serverInfo.name).toBe("design-playground");
    expect(r1.instructions).toContain("chat_aguardar");
    const r2 = respostas.get(2)!.result as { tools: { name: string }[] };
    expect(r2.tools).toHaveLength(FERRAMENTAS.length);

    expect(await new Response(proc.stderr).text()).toContain("[design-playground]");
    expect(await portaFechada(porta)).toBe(true);
  }, 20_000);
});
