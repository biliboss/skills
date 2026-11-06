import { afterEach, describe, expect, test } from "bun:test";
import { mkdirSync, utimesSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { LeitorSSE, ligarMcp, pastaTemporaria, rascunho, subirApp, textoDe } from "./ajuda.ts";

type Pedido = { pedido: string; op: Record<string, unknown> };

describe("patches no disco, modificadores e componentes_conferir", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  /** Um app com <tmp>/mod-a/patches e <tmp>/mod-b/patches como pastas de patches. */
  async function preparar() {
    const tmp = pastaTemporaria();
    limpar.push(tmp.apagar);
    const pa = join(tmp.dir, "mod-a", "patches");
    const pb = join(tmp.dir, "mod-b", "patches");
    mkdirSync(pa, { recursive: true });
    mkdirSync(pb, { recursive: true });
    const app = subirApp({ patchesDirs: [pa, pb] });
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    limpar.push(fechar);
    app.componentes.definir({
      ...rascunho("loja/botao"),
      slots: [{ chave: "rotulo", seletor: ".btn", como: "texto" }],
      dados: { rotulo: "Continuar" },
      modificadores: {
        carregando: { descricao: "esperando a rede", classe: "is-loading", dados: { rotulo: "Aguarde" } },
        desabilitado: { attr: { disabled: "" } },
      },
    });
    const escrever = (pasta: string, nome: string, v: unknown) => writeFileSync(join(pasta, nome), typeof v === "string" ? v : JSON.stringify(v));
    return { app, client, pa, pb, escrever };
  }

  test("o patch do disco se aplica na leitura e não é gravado na definição", async () => {
    const { app, pa, escrever } = await preparar();
    escrever(pa, "10-rotulo.json", { alvo: "loja/botao", ops: [{ op: "replace", path: "/dados/rotulo", value: "Seguir" }, { op: "css", anexar: ".x{color:red}" }] });
    expect(app.componentes.ler("loja/botao")!.dados.rotulo).toBe("Seguir");
    expect(app.componentes.ler("loja/botao")!.css).toContain(".x{color:red}");
    expect(app.componentes.todos().find((c) => c.id === "loja/botao")!.dados.rotulo).toBe("Seguir");
    // o arquivo guardado continua cru
    const cru = JSON.parse(await Bun.file(join(app.dadosDir, "componentes", "loja", "botao.json")).text());
    expect(cru.dados.rotulo).toBe("Continuar");
    // mudou o arquivo (mtime): a próxima leitura vê
    escrever(pa, "10-rotulo.json", { alvo: "loja/botao", ops: [{ op: "replace", path: "/dados/rotulo", value: "Ir" }] });
    utimesSync(join(pa, "10-rotulo.json"), new Date(), new Date(Date.now() + 5000));
    expect(app.componentes.ler("loja/botao")!.dados.rotulo).toBe("Ir");
  });

  test("a ordem é por pasta (mod) e por nome de arquivo: o último ganha", async () => {
    const { app, pa, pb, escrever } = await preparar();
    escrever(pb, "a.json", { alvo: "loja/*", ops: [{ op: "replace", path: "/dados/rotulo", value: "do B" }] });
    escrever(pa, "z.json", { alvo: "loja/botao", ops: [{ op: "replace", path: "/dados/rotulo", value: "do A-z" }] });
    escrever(pa, "b.json", { alvo: "loja/botao", ops: [{ op: "replace", path: "/dados/rotulo", value: "do A-b" }] });
    expect(app.componentes.ler("loja/botao")!.dados.rotulo).toBe("do B");
    const log = app.componentes.conferirCarga();
    expect(log.patchesCarregados).toEqual(["mod-a/b", "mod-a/z", "mod-b/a"]);
  });

  test("patch que deixa o componente inválido é descartado e o erro vai para o log; arquivo inválido não quebra", async () => {
    const { app, pa, escrever } = await preparar();
    escrever(pa, "1-ruim.json", { alvo: "loja/botao", ops: [{ op: "replace", path: "/html", value: "" }] });
    escrever(pa, "2-bom.json", { alvo: "loja/botao", ops: [{ op: "replace", path: "/dados/rotulo", value: "Bom" }] });
    escrever(pa, "3-quebrado.json", "{ nao é json");
    escrever(pa, "4-sem-alvo.json", { ops: [] });
    const c = app.componentes.ler("loja/botao")!;
    expect(c.html).toContain("aviso");
    expect(c.dados.rotulo).toBe("Bom");

    const log = app.componentes.conferirCarga("loja");
    const b = log.componentes.find((x) => x.id === "loja/botao")!;
    expect(b.aplicados).toEqual(["mod-a/2-bom"]);
    expect(b.erros.map((e) => e.nome)).toEqual(["mod-a/1-ruim"]);
    expect(b.erros[0]!.erro).toContain("descartado");
    expect(log.patchesInvalidos.map((p) => p.arquivo.split("/").pop()).sort()).toEqual(["3-quebrado.json", "4-sem-alvo.json"]);
  });

  test("componentes_conferir (MCP e GET /api/componentes/log): pulados, requer faltando e filho inválido", async () => {
    const { app, client, pa, escrever } = await preparar();
    app.componentes.definir({ ...rascunho("loja/base"), abstrato: true });
    app.componentes.definir(rascunho("outro/dep"));
    app.componentes.definir({ id: "loja/filho", herda: "loja/base", nome: "Filho", descricao: "d", requer: ["outro/dep"] } as never);
    escrever(pa, "pula.json", { alvo: "loja/botao", seExiste: "mod/ausente", ops: [{ op: "css", anexar: ".y{}" }] });
    // pai sumindo deixa o filho inválido
    await Bun.$`rm ${join(app.dadosDir, "componentes", "loja", "base.json")} ${join(app.dadosDir, "componentes", "outro", "dep.json")}`;

    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");
    escrever(pa, "ok.json", { alvo: "loja/botao", ops: [{ op: "css", anexar: ".z{}" }] });

    const r = await client.callTool({ name: "componentes_conferir", arguments: { produto: "loja" } });
    const log = JSON.parse(textoDe(r));
    const botao = log.componentes.find((x: { id: string }) => x.id === "loja/botao");
    expect(botao.aplicados).toEqual(["mod-a/ok"]);
    expect(botao.pulados[0].nome).toBe("mod-a/pula");
    const filho = log.componentes.find((x: { id: string }) => x.id === "loja/filho");
    expect(filho.valido).toBe(false);
    expect(filho.problemas.join(" ")).toContain("loja/base");
    expect(filho.requerFaltando).toEqual(["outro/dep"]);
    // o evento componente dos afetados
    expect(await sse.evento<{ id: string }>("componente", (d) => d.id === "loja/botao")).toBeTruthy();

    const http = (await (await fetch(`${app.url}/api/componentes/log?produto=loja`)).json()) as typeof log;
    expect(http.componentes.map((x: { id: string }) => x.id)).toEqual(log.componentes.map((x: { id: string }) => x.id));
  });

  test("componente_listar mostra os modificadores e aceita incluirAbstratos", async () => {
    const { app, client } = await preparar();
    app.componentes.definir({ ...rascunho("loja/base"), abstrato: true });
    const l = async (args: Record<string, unknown>) => JSON.parse(textoDe(await client.callTool({ name: "componente_listar", arguments: args }))).componentes;
    expect((await l({})).map((c: { id: string }) => c.id)).toEqual(["loja/botao"]);
    const todos = await l({ incluirAbstratos: true });
    expect(todos.map((c: { id: string }) => c.id)).toEqual(["loja/base", "loja/botao"]);
    expect(todos[1].modificadores).toEqual([{ nome: "carregando", descricao: "esperando a rede" }, { nome: "desabilitado" }]);
  });

  test("filho herda os modificadores do pai, mesclados por nome", async () => {
    const { app } = await preparar();
    app.componentes.definir({ id: "loja/botao-forte", herda: "loja/botao", nome: "Forte", descricao: "d", modificadores: { carregando: { classe: "forte" }, erro: { classe: "is-erro" } } } as never);
    const m = app.componentes.ler("loja/botao-forte")!.modificadores!;
    expect(Object.keys(m).sort()).toEqual(["carregando", "desabilitado", "erro"]);
    expect(m.carregando!.classe).toBe("forte");
  });

  test("a definição com modificador ruim é recusada", async () => {
    const { app } = await preparar();
    expect(() => app.componentes.definir({ ...rascunho("loja/x"), modificadores: { Ruim: { dados: { naoExiste: "a" } } } })).toThrow(/modificadores/);
  });

  test("tela_montar, instancia_inserir e instancia_mudar validam os modificadores e levam na op", async () => {
    const { app, client } = await preparar();
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");

    const ruim = await client.callTool({ name: "tela_montar", arguments: { nome: "T", pecas: [{ componente: "loja/botao", modificadores: ["sumido"] }] } });
    expect(ruim.isError).toBe(true);
    expect(textoDe(ruim)).toContain("sumido");
    expect(textoDe(ruim)).toContain("carregando, desabilitado");
    const lat = await client.callTool({ name: "tela_montar", arguments: { nome: "T", largura: "desktop", pecas: [{ componente: "loja/botao" }], lateral: { largura: 200, pecas: [{ componente: "loja/botao", modificadores: ["x"] }] } } });
    expect(lat.isError).toBe(true);
    expect(textoDe(lat)).toContain("lateral");

    const c = client.callTool({ name: "tela_montar", arguments: { nome: "T", pecas: [{ componente: "loja/botao", modificadores: ["carregando"] }] } });
    const p = await sse.evento<Pedido>("canvas");
    expect(p.op.pecas).toEqual([{ componente: "loja/botao", modificadores: ["carregando"] }]);
    await fetch(`${app.url}/api/canvas/resposta`, { method: "POST", body: JSON.stringify({ pedido: p.pedido, ok: true, resultado: { id: "shape:t", pecas: ["shape:a"] } }) });
    expect((await c).isError).toBeFalsy();

    const dup = await client.callTool({ name: "instancia_inserir", arguments: { tela: "shape:t", componente: "loja/botao", modificadores: ["carregando", "carregando"] } });
    expect(dup.isError).toBe(true);
    expect(textoDe(dup)).toContain("repetido");
    const i = client.callTool({ name: "instancia_inserir", arguments: { tela: "shape:t", componente: "loja/botao", modificadores: ["desabilitado"] } });
    const pi = await sse.evento<Pedido>("canvas");
    expect(pi.op).toMatchObject({ tipo: "instancia_inserir", modificadores: ["desabilitado"] });
    await fetch(`${app.url}/api/canvas/resposta`, { method: "POST", body: JSON.stringify({ pedido: pi.pedido, ok: true, resultado: { id: "shape:i" } }) });
    await i;

    // instancia_mudar: sem espelho do canvas o servidor repassa à página, que valida; só manda modificadores
    const m = client.callTool({ name: "instancia_mudar", arguments: { id: "shape:i", modificadores: [] } });
    const pm = await sse.evento<Pedido>("canvas");
    expect(pm.op).toMatchObject({ tipo: "instancia_mudar", id: "shape:i", modificadores: [] });
    await fetch(`${app.url}/api/canvas/resposta`, { method: "POST", body: JSON.stringify({ pedido: pm.pedido, ok: true, resultado: { id: "shape:i" } }) });
    await m;
    const vazio = await client.callTool({ name: "instancia_mudar", arguments: { id: "shape:i" } });
    expect(vazio.isError).toBe(true);
  });
});
