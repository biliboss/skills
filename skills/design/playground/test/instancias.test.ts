import { afterEach, describe, expect, test } from "bun:test";
import { LeitorSSE, ligarMcp, rascunho, subirApp, textoDe } from "./ajuda.ts";

type Pedido = { pedido: string; op: Record<string, unknown> };

describe("tela_montar e instâncias", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  /** Um app com dois componentes definidos (loja/topo e loja/botao) e uma página aberta. */
  async function preparar() {
    const app = subirApp();
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    limpar.push(fechar);
    app.componentes.definir(rascunho("loja/topo"));
    app.componentes.definir({
      ...rascunho("loja/botao"),
      slots: [{ chave: "rotulo", seletor: ".btn", como: "texto" }],
      dados: { rotulo: "Continuar" },
    });
    const sse = await LeitorSSE.abrir(app.url);
    limpar.push(() => sse.fechar());
    await sse.evento("ola");
    return { app, client, sse };
  }

  async function responder(url: string, pedido: string, resultado: unknown) {
    const r = await fetch(`${url}/api/canvas/resposta`, { method: "POST", body: JSON.stringify({ pedido, ok: true, resultado }) });
    expect(r.status).toBe(204);
  }

  test("tela_montar manda a op {nome, w, h, x, y, pecas: [{componente, dados}]} e volta com a resposta da página", async () => {
    const { app, client, sse } = await preparar();
    const pecas = [{ componente: "loja/topo", dados: { nome: "Cliente" } }, { componente: "loja/botao" }];
    const chamada = client.callTool({ name: "tela_montar", arguments: { nome: "Busca", largura: "desktop", x: 10, y: 20, pecas } });
    const p = await sse.evento<Pedido>("canvas");
    expect(p.op).toEqual({ tipo: "tela_montar", nome: "Busca", w: 1280, h: 800, x: 10, y: 20, pecas });
    await responder(app.url, p.pedido, { id: "shape:tela", pecas: ["shape:a", "shape:b"] });
    const r = await chamada;
    expect(r.isError).toBeFalsy();
    expect(JSON.parse(textoDe(r))).toEqual({ id: "shape:tela", pecas: ["shape:a", "shape:b"] });

    // celular por padrão; a altura explícita vence
    const c2 = client.callTool({ name: "tela_montar", arguments: { nome: "Busca iPhone", altura: 1200, pecas: [pecas[1]] } });
    const p2 = await sse.evento<Pedido>("canvas");
    expect(p2.op).toMatchObject({ tipo: "tela_montar", w: 393, h: 1200, pecas: [{ componente: "loja/botao" }] });
    await responder(app.url, p2.pedido, { id: "shape:t2", pecas: ["shape:c"] });
    expect((await c2).isError).toBeFalsy();
  });

  test("tela_montar e instancia_inserir recusam componente ou chave que não existe, no servidor, sem ir à página", async () => {
    const { client, sse } = await preparar();
    const montar = (pecas: unknown[]) => client.callTool({ name: "tela_montar", arguments: { nome: "Home", pecas } });

    const semComponente = await montar([{ componente: "loja/topo" }, { componente: "loja/rodape" }]);
    expect(semComponente.isError).toBe(true);
    expect(textoDe(semComponente)).toContain('peça 2: não existe o componente "loja/rodape"');
    expect(textoDe(semComponente)).toContain("loja/botao, loja/topo");
    expect(textoDe(semComponente)).toContain("componente_definir");

    const outroProduto = await montar([{ componente: "acme/topo" }]);
    expect(outroProduto.isError).toBe(true);
    expect(textoDe(outroProduto)).toContain("loja/botao, loja/topo");

    const chaveRuim = await montar([{ componente: "loja/botao", dados: { cor: "azul", rotulo: "Ir" } }]);
    expect(chaveRuim.isError).toBe(true);
    expect(textoDe(chaveRuim)).toContain('o componente "loja/botao" não tem as chaves cor (chaves: rotulo)');

    // id fora do formato: o schema recusa
    const idRuim = await montar([{ componente: "botao" }]);
    expect(idRuim.isError).toBe(true);

    const inserir = await client.callTool({ name: "instancia_inserir", arguments: { tela: "shape:t", componente: "loja/rodape" } });
    expect(inserir.isError).toBe(true);
    expect(textoDe(inserir)).toContain('não existe o componente "loja/rodape"');
    const inserirChave = await client.callTool({
      name: "instancia_inserir",
      arguments: { tela: "shape:t", componente: "loja/botao", dados: { titulo: "x" } },
    });
    expect(inserirChave.isError).toBe(true);
    expect(textoDe(inserirChave)).toContain("titulo");

    await Bun.sleep(50);
    expect(sse.nomeados().filter((e) => e.evento === "canvas")).toEqual([]);
  });

  test("tela_montar com lateral manda {lateral: {largura, pecas}} na op e devolve os ids da lateral", async () => {
    const { app, client, sse } = await preparar();
    const lateral = { largura: 248, pecas: [{ componente: "loja/topo" }, { componente: "loja/botao", dados: { rotulo: "Sair" } }] };
    const pecas = [{ componente: "loja/botao" }];
    const chamada = client.callTool({ name: "tela_montar", arguments: { nome: "Painel", largura: 1280, x: 0, y: 0, pecas, lateral } });
    const p = await sse.evento<Pedido>("canvas");
    expect(p.op).toEqual({ tipo: "tela_montar", nome: "Painel", w: 1280, h: 800, x: 0, y: 0, pecas, lateral });
    const resultado = { id: "shape:tela", pecas: ["shape:p"], lateral: ["shape:l1", "shape:l2"] };
    await responder(app.url, p.pedido, resultado);
    const r = await chamada;
    expect(r.isError).toBeFalsy();
    expect(JSON.parse(textoDe(r))).toEqual(resultado);

    // nos limites: 80 e a largura da tela − 200 (desktop: 1080) passam
    for (const largura of [80, 1080]) {
      const c = client.callTool({ name: "tela_montar", arguments: { nome: "Limite", largura: "desktop", pecas, lateral: { largura, pecas } } });
      const pl = await sse.evento<Pedido>("canvas");
      expect(pl.op).toMatchObject({ w: 1280, lateral: { largura } });
      await responder(app.url, pl.pedido, { id: "shape:t", pecas: ["shape:a"], lateral: ["shape:b"] });
      expect((await c).isError).toBeFalsy();
    }
  });

  test("tela_montar recusa na lateral componente, chave e largura fora de 80..(largura da tela − 200), sem ir à página", async () => {
    const { client, sse } = await preparar();
    const montar = (largura: unknown, lateral: unknown) =>
      client.callTool({ name: "tela_montar", arguments: { nome: "Painel", largura, pecas: [{ componente: "loja/topo" }], lateral } });

    const semComponente = await montar("desktop", { largura: 248, pecas: [{ componente: "loja/topo" }, { componente: "loja/menu" }] });
    expect(semComponente.isError).toBe(true);
    expect(textoDe(semComponente)).toContain('lateral, peça 2: não existe o componente "loja/menu"');

    const chaveRuim = await montar("desktop", { largura: 248, pecas: [{ componente: "loja/botao", dados: { icone: "x" } }] });
    expect(chaveRuim.isError).toBe(true);
    expect(textoDe(chaveRuim)).toContain("lateral, ");
    expect(textoDe(chaveRuim)).toContain('o componente "loja/botao" não tem as chaves icone');

    const estreita = await montar("desktop", { largura: 79, pecas: [{ componente: "loja/topo" }] });
    expect(estreita.isError).toBe(true);
    expect(textoDe(estreita)).toContain("lateral.largura deve ficar entre 80 e 1080");

    const larga = await montar("desktop", { largura: 1081, pecas: [{ componente: "loja/topo" }] });
    expect(larga.isError).toBe(true);
    expect(textoDe(larga)).toContain("entre 80 e 1080");

    // num celular (393) o máximo é 193; numa tela de 200 não cabe lateral nenhuma
    expect(textoDe(await montar("celular", { largura: 194, pecas: [{ componente: "loja/topo" }] }))).toContain("entre 80 e 193");
    expect(textoDe(await montar(200, { largura: 80, pecas: [{ componente: "loja/topo" }] }))).toContain("estreita demais");

    // a lateral sem peças: o schema recusa
    expect((await montar("desktop", { largura: 248, pecas: [] })).isError).toBe(true);

    await Bun.sleep(50);
    expect(sse.nomeados().filter((e) => e.evento === "canvas")).toEqual([]);
  });

  test("instancia_inserir leva a coluna na op e recusa coluna fora de lateral/principal", async () => {
    const { app, client, sse } = await preparar();
    for (const coluna of ["lateral", "principal"]) {
      const c = client.callTool({ name: "instancia_inserir", arguments: { tela: "shape:tela", componente: "loja/topo", coluna, indice: 0 } });
      const p = await sse.evento<Pedido>("canvas");
      expect(p.op).toEqual({ tipo: "instancia_inserir", tela: "shape:tela", componente: "loja/topo", indice: 0, coluna });
      await responder(app.url, p.pedido, { id: "shape:x" });
      expect((await c).isError).toBeFalsy();
    }
    const ruim = await client.callTool({ name: "instancia_inserir", arguments: { tela: "shape:tela", componente: "loja/topo", coluna: "direita" } });
    expect(ruim.isError).toBe(true);
  });

  test("instancia_inserir, instancia_mudar e canvas_agrupar mandam as ops certas", async () => {
    const { app, client, sse } = await preparar();
    const casos: [string, Record<string, unknown>, Record<string, unknown>, unknown][] = [
      [
        "instancia_inserir",
        { tela: "shape:tela", componente: "loja/botao", dados: { rotulo: "Ver no mapa" }, indice: 1 },
        { tipo: "instancia_inserir", tela: "shape:tela", componente: "loja/botao", dados: { rotulo: "Ver no mapa" }, indice: 1 },
        { id: "shape:w" },
      ],
      [
        "instancia_mudar",
        { id: "shape:w", dados: { rotulo: "Buscar", lista: ["a", "b"] } },
        { tipo: "instancia_mudar", id: "shape:w", dados: { rotulo: "Buscar", lista: ["a", "b"] } },
        { id: "shape:w" },
      ],
      ["canvas_agrupar", { ids: ["shape:a", "shape:b"] }, { tipo: "agrupar", ids: ["shape:a", "shape:b"] }, { id: "shape:g" }],
    ];
    for (const [nome, args, op, resultado] of casos) {
      const chamada = client.callTool({ name: nome, arguments: args });
      const p = await sse.evento<Pedido>("canvas");
      expect({ nome, op: p.op }).toEqual({ nome, op });
      await responder(app.url, p.pedido, resultado);
      const r = await chamada;
      expect({ nome, erro: r.isError ?? false }).toEqual({ nome, erro: false });
      expect(JSON.parse(textoDe(r))).toEqual(resultado);
    }

    // instancia_inserir sem indice nem dados: a op vai sem eles
    const c = client.callTool({ name: "instancia_inserir", arguments: { tela: "shape:tela", componente: "loja/topo" } });
    const p = await sse.evento<Pedido>("canvas");
    expect(p.op).toEqual({ tipo: "instancia_inserir", tela: "shape:tela", componente: "loja/topo" });
    await responder(app.url, p.pedido, { id: "shape:x" });
    await c;

    // agrupar pede pelo menos duas formas
    expect((await client.callTool({ name: "canvas_agrupar", arguments: { ids: ["shape:a"] } })).isError).toBe(true);
  });

  test("instancia_mudar confere as chaves quando o espelho do canvas conhece a instância", async () => {
    const { app, client, sse } = await preparar();
    const instancia = { id: "shape:i", typeName: "shape", type: "widget", props: { w: 393, h: 56, componente: "loja/botao", dados: "{}" } };
    const r = await fetch(`${app.url}/api/canvas/diff`, { method: "POST", body: JSON.stringify({ put: { "shape:i": instancia } }) });
    expect(r.status).toBe(204);

    const ruim = await client.callTool({ name: "instancia_mudar", arguments: { id: "shape:i", dados: { preco: "R$ 1" } } });
    expect(ruim.isError).toBe(true);
    expect(textoDe(ruim)).toContain("não tem as chaves preco");

    const boa = client.callTool({ name: "instancia_mudar", arguments: { id: "shape:i", dados: { rotulo: "Salvar" } } });
    const p = await sse.evento<Pedido>("canvas");
    expect(p.op).toEqual({ tipo: "instancia_mudar", id: "shape:i", dados: { rotulo: "Salvar" } });
    await responder(app.url, p.pedido, { id: "shape:i" });
    expect((await boa).isError).toBeFalsy();
  });
});
