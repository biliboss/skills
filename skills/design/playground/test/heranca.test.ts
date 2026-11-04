import { afterEach, describe, expect, test } from "bun:test";
import { Componentes, problemaDoComponente, problemasDoComponente, type Componente } from "../src/componentes.ts";
import { pastaTemporaria, rascunho } from "./ajuda.ts";

describe("componentes: todos os problemas, herança, requer, sprite", () => {
  const limpar: (() => void)[] = [];
  afterEach(() => {
    for (const f of limpar.splice(0)) f();
  });
  function armazem(): Componentes {
    const p = pastaTemporaria();
    limpar.push(p.apagar);
    return new Componentes(p.dir);
  }
  const base = (extra: Record<string, unknown> = {}) => ({ ...rascunho("loja/base"), abstrato: true, ...extra });

  test("lista todos os problemas, e o primeiro continua disponível", () => {
    const ruim = { ...rascunho(), nome: "", estado: "tanto-faz", w: -1, slots: "x", dados: 3 };
    const todos = problemasDoComponente(ruim);
    expect(todos.length).toBeGreaterThanOrEqual(5);
    expect(problemaDoComponente(ruim)).toBe(todos[0]!);
    expect(problemasDoComponente(rascunho())).toEqual([]);
  });

  test("definir erra com um problema só ou com a lista", () => {
    const c = armazem();
    expect(() => c.definir({ ...rascunho(), nome: "" })).toThrow(/^nome ausente$/);
    let msg = "";
    try {
      c.definir({ ...rascunho(), nome: "", w: 0 });
    } catch (e) {
      msg = (e as Error).message;
    }
    expect(msg).toMatch(/^2 problemas:\n- nome ausente\n- w e h/);
  });

  test("filho herda do pai: escalares, dados, slots, css", () => {
    const c = armazem();
    c.definir(base());
    const filho = c.definir({
      id: "loja/aviso-vip",
      herda: "loja/base",
      nome: "Aviso VIP",
      css: ".vip{color:gold}",
      dados: { nome: "Zélia", extra: "x" },
      slots: [{ chave: "nome", seletor: ".nome b", como: "texto" }, { chave: "novo", seletor: ".novo", como: "texto" }],
    });
    expect(filho.html).toContain("Buscando para");
    expect(filho.w).toBe(393);
    expect(filho.css).toBe(".aviso{padding:8px}\n.vip{color:gold}");
    expect(filho.dados).toEqual({ titulo: "Buscando para", nome: "Zélia", extra: "x" });
    expect(filho.slots.map((s) => s.chave)).toEqual(["titulo", "nome", "cor", "novo"]);
    expect(filho.slots[1]!.seletor).toBe(".nome b");
    expect(filho.abstrato).toBeUndefined();
    // no disco fica como veio
    const cru = JSON.parse(require("node:fs").readFileSync(`${c.dir}/loja/aviso-vip.json`, "utf8"));
    expect(cru.herda).toBe("loja/base");
    expect(cru.html).toBeUndefined();
    expect(c.ler("loja/aviso-vip")!.w).toBe(393);
  });

  test("variantes mescladas por chave e herança em cadeia", () => {
    const c = armazem();
    c.definir(base({ variantes: { desktop: { css: "", w: 1280, h: 80 } } }));
    c.definir({ id: "loja/meio", herda: "loja/base", nome: "Meio", h: 70 });
    const neto = c.definir({ id: "loja/neto", herda: "loja/meio", nome: "Neto" });
    expect(neto.h).toBe(70);
    expect(neto.variantes!.desktop!.w).toBe(1280);
  });

  test("pai inexistente, ciclo e mensagens", () => {
    const c = armazem();
    expect(() => c.definir({ id: "loja/f", herda: "loja/nada", nome: "F" })).toThrow(/loja\/nada, que não está definido/);
    c.definir(base());
    c.definir({ id: "loja/a", herda: "loja/base", nome: "A" });
    expect(() => c.definir({ ...base(), herda: "loja/a" })).toThrow(/ciclo de herança: loja\/base -> loja\/a -> loja\/base/);
    expect(() => c.definir({ id: "loja/si", herda: "loja/si", nome: "S" })).toThrow(/ciclo/);
  });

  test("abstrato: fora do listar padrão, recusado no conferir, ainda legível", () => {
    const c = armazem();
    c.definir(base());
    c.definir({ id: "loja/f", herda: "loja/base", nome: "F" });
    expect(c.listar().map((r) => r.id)).toEqual(["loja/f"]);
    expect(c.listar(undefined, true).map((r) => [r.id, r.abstrato])).toEqual([["loja/base", true], ["loja/f", undefined]]);
    expect(c.listar(undefined, true)[1]!.herda).toBe("loja/base");
    expect(c.conferir("loja/base", undefined)).toContain("é abstrato, use um filho");
    expect(c.conferir("loja/f", undefined)).toBeNull();
    expect(c.ler("loja/base")!.abstrato).toBe(true);
  });

  test("redefinir o pai avisa os filhos (resolvidos)", () => {
    const c = armazem();
    c.definir(base());
    c.definir({ id: "loja/f", herda: "loja/base", nome: "F" });
    c.definir({ id: "loja/n", herda: "loja/f", nome: "N" });
    const avisos: Componente[] = [];
    c.aoDefinir = (x) => avisos.push(x);
    c.definir(base({ h: 99 }));
    expect(avisos.map((a) => a.id)).toEqual(["loja/base", "loja/f", "loja/n"]);
    expect(avisos[2]!.h).toBe(99);
    expect(avisos[1]!.versao).toBe(1);
  });

  test("requer: faltando é problema", () => {
    const c = armazem();
    expect(() => c.definir({ ...rascunho(), requer: ["loja/icones"] })).toThrow("requer loja/icones, que não está definido");
    c.definir(rascunho("loja/icones"));
    expect(c.definir({ ...rascunho(), requer: ["loja/icones"] }).requer).toEqual(["loja/icones"]);
  });

  test("sprite: <use> sem <symbol> é problema", () => {
    const html = '<div class="aviso"><svg><use href="#seta"/></svg><svg><use xlink:href="#lupa"></use></svg></div>';
    const sprite = '<svg><symbol id="seta" viewBox="0 0 1 1"></symbol></svg>';
    const ps = problemasDoComponente({ ...rascunho(), html, sprite });
    expect(ps).toEqual(['o html usa <use href="#lupa">, mas o sprite não tem <symbol id="lupa">']);
    expect(problemasDoComponente({ ...rascunho(), html }).length).toBe(2);
    expect(problemasDoComponente({ ...rascunho(), html, sprite: sprite.replace("</svg>", '<symbol id="lupa"></symbol></svg>') })).toEqual([]);
    expect(problemasDoComponente(rascunho())).toEqual([]);
  });

  test("o filho usa o sprite do pai", () => {
    const c = armazem();
    c.definir(base({ sprite: '<svg><symbol id="seta"></symbol></svg>' }));
    const f = c.definir({ id: "loja/f", herda: "loja/base", nome: "F", html: '<i><svg><use href="#seta"/></svg></i>' });
    expect(f.sprite).toContain("seta");
  });
});

describe("componentes: pai ausente não esconde os outros erros", () => {
  test("lista o pai que falta, o estado ruim e o requer que falta juntos", () => {
    const buscar = () => null;
    const p = problemasDoComponente({ id: "loja/ruim", nome: "", estado: "x", herda: "loja/nao-existe", requer: ["loja/falta"] }, buscar);
    expect(p.some((m) => m.includes("herda loja/nao-existe"))).toBe(true);
    expect(p.some((m) => m.includes("estado precisa ser"))).toBe(true);
    expect(p.some((m) => m.includes("nome, quando vem"))).toBe(true);
    expect(p.some((m) => m.includes("requer loja/falta"))).toBe(true);
  });
});
