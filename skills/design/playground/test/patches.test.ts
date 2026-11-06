import { describe, expect, test } from "bun:test";
import { aplicaA, aplicarPatches, problemasDoPatch, type Patch } from "../src/patches.ts";

const base = () => ({
  id: "loja/botao",
  css: ".b{color:red}",
  html: '<div><button class="b">Comprar</button><span>x</span></div>',
  variantes: { desktop: { html: '<button class="b">Comprar</button>', css: ".d{}", w: 1, h: 1 } },
  dados: { rotulo: "Comprar", itens: ["a", "b"], "a/b": { "c~d": 1 } } as Record<string, any>,
});
const ap = (patch: Patch, existe = (_: string) => true, c = base()) => aplicarPatches(c, [{ nome: "p.json", patch }], existe);
const P = (ops: any[], extra: Partial<Patch> = {}): Patch => ({ alvo: "loja/botao", ops, ...extra });

describe("patches: JSON Patch", () => {
  test("add, replace, remove, listas, '-' e escapes", () => {
    const r = ap(P([
      { op: "add", path: "/dados/novo", value: { x: 1 } },
      { op: "replace", path: "/dados/rotulo", value: "Levar" },
      { op: "add", path: "/dados/itens/-", value: "c" },
      { op: "add", path: "/dados/itens/0", value: "z" },
      { op: "remove", path: "/dados/itens/1" },
      { op: "replace", path: "/dados/a~1b/c~0d", value: 2 },
    ]));
    expect(r.erros).toEqual([]);
    expect(r.aplicados).toEqual(["p.json"]);
    expect(r.componente.dados).toEqual({ rotulo: "Levar", itens: ["z", "b", "c"], novo: { x: 1 }, "a/b": { "c~d": 2 } });
  });
  test("não muda a entrada", () => {
    const c = base();
    ap(P([{ op: "replace", path: "/dados/rotulo", value: "Z" }]), () => true, c);
    expect(c.dados.rotulo).toBe("Comprar");
  });
  test("test que passa deixa seguir; que falha pula o patch inteiro", () => {
    const ok = ap(P([{ op: "test", path: "/dados/rotulo", value: "Comprar" }, { op: "replace", path: "/dados/rotulo", value: "Q" }]));
    expect(ok.componente.dados.rotulo).toBe("Q");
    const no = ap(P([{ op: "replace", path: "/dados/rotulo", value: "Q" }, { op: "test", path: "/dados/rotulo", value: "outro" }]));
    expect(no.componente.dados.rotulo).toBe("Comprar");
    expect(no.aplicados).toEqual([]);
    expect(no.erros).toEqual([]);
    expect(no.pulados[0]!.nome).toBe("p.json");
    expect(no.pulados[0]!.porque).toContain("ops[1]");
  });
  test("atomicidade: replace/remove em path inexistente desfaz tudo e dá o índice", () => {
    for (const op of [{ op: "replace", path: "/dados/nada", value: 1 }, { op: "remove", path: "/dados/nada" }]) {
      const r = ap(P([{ op: "replace", path: "/dados/rotulo", value: "Q" }, { op: "css", anexar: ".z{}" }, op]));
      expect(r.componente.dados.rotulo).toBe("Comprar");
      expect(r.componente.css).toBe(".b{color:red}");
      expect(r.erros).toHaveLength(1);
      expect(r.erros[0]!.erro).toContain("ops[2]");
    }
  });
  test("um patch com erro não impede o seguinte", () => {
    const r = aplicarPatches(base(), [
      { nome: "a.json", patch: P([{ op: "remove", path: "/dados/nada" }]) },
      { nome: "b.json", patch: P([{ op: "replace", path: "/dados/rotulo", value: "B" }]) },
    ], () => true);
    expect(r.erros.map((e) => e.nome)).toEqual(["a.json"]);
    expect(r.aplicados).toEqual(["b.json"]);
  });
});

describe("patches: html e css", () => {
  test("texto, attr, classe, antes, depois no html e na variante desktop", () => {
    const r = ap(P([
      { op: "html", seletor: "button", acao: "texto", valor: "Levar" },
      { op: "html", seletor: "button", acao: "attr", nome: "data-x", valor: "1" },
      { op: "html", seletor: "button", acao: "classe", valor: "grande" },
      { op: "html", seletor: "button", acao: "antes", valor: "<i>A</i>" },
      { op: "html", seletor: "button", acao: "depois", valor: "<i>D</i>" },
    ]));
    expect(r.erros).toEqual([]);
    for (const h of [r.componente.html, r.componente.variantes.desktop.html]) {
      expect(h).toContain("Levar</button>");
      expect(h).toContain('data-x="1"');
      expect(h).toContain('class="b grande"');
      expect(h).toContain("<i>A</i><button");
      expect(h).toContain("</button><i>D</i>");
    }
  });
  test("remover", () => {
    const r = ap(P([{ op: "html", seletor: "span", acao: "remover" }]));
    expect(r.componente.html).not.toContain("span");
    expect(r.componente.html).toContain("button");
  });
  test("seletor sem match é erro e desfaz", () => {
    const r = ap(P([{ op: "css", anexar: ".z{}" }, { op: "html", seletor: ".nao-existe", acao: "remover" }]));
    expect(r.erros[0]!.erro).toBe("ops[1]: o seletor .nao-existe não achou nada em loja/botao");
    expect(r.componente.css).toBe(".b{color:red}");
    expect(r.componente.html).toBe(base().html);
  });
  test("seletor que só casa na variante desktop vale", () => {
    const c = base();
    c.html = "<div>sem botão</div>";
    const r = ap(P([{ op: "html", seletor: "button", acao: "remover" }]), () => true, c);
    expect(r.erros).toEqual([]);
    expect(r.componente.variantes.desktop.html).toBe("");
  });
  test("css soma no fim, também no desktop", () => {
    const r = ap(P([{ op: "css", anexar: ".x{top:0}" }]));
    expect(r.componente.css).toBe(".b{color:red}\n.x{top:0}");
    expect(r.componente.variantes.desktop.css).toBe(".d{}\n.x{top:0}");
  });
});

