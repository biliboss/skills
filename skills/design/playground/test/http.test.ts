import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { connect } from "node:net";
import { ate, estado, pastaTemporaria, postar, subirApp } from "./ajuda.ts";

type AppTeste = ReturnType<typeof subirApp>;

/** Manda uma requisição crua, sem a normalização de `..` que o fetch/URL faz. */
function requisicaoCrua(porta: number, caminho: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const sock = connect(porta, "127.0.0.1", () => {
      sock.write(`GET ${caminho} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n`);
    });
    let resposta = "";
    sock.on("data", (d) => (resposta += d.toString()));
    sock.on("end", () => {
      const m = /^HTTP\/1\.1 (\d{3})/.exec(resposta);
      if (m) resolve(Number(m[1]));
      else reject(new Error("resposta sem status: " + resposta.slice(0, 200)));
    });
    sock.on("error", reject);
  });
}

describe("HTTP", () => {
  let app: AppTeste;
  let webTmp: ReturnType<typeof pastaTemporaria>;

  beforeEach(() => {
    // Uma web/ própria, com um segredo ao lado para tentar alcançar por `..`.
    webTmp = pastaTemporaria();
    mkdirSync(join(webTmp.dir, "web", "sub"), { recursive: true });
    writeFileSync(join(webTmp.dir, "web", "index.html"), "<h1>oi</h1>");
    writeFileSync(join(webTmp.dir, "web", "x.css"), "body{}");
    writeFileSync(join(webTmp.dir, "web", "sub", "y.js"), "export {}");
    writeFileSync(join(webTmp.dir, "segredo.txt"), "não pode sair");
    app = subirApp({ webDir: join(webTmp.dir, "web") });
  });

  afterEach(async () => {
    await app.encerrar();
    webTmp.apagar();
  });

  test("POST /api/mensagens devolve 201 com a mensagem", async () => {
    const r = await fetch(`${app.url}/api/mensagens`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ texto: "faz um botão", selecao: ["shape:a", "shape:b"] }),
    });
    expect(r.status).toBe(201);
    const { mensagem } = (await r.json()) as { mensagem: Record<string, unknown> };
    expect(mensagem.autor).toBe("pessoa");
    expect(mensagem.texto).toBe("faz um botão");
    expect(mensagem.selecao).toEqual(["shape:a", "shape:b"]);
    expect(typeof mensagem.id).toBe("string");
    expect(new Date(mensagem.em as string).toISOString()).toBe(mensagem.em as string);
  });

  test("POST /api/mensagens recusa texto vazio, em branco, sem texto e corpo inválido com 400", async () => {
    const enviar = (body: string) =>
      fetch(`${app.url}/api/mensagens`, { method: "POST", headers: { "content-type": "application/json" }, body });
    expect((await enviar(JSON.stringify({ texto: "" }))).status).toBe(400);
    expect((await enviar(JSON.stringify({ texto: "   \n " }))).status).toBe(400);
    expect((await enviar(JSON.stringify({}))).status).toBe(400);
    expect((await enviar(JSON.stringify({ texto: 3 }))).status).toBe(400);
    expect((await enviar("não é json")).status).toBe(400);
    expect((await enviar(JSON.stringify({ texto: "ok", selecao: [1] }))).status).toBe(400);
    // Nada disso entrou na conversa.
    expect((await estado(app.url)).mensagens).toEqual([]);
  });

  test("GET /api/estado traz motor, digitando e as mensagens na ordem", async () => {
    const vazio = await estado(app.url);
    expect(vazio).toEqual({ motor: "sem-agente", digitando: false, mensagens: [] });

    const a = await postar(app.url, "um");
    const b = await postar(app.url, "dois", ["shape:x"]);
    const e = await estado(app.url);
    expect(e.mensagens.map((m) => m.id)).toEqual([a.id, b.id]);
    expect(e.mensagens[1]!.selecao).toEqual(["shape:x"]);
  });

  test("estáticos: / e /web/<arquivo> devolvem 200 quando existem, 404 quando não", async () => {
    const raiz = await fetch(`${app.url}/`);
    expect(raiz.status).toBe(200);
    expect(await raiz.text()).toBe("<h1>oi</h1>");

    const css = await fetch(`${app.url}/web/x.css`);
    expect(css.status).toBe(200);
    expect(await css.text()).toBe("body{}");

    expect((await fetch(`${app.url}/web/sub/y.js`)).status).toBe(200);
    expect((await fetch(`${app.url}/web/nao-existe.js`)).status).toBe(404);
    expect((await fetch(`${app.url}/nada`)).status).toBe(404);
  });

  test("estáticos: path traversal é recusado", async () => {
    // Codificado, para o `..` passar pelo URL do fetch sem ser normalizado.
    for (const caminho of ["/web/..%2fsegredo.txt", "/web/%2e%2e%2fsegredo.txt", "/web/sub%2f..%2f..%2fsegredo.txt", "/web/..%5csegredo.txt"]) {
      const r = await fetch(`${app.url}${caminho}`);
      expect({ caminho, status: r.status }).toEqual({ caminho, status: 400 });
      expect(await r.text()).not.toContain("não pode sair");
    }
    // Cru, sem normalização do cliente.
    for (const caminho of ["/web/../segredo.txt", "/web/sub/../../segredo.txt"]) {
      const status = await requisicaoCrua(app.porta, caminho);
      expect([400, 404]).toContain(status);
    }
    // Byte nulo.
    expect((await fetch(`${app.url}/web/x.css%00.png`)).status).toBe(400);
  });

  test("a web/ de verdade do projeto é servida", async () => {
    const real = subirApp();
    try {
      const pagina = await fetch(`${real.url}/`);
      expect(pagina.status).toBe(200);
      const html = await pagina.text();
      expect(html).toContain('id="chat"');
      expect(html).toContain('id="canvas"');
      for (const f of ["app.css", "chat.css", "canvas.js", "chat.js"]) {
        expect({ f, status: (await fetch(`${real.url}/web/${f}`)).status }).toEqual({ f, status: 200 });
      }
    } finally {
      await real.encerrar();
    }
  });

  test("canvas: GET começa vazio; diff put/remove muda o GET e persiste em canvas.json", async () => {
    const vazio = await fetch(`${app.url}/api/canvas`);
    expect(vazio.status).toBe(200);
    expect(await vazio.json()).toEqual({ registros: {} });

    const diff = (corpo: unknown) =>
      fetch(`${app.url}/api/canvas/diff`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(corpo),
      });

    const forma = (id: string, x: number) => ({ id, typeName: "shape", type: "geo", x, y: 0 });
    const r1 = await diff({ put: { "shape:a": forma("shape:a", 1), "shape:b": forma("shape:b", 2), "page:p": { id: "page:p", typeName: "page" } } });
    expect(r1.status).toBe(204);
    const r2 = await diff({ put: { "shape:a": forma("shape:a", 10) }, remove: ["shape:b"] });
    expect(r2.status).toBe(204);

    const esperado = { "shape:a": forma("shape:a", 10), "page:p": { id: "page:p", typeName: "page" } };
    expect(await (await fetch(`${app.url}/api/canvas`)).json()).toEqual({ registros: esperado });

    const arquivo = join(app.dadosDir, "canvas.json");
    await app.canvas.descarregar();
    await ate(() => existsSync(arquivo), 2000, "canvas.json");
    expect(JSON.parse(readFileSync(arquivo, "utf8"))).toEqual({ registros: esperado });

    // Diffs inválidos.
    expect((await diff({ put: [1, 2] })).status).toBe(400);
    expect((await diff({ remove: "shape:a" })).status).toBe(400);
    expect((await diff([1])).status).toBe(400);
  });

  test("métodos errados devolvem 405", async () => {
    expect((await fetch(`${app.url}/api/mensagens`)).status).toBe(405);
    expect((await fetch(`${app.url}/api/estado`, { method: "POST" })).status).toBe(405);
    expect((await fetch(`${app.url}/api/canvas/diff`)).status).toBe(405);
  });
});
