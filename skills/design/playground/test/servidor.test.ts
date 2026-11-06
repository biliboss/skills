/**
 * O modo servidor por processo (`bun run src/main.ts --servidor`): só o HTTP
 * (a Web e o /mcp), sem stdio, até SIGTERM; e onde ele escuta.
 */
import { afterEach, describe, expect, test } from "bun:test";
import { connect } from "node:net";
import { networkInterfaces } from "node:os";
import { join } from "node:path";
import { FERRAMENTAS, RAIZ, ate, ligarHttp, pastaTemporaria, portaLivre } from "./ajuda.ts";

/** Um IPv4 desta máquina que não é loopback (a rede local ou a tailnet), ou null. */
function ipLocal(): string | null {
  for (const lista of Object.values(networkInterfaces())) {
    for (const i of lista ?? []) if (i.family === "IPv4" && !i.internal) return i.address;
  }
  return null;
}

/** Se dá para abrir uma conexão TCP em ip:porta. */
function aceita(ip: string, porta: number): Promise<boolean> {
  return new Promise((resolve) => {
    const s = connect({ host: ip, port: porta, timeout: 1000 }, () => {
      s.destroy();
      resolve(true);
    });
    s.on("error", () => resolve(false));
    s.on("timeout", () => {
      s.destroy();
      resolve(false);
    });
  });
}

describe("modo servidor (--servidor)", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  async function subir(extra: Record<string, string>) {
    const porta = await portaLivre();
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);
    const env: Record<string, string> = {};
    for (const [k, v] of Object.entries(process.env)) if (v !== undefined) env[k] = v;
    delete env.DP_TOKEN;
    const proc = Bun.spawn([process.execPath, "run", join(RAIZ, "src/main.ts"), "--servidor"], {
      cwd: RAIZ,
      env: { ...env, PORT: String(porta), ABRIR_WEB: "0", DADOS_DIR: pasta.dir, ...extra },
      stdin: "ignore",
      stdout: "pipe",
      stderr: "pipe",
    });
    limpar.push(() => {
      if (proc.exitCode === null) proc.kill("SIGKILL");
    });
    let stderr = "";
    void (async () => {
      const d = new TextDecoder();
      for await (const parte of proc.stderr) stderr += d.decode(parte, { stream: true });
    })();
    const url = `http://127.0.0.1:${porta}`;
    await ate(
      async () => {
        try {
          return (await fetch(`${url}/api/estado`)).status === 200;
        } catch {
          return false;
        }
      },
      8000,
      "o servidor subir",
    );
    return { proc, porta, url, stderr: () => stderr };
  }

  test("sobe sem stdio, responde /api/estado e /mcp, e encerra limpo no SIGTERM", async () => {
    const { proc, porta, url, stderr } = await subir({ DP_TAILNET: "0" });
    expect(await (await fetch(`${url}/api/estado`)).json()).toMatchObject({ motor: "sem-agente" });

    const { client, fechar } = await ligarHttp(url);
    limpar.push(fechar);
    expect((await client.listTools()).tools.map((t) => t.name).sort()).toEqual(FERRAMENTAS);
    expect((await client.callTool({ name: "chat_historico", arguments: {} })).isError).toBeFalsy();
    expect(await (await fetch(`${url}/api/estado`)).json()).toMatchObject({ motor: "ocupado" });

    // Sem stdio: o stdout fica vazio, e o log diz onde está o MCP.
    await ate(() => stderr().includes("modo servidor"), 3000, "o log do modo servidor");
    expect(stderr()).toContain(`${url}/mcp`);

    // Com uma sessão aberta, o SIGTERM encerra (código 0) e solta a porta.
    proc.kill("SIGTERM");
    const codigo = await Promise.race([proc.exited, Bun.sleep(5000).then(() => "travou" as const)]);
    expect(codigo).toBe(0);
    expect(await new Response(proc.stdout).text()).toBe("");
    expect(await aceita("127.0.0.1", porta)).toBe(false);
    expect(stderr()).toContain("encerrando: SIGTERM");
  }, 20_000);

  test("SIGINT também encerra", async () => {
    const { proc, porta } = await subir({ DP_TAILNET: "0" });
    proc.kill("SIGINT");
    expect(await Promise.race([proc.exited, Bun.sleep(5000).then(() => "travou" as const)])).toBe(0);
    expect(await aceita("127.0.0.1", porta)).toBe(false);
  }, 20_000);

  test("com DP_TAILNET=0, só escuta em 127.0.0.1", async () => {
    const { proc, porta, stderr } = await subir({ DP_TAILNET: "0", DP_TAILNET_IP: ipLocal() ?? "100.64.0.7" });
    expect(await aceita("127.0.0.1", porta)).toBe(true);
    const ip = ipLocal();
    if (ip) expect(await aceita(ip, porta)).toBe(false);
    expect(stderr()).toContain(`escutando em http://127.0.0.1:${porta} ·`);
    proc.kill("SIGTERM");
    await proc.exited;
  }, 20_000);

  test("com o IP da tailnet, escuta também nele, e a guarda aceita esse Host", async () => {
    const ip = ipLocal();
    if (!ip) {
      console.warn("sem IPv4 fora do loopback nesta máquina: teste pulado");
      return;
    }
    const { proc, porta, stderr } = await subir({ DP_TAILNET_IP: ip });
    expect(await aceita("127.0.0.1", porta)).toBe(true);
    expect(await aceita(ip, porta)).toBe(true);
    expect(stderr()).toContain(`escutando em http://127.0.0.1:${porta} e http://${ip}:${porta}`);

    const pelaTailnet = `http://${ip}:${porta}`;
    expect((await fetch(`${pelaTailnet}/api/estado`)).status).toBe(200);
    const { client, fechar } = await ligarHttp(pelaTailnet);
    limpar.push(fechar);
    expect((await client.listTools()).tools).toHaveLength(FERRAMENTAS.length);

    proc.kill("SIGTERM");
    expect(await proc.exited).toBe(0);
    expect(await aceita(ip, porta)).toBe(false);
  }, 20_000);

  test("com a porta em uso, o modo servidor sai com erro", async () => {
    const { proc, porta } = await subir({ DP_TAILNET: "0" });
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);
    const segundo = Bun.spawn([process.execPath, "run", join(RAIZ, "src/main.ts"), "--servidor"], {
      cwd: RAIZ,
      env: { ...process.env, PORT: String(porta), ABRIR_WEB: "0", DADOS_DIR: pasta.dir, DP_TAILNET: "0" },
      stdin: "ignore",
      stdout: "ignore",
      stderr: "pipe",
    });
    limpar.push(() => {
      if (segundo.exitCode === null) segundo.kill("SIGKILL");
    });
    expect(await Promise.race([segundo.exited, Bun.sleep(5000).then(() => "travou" as const)])).toBe(1);
    expect(await new Response(segundo.stderr).text()).toContain("já está em uso");
    proc.kill("SIGTERM");
    await proc.exited;
  }, 20_000);
});
