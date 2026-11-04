import { afterEach, describe, expect, test } from "bun:test";
import { FERRAMENTAS, estado, ligarMcp, pastaTemporaria, portaLivre, postar, subirApp, textoDe } from "./ajuda.ts";

describe("segunda sessão na mesma porta", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  test("o segundo app tem portaOcupada e toda ferramenta devolve isError com 'outra sessão'", async () => {
    const porta = await portaLivre();
    const primeiro = subirApp({ porta });
    limpar.push(primeiro.encerrar);
    expect(primeiro.portaOcupada).toBe(false);
    expect(primeiro.porta).toBe(porta);
    expect(primeiro.http).not.toBeNull();

    const segundo = subirApp({ porta });
    limpar.push(segundo.encerrar);
    expect(segundo.portaOcupada).toBe(true);
    expect(segundo.http).toBeNull();
    expect(segundo.url).toBe(`http://127.0.0.1:${porta}`);

    const { client, fechar } = await ligarMcp(segundo);
    limpar.push(fechar);
    // A lista ainda funciona (o MCP sobe); as chamadas é que recusam.
    expect((await client.listTools()).tools).toHaveLength(FERRAMENTAS.length);

    const chamadas: [string, Record<string, unknown>][] = [
      ["web_abrir", {}],
      ["chat_aguardar", { timeout_s: 30 }],
      ["chat_responder", { texto: "oi" }],
      ["chat_digitando", { ativo: true }],
      ["chat_historico", { limite: 5 }],
    ];
    for (const [name, args] of chamadas) {
      const inicio = performance.now();
      const r = await client.callTool({ name, arguments: args });
      expect({ name, isError: r.isError }).toEqual({ name, isError: true });
      expect(textoDe(r)).toContain("outra sessão");
      expect(textoDe(r)).toContain(segundo.url);
      expect(performance.now() - inicio).toBeLessThan(500); // chat_aguardar recusa na hora, sem esperar
    }

    // O primeiro segue sendo o motor e não viu nada do segundo.
    const m = await postar(primeiro.url, "só o primeiro");
    expect((await estado(primeiro.url)).mensagens.map((x) => x.id)).toEqual([m.id]);
    expect(primeiro.chat.digitando).toBe(false);
  });

  test("a porta volta a ficar livre depois de parar o primeiro", async () => {
    const porta = await portaLivre();
    const pasta = pastaTemporaria();
    limpar.push(pasta.apagar);
    const primeiro = subirApp({ porta, dadosDir: pasta.dir });
    await primeiro.parar();

    const depois = subirApp({ porta, dadosDir: pasta.dir });
    limpar.push(() => depois.parar());
    expect(depois.portaOcupada).toBe(false);
    expect((await fetch(`${depois.url}/api/estado`)).status).toBe(200);
  });
});
