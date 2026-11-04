import { describe, expect, test } from "bun:test";
import { aplicarModificadores, problemasDaEscolha, problemasDosModificadores } from "../src/modificadores.ts";

const mapa = {
  desabilitado: { classe: "is-off", attr: { disabled: "", "aria-disabled": "true" }, css: ".is-off{opacity:.5}", dados: { rotulo: "Indisponível" } },
  carregando: { classe: "is-loading", dados: { rotulo: "Carregando…" } },
};
const base = { html: '<button class="btn" data-x=\'1\'>ok</button>', css: ".btn{}", dados: { rotulo: "Salvar" }, modificadores: mapa };

describe("problemasDosModificadores", () => {
  test("mapa válido e ausente", () => {
    expect(problemasDosModificadores(mapa, ["rotulo"])).toEqual([]);
    expect(problemasDosModificadores(undefined, [])).toEqual([]);
  });
  test("acusa nome, campo, attr e chave de dados", () => {
    const p = problemasDosModificadores({ Ruim_Nome: { dados: { x: "a" }, attr: { onclick: "a()" }, foo: 1 } }, ["rotulo"]);
    expect(p.join("\n")).toMatch(/kebab-case/);
    expect(p.join("\n")).toMatch(/campo desconhecido "foo"/);
    expect(p.join("\n")).toMatch(/onclick/);
    expect(p.join("\n")).toMatch(/dados\.x: não é chave/);
  });
  test("não-objeto", () => {
    expect(problemasDosModificadores([], [])).toHaveLength(1);
    expect(problemasDosModificadores({ a: 3 }, [])).toHaveLength(1);
  });
});

describe("problemasDaEscolha", () => {
  test("ok, desconhecido, repetido, formato", () => {
    expect(problemasDaEscolha(["carregando"], ["carregando"])).toEqual([]);
    expect(problemasDaEscolha(["x"], ["carregando"])[0]).toMatch(/não existe/);
    expect(problemasDaEscolha(["a", "a"], ["a"])[0]).toMatch(/repetido/);
    expect(problemasDaEscolha("a", ["a"])).toHaveLength(1);
  });
});

describe("aplicarModificadores", () => {
  test("sem ligados nada muda", () => {
    expect(aplicarModificadores(base, [])).toEqual({ html: base.html, css: base.css, dados: base.dados });
  });
  test("classe somada, attr booleano e valorado só na raiz", () => {
    const r = aplicarModificadores({ ...base, html: '<div class="a"><button class="btn">x</button></div>' }, ["desabilitado"]);
    expect(r.html).toBe('<div class="a is-off" disabled aria-disabled="true"><button class="btn">x</button></div>');
  });
  test("raiz sem class; attr existente é substituído", () => {
    const r = aplicarModificadores({ ...base, html: '<button disabled="no">x</button>' }, ["desabilitado"]);
    expect(r.html).toBe('<button class="is-off" disabled aria-disabled="true">x</button>');
  });
  test("css depois do da peça; dados da instância ganham dos do modificador", () => {
    const r = aplicarModificadores(base, ["carregando", "desabilitado"]);
    expect(r.css.indexOf(".btn{}")).toBeLessThan(r.css.indexOf(".is-off"));
    expect(r.dados.rotulo).toBe("Salvar");
    const sem = aplicarModificadores({ ...base, dados: {} }, ["carregando", "desabilitado"]);
    expect(sem.dados.rotulo).toBe("Indisponível"); // o último ligado vence entre modificadores
  });
  test("nome desconhecido é ignorado; tag autofechada", () => {
    const r = aplicarModificadores({ ...base, html: '<input type="text" />' }, ["nada", "carregando"]);
    expect(r.html).toBe('<input type="text" class="is-loading" />');
  });
});