describe("patches: alvo e seExiste", () => {
  const p = (alvo: Patch["alvo"]): Patch => P([{ op: "css", anexar: "a{}" }], { alvo });
  test("alvo exato, lista e '*'", () => {
    expect(aplicaA(p("loja/botao"), "loja/botao")).toBe(true);
    expect(aplicaA(p("loja/botao"), "loja/botao-grande")).toBe(false);
    expect(aplicaA(p(["loja/a", "loja/botao"]), "loja/botao")).toBe(true);
    expect(aplicaA(p("loja/*"), "loja/qualquer")).toBe(true);
    expect(aplicaA(p("loja/*"), "outra/qualquer")).toBe(false);
    expect(aplicaA(p("loja/botao-*"), "loja/botao-grande")).toBe(true);
    expect(aplicaA(p("loja/botao-*"), "loja/cartao")).toBe(false);
  });
  test("patch de outro alvo não aparece em nada", () => {
    const r = ap(P([{ op: "css", anexar: "a{}" }], { alvo: "loja/outro" }));
    expect(r.aplicados).toEqual([]);
    expect(r.pulados).toEqual([]);
    expect(r.componente).toEqual(base());
  });
  test("seExiste: pula quando falta, aplica quando todos existem", () => {
    const patch = P([{ op: "css", anexar: "a{}" }], { seExiste: ["mod/x", "mod/y"] });
    const pula = ap(patch, (id) => id === "mod/x");
    expect(pula.aplicados).toEqual([]);
    expect(pula.pulados[0]!.porque).toContain("mod/y");
    expect(ap(patch, () => true).aplicados).toEqual(["p.json"]);
    expect(ap(P([{ op: "css", anexar: "a{}" }], { seExiste: "mod/x" }), () => false).pulados).toHaveLength(1);
  });
  test("ordem da lista: o segundo vê o resultado do primeiro", () => {
    const r = aplicarPatches(base(), [
      { nome: "1", patch: P([{ op: "replace", path: "/dados/rotulo", value: "A" }]) },
      { nome: "2", patch: P([{ op: "test", path: "/dados/rotulo", value: "A" }, { op: "replace", path: "/dados/rotulo", value: "B" }]) },
    ], () => true);
    expect(r.componente.dados.rotulo).toBe("B");
    expect(r.aplicados).toEqual(["1", "2"]);
  });
});

describe("patches: validação", () => {
  test("válido", () => {
    expect(problemasDoPatch(P([{ op: "add", path: "/dados/x", value: 1 }, { op: "html", seletor: "b", acao: "remover" }, { op: "css", anexar: "a{}" }], { alvo: ["loja/a", "loja/*"], seExiste: "m/x" }))).toEqual([]);
  });
  test("mensagens para corrigir", () => {
    expect(problemasDoPatch(null)).toHaveLength(1);
    const m = problemasDoPatch({ alvo: "Loja/*x", ops: [
      { op: "add", path: "dados/x", value: 1 },
      { op: "replace", path: "/id", value: "a/b" },
      { op: "add", path: "/dados/x" },
      { op: "html", seletor: "b", acao: "texto" },
      { op: "html", seletor: "b", acao: "attr", valor: "1" },
      { op: "css" },
      { op: "mover" },
      { op: "add", path: "/__proto__/x", value: 1 },
    ] }).join("\n");
    for (const t of ["alvo", "ops[0]", "ops[1]", "ops[2]", "ops[3]", "ops[4]", "ops[5]", "ops[6]", "ops[7]"]) expect(m).toContain(t);
    expect(problemasDoPatch({ alvo: "a/b", ops: [] })[0]).toContain("ops");
  });
});

describe("patches: alvo com prefixo", () => {
  test('"loja/botao-*" é um alvo válido', () => {
    expect(problemasDoPatch({ alvo: "loja/botao-*", ops: [{ op: "css", anexar: "a{}" }] })).toEqual([]);
    expect(problemasDoPatch({ alvo: "loja/botao*", ops: [{ op: "css", anexar: "a{}" }] })).toEqual([]);
    expect(problemasDoPatch({ alvo: "loja/-*", ops: [{ op: "css", anexar: "a{}" }] }).length).toBeGreaterThan(0);
  });
});
