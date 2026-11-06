import { afterEach, describe, expect, test } from "bun:test";
import { existsSync, mkdirSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Componentes, lerPasta, problemaDoComponente, type Componente } from "../src/componentes.ts";
import { LeitorSSE, ligarMcp, pastaTemporaria, rascunho, subirApp, textoDe } from "./ajuda.ts";

const FONTE = { repo: "exemplo/loja", arquivo: "src/app.js", simbolo: "publicacao", commit: "abc1234", receita: "executar" };

/** Uma pasta de wrapper com o componente.json e os arquivos de papel fixo. */
function pastaDeWrapper(raiz: string, nome: string, json: Record<string, unknown>, arquivos: Record<string, string> = {}): string {
  const pasta = join(raiz, nome);
  mkdirSync(pasta, { recursive: true });
  writeFileSync(join(pasta, "componente.json"), JSON.stringify(json));
  for (const [arquivo, conteudo] of Object.entries(arquivos)) writeFileSync(join(pasta, arquivo), conteudo);
  return pasta;
}

describe("componentes", () => {
  const limpar: (() => Promise<void> | void)[] = [];
  afterEach(async () => {
    for (const f of limpar.splice(0).reverse()) await f();
  });

  async function preparar() {
    const app = subirApp();
    limpar.push(app.encerrar);
    const { client, fechar } = await ligarMcp(app);
    limpar.push(fechar);
    const wrappers = pastaTemporaria();
    limpar.push(wrappers.apagar);
    return { app, client, wrappers: wrappers.dir };
  }

  const definir = (client: Awaited<ReturnType<typeof preparar>>["client"], args: Record<string, unknown>) =>
    client.callTool({ name: "componente_definir", arguments: args });

  test("o formato do CONTRATO: válido passa, o resto diz o problema", () => {
    expect(problemaDoComponente(rascunho())).toBeNull();
    expect(problemaDoComponente({ ...rascunho(), estado: "real", fonte: FONTE })).toBeNull();
    expect(problemaDoComponente({ ...rascunho(), variantes: { desktop: { css: "", w: 1280, h: 80 } } })).toBeNull();

    const casos: [Record<string, unknown>, string][] = [
      [{ ...rascunho(), id: "aviso-cliente" }, "produto"],
      [{ ...rascunho(), id: "Via/aviso" }, "kebab-case"],
      [{ ...rascunho(), id: "loja/aviso/x" }, "kebab-case"],
      [{ ...rascunho(), id: "loja/../x" }, "kebab-case"],
      [{ ...rascunho(), estado: "pronto" }, "estado"],
      [{ ...rascunho(), estado: "real" }, "exige fonte"],
      [{ ...rascunho(), fonte: FONTE }, "rascunho não tem fonte"],
      [{ ...rascunho(), estado: "real", fonte: { ...FONTE, receita: "raspar" } }, "receita"],
      [{ ...rascunho(), estado: "real", fonte: { repo: "x" } }, "commit"],
      [{ ...rascunho(), html: "" }, "html"],
      [{ ...rascunho(), css: undefined }, "css"],
      [{ ...rascunho(), w: 0 }, "w e h"],
      [{ ...rascunho(), slots: [{ chave: "x", seletor: ".x", como: "pintar" }] }, "como"],
      [{ ...rascunho(), dados: { x: 1 } }, "dados.x"],
      [{ ...rascunho(), variantes: { tablet: { css: "", w: 768, h: 1 } } }, "desktop"],
      [{ ...rascunho(), variantes: { desktop: { w: 1280, h: 1 } } }, "variantes.desktop.css"],
      [{ ...rascunho(), fontes: "x.css" }, "fontes"],
    ];
    for (const [valor, trecho] of casos) expect(problemaDoComponente(valor)).toContain(trecho);
    expect(problemaDoComponente([])).not.toBeNull();
  });

  test("componente_definir com o JSON grava em componentes/<produto>/<peça>.json, e a versão sobe", async () => {
    const { app, client } = await preparar();
    const r = await definir(client, { componente: { ...rascunho(), versao: 99, extra: "fica de fora" } });
    expect(r.isError).toBeFalsy();
    expect(JSON.parse(textoDe(r))).toEqual({ id: "loja/aviso-cliente", versao: 1, estado: "rascunho" });

    const arquivo = join(app.dadosDir, "componentes", "loja", "aviso-cliente.json");
    const gravado = JSON.parse(readFileSync(arquivo, "utf8")) as Componente & { extra?: string };
    expect(gravado.versao).toBe(1);
    expect(gravado.extra).toBeUndefined();
    expect(gravado.html).toBe(rascunho().html as string);

    const r2 = await definir(client, { componente: { ...rascunho(), nome: "Aviso v2" } });
    expect(JSON.parse(textoDe(r2))).toEqual({ id: "loja/aviso-cliente", versao: 2, estado: "rascunho" });
    expect((JSON.parse(readFileSync(arquivo, "utf8")) as Componente).nome).toBe("Aviso v2");

    // A versão sobrevive a reiniciar (vem do arquivo).
    const outro = new Componentes(app.dadosDir);
    expect(outro.definir(rascunho()).versao).toBe(3);
  });

  test("componente_definir recusa o inválido, com o problema, e nada é gravado", async () => {
    const { app, client } = await preparar();
    const real = await definir(client, { componente: { ...rascunho(), estado: "real" } });
    expect(real.isError).toBe(true);
    expect(textoDe(real)).toContain('estado "real" exige fonte');

    const idRuim = await definir(client, { componente: { ...rascunho(), id: "../fora" } });
    expect(idRuim.isError).toBe(true);
    expect(textoDe(idRuim)).toContain("<produto>/<peça>");

    const nenhum = await definir(client, {});
    expect(nenhum.isError).toBe(true);
    expect(textoDe(nenhum)).toContain("um dos dois");
    const osDois = await definir(client, { pasta: "/tmp", componente: rascunho() });
    expect(osDois.isError).toBe(true);

    expect(existsSync(join(app.dadosDir, "componentes"))).toBe(false);

    // O real com fonte passa.
    const ok = await definir(client, { componente: { ...rascunho("loja/botao"), estado: "real", fonte: FONTE } });
    expect(JSON.parse(textoDe(ok))).toEqual({ id: "loja/botao", versao: 1, estado: "real" });
  });

  test("componente_definir({pasta}) lê o componente.json e os arquivos de papel fixo quando o campo falta", async () => {
    const { app, client, wrappers } = await preparar();
    const json = { ...rascunho("loja/cartao-produto"), estado: "real", fonte: FONTE, variantes: { desktop: { w: 1280, h: 120 } } } as Record<string, unknown>;
    delete json.html;
    delete json.css;
    const pasta = pastaDeWrapper(wrappers, "cartao-imovel", json, {
      "peca.html": '<article class="cartao">do arquivo</article>',
      "peca.css": ".cartao{color:red}",
      "desktop.css": ".cartao{color:blue}",
      "sprite.svg": '<svg><symbol id="i-casa"/></svg>',
    });
    const r = await definir(client, { pasta });
    expect(r.isError).toBeFalsy();
    expect(JSON.parse(textoDe(r))).toEqual({ id: "loja/cartao-produto", versao: 1, estado: "real" });

    const c = app.componentes.ler("loja/cartao-produto")!;
    expect(c.html).toBe('<article class="cartao">do arquivo</article>');
    expect(c.css).toBe(".cartao{color:red}");
    expect(c.variantes).toEqual({ desktop: { css: ".cartao{color:blue}", w: 1280, h: 120 } });
    expect(c.sprite).toBe('<svg><symbol id="i-casa"/></svg>');
    expect(c.fonte).toEqual(FONTE as Componente["fonte"]);

    // O campo no JSON vence o arquivo.
    const pasta2 = pastaDeWrapper(wrappers, "aviso", rascunho(), { "peca.html": "<p>não usado</p>" });
    await definir(client, { pasta: pasta2 });
    expect(app.componentes.ler("loja/aviso-cliente")!.html).toBe(rascunho().html as string);

    // Sem variantes no JSON, um desktop.css vira a variante web (1280).
    const pasta3 = pastaDeWrapper(wrappers, "faixa", rascunho("loja/faixa"), { "desktop.css": ".faixa{}" });
    await definir(client, { pasta: pasta3 });
    expect(app.componentes.ler("loja/faixa")!.variantes).toEqual({ desktop: { css: ".faixa{}", w: 1280, h: 64 } });

    // componente_ler devolve a definição inteira.
    const lido = JSON.parse(textoDe(await client.callTool({ name: "componente_ler", arguments: { id: "loja/cartao-produto" } })));
    expect(lido).toEqual(c);
  });

  test("a pasta: caminho relativo, com .., inexistente, sem componente.json e link para fora são recusados", async () => {
    const { client, wrappers } = await preparar();
    const fora = pastaTemporaria();
    limpar.push(fora.apagar);
    writeFileSync(join(fora.dir, "segredo.css"), "body{background:url(segredo)}");
    writeFileSync(join(fora.dir, "componente.json"), JSON.stringify(rascunho("loja/segredo")));

    const semCss = { ...rascunho("loja/link") } as Record<string, unknown>;
    delete semCss.css;
    const comLink = pastaDeWrapper(wrappers, "com-link", semCss);
    symlinkSync(join(fora.dir, "segredo.css"), join(comLink, "peca.css"));

    const soLink = join(wrappers, "so-link");
    mkdirSync(soLink);
    symlinkSync(join(fora.dir, "componente.json"), join(soLink, "componente.json"));

    pastaDeWrapper(wrappers, "ok", rascunho("loja/ok"));
    const casos: [string, string][] = [
      ["relativa/pasta", "caminho absoluto"],
      [`${wrappers}/ok/../../${fora.dir.split("/").pop()}`, '".."'],
      [join(wrappers, "nao-existe"), "não existe"],
      [fora.dir + "/segredo.css", "não é uma pasta"],
      [join(wrappers), "não tem componente.json"],
      [comLink, "para fora da pasta"],
      [soLink, "para fora da pasta"],
    ];
    for (const [pasta, trecho] of casos) {
      const r = await definir(client, { pasta });
      expect({ pasta, erro: r.isError }).toEqual({ pasta, erro: true });
      expect(textoDe(r)).toContain(trecho);
    }
    expect(() => lerPasta("x")).toThrow("absoluto");

    // Um link que fica dentro da pasta vale.
    const dentro = pastaDeWrapper(wrappers, "dentro", semCss, { "estilos.css": ".x{}" });
    symlinkSync(join(dentro, "estilos.css"), join(dentro, "peca.css"));
    expect((await definir(client, { pasta: dentro })).isError).toBeFalsy();
  });

  test("cada definição manda o SSE `componente` {id, versao} para todas as abas", async () => {
    const { app, client } = await preparar();
    const aba1 = await LeitorSSE.abrir(app.url);
    limpar.push(() => aba1.fechar());
    const aba2 = await LeitorSSE.abrir(app.url);
    limpar.push(() => aba2.fechar());
    await aba1.evento("ola");
    await aba2.evento("ola");

    await definir(client, { componente: rascunho() });
    expect(await aba1.evento<{ id: string; versao: number }>("componente")).toEqual({ id: "loja/aviso-cliente", versao: 1 });
    expect(await aba2.evento<{ id: string; versao: number }>("componente")).toEqual({ id: "loja/aviso-cliente", versao: 1 });
    await definir(client, { componente: rascunho() });
    expect(await aba1.evento<{ id: string; versao: number }>("componente")).toEqual({ id: "loja/aviso-cliente", versao: 2 });
    expect(await aba2.evento<{ id: string; versao: number }>("componente")).toEqual({ id: "loja/aviso-cliente", versao: 2 });

    // Uma definição recusada não avisa ninguém.
    await definir(client, { componente: { ...rascunho(), w: -1 } });
    await Bun.sleep(50);
    expect(aba1.nomeados().filter((e) => e.evento === "componente")).toHaveLength(2);
  });

  test("componente_listar e GET /api/componentes", async () => {
    const { app, client } = await preparar();
    const vazio = JSON.parse(textoDe(await client.callTool({ name: "componente_listar", arguments: {} })));
    expect(vazio.componentes).toEqual([]);
    expect(vazio.dica).toContain("componente_definir");

    await definir(client, { componente: rascunho("loja/topo") });
    await definir(client, { componente: rascunho("acme/botao") });
    await definir(client, { componente: rascunho("loja/aviso") });
    // Um arquivo estragado na pasta é ignorado.
    writeFileSync(join(app.dadosDir, "componentes", "loja", "quebrado.json"), "{ não é json");

    const todos = JSON.parse(textoDe(await client.callTool({ name: "componente_listar", arguments: {} }))) as {
      componentes: Record<string, unknown>[];
    };
    expect(todos.componentes.map((c) => c.id)).toEqual(["acme/botao", "loja/aviso", "loja/topo"]);
    expect(todos.componentes[0]).toEqual({
      id: "acme/botao",
      nome: "Aviso da cliente",
      descricao: "O aviso no topo quando a corretora busca para uma cliente.",
      estado: "rascunho",
      versao: 1,
      w: 393,
      h: 64,
      chaves: ["titulo", "nome", "cor"],
      dados: { titulo: "Buscando para", nome: "Vera" },
    });
    const via = JSON.parse(textoDe(await client.callTool({ name: "componente_listar", arguments: { produto: "loja" } }))) as {
      componentes: { id: string }[];
    };
    expect(via.componentes.map((c) => c.id)).toEqual(["loja/aviso", "loja/topo"]);

    const r = await fetch(`${app.url}/api/componentes`);
    expect(r.status).toBe(200);
    const { componentes } = (await r.json()) as { componentes: Componente[] };
    expect(componentes.map((c) => c.id)).toEqual(["acme/botao", "loja/aviso", "loja/topo"]);
    expect(componentes[1]!.html).toBe(rascunho().html as string);
    expect(componentes[1]!.versao).toBe(1);
    expect((await fetch(`${app.url}/api/componentes`, { method: "POST" })).status).toBe(405);

    // Os kits saíram.
    expect((await fetch(`${app.url}/api/kits`)).status).toBe(404);
    expect((await fetch(`${app.url}/kits/tmp/kit.json`)).status).toBe(404);

    const naoExiste = await client.callTool({ name: "componente_ler", arguments: { id: "loja/nada" } });
    expect(naoExiste.isError).toBe(true);
    expect(textoDe(naoExiste)).toContain("loja/aviso, loja/topo");
  });

  test("as instruções falam de componentes e não de kits", async () => {
    const { client } = await preparar();
    const instrucoes = client.getInstructions() ?? "";
    for (const trecho of ["componente_definir", "rascunho", "tela_montar", "skill design", "chat_atividade", "1280×800", "393×852", "não consigo"]) {
      expect({ trecho, tem: instrucoes.includes(trecho) }).toEqual({ trecho, tem: true });
    }
    expect(instrucoes).not.toContain("widget_");
    expect(instrucoes).not.toContain("kit");
  });
});
