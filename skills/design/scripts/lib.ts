// O que serve a qualquer produto: o tipo do wrapper, o CSS resolvido por largura,
// a leitura do repo do produto pelo git (só leitura, no origin/main) e a medida
// de uma peça num shadow DOM, como a forma `widget` do design-playground a desenha.

import { chromium, type Browser } from "playwright-core";
import { $ } from "bun";

export type Slot = { chave: string; seletor: string; como: string };
export type Fonte = { repo: string; arquivo: string; simbolo?: string; commit: string; receita: "executar" | "copiar" };
export type Componente = {
  id: string; nome: string; descricao: string;
  estado: "rascunho" | "real";
  html?: string; css?: string;
  w: number; h: number;
  variantes?: { desktop?: { html?: string; css?: string; w: number; h: number } };
  slots: Slot[];
  dados: Record<string, string | string[]>;
  fonte?: Fonte;
  fontes?: string[];
  sprite?: string;
};

/** O que a receita de um produto devolve por peça; o wrapper.ts grava. */
export type Peca = {
  id: string; nome: string; descricao: string; slots: Slot[];
  html: string; dados: Record<string, string | string[]>;
  css: string; desktopCss: string; sprite?: string; fontes?: string[];
  fonte: Omit<Fonte, "commit" | "repo">;
  /** por que copiar, quando a receita é "copiar" */
  porque?: string;
};

/** O repo do produto, só leitura: tudo sai do `origin/<ramo>`, nada muda no checkout. */
export class Repo {
  constructor(public dir: string, public remoto: string, public ramo = "main") {}
  get ref() { return `origin/${this.ramo}`; }
  async buscar() { await $`git -C ${this.dir} fetch -q origin ${this.ramo}`.quiet().nothrow(); }
  async commit(ref = this.ref) { return (await $`git -C ${this.dir} rev-parse ${ref}`.text()).trim(); }
  async ler(arquivo: string, ref = this.ref) { return await $`git -C ${this.dir} show ${ref}:${arquivo}`.quiet().text(); }
  /** o arquivo mudou entre dois commits? (o diff só daquele caminho) */
  async mudou(arquivo: string, de: string, ate = this.ref) {
    const r = await $`git -C ${this.dir} diff --quiet ${de} ${ate} -- ${arquivo}`.quiet().nothrow();
    return r.exitCode !== 0;
  }
  async atras(de: string, ate = this.ref) {
    return Number((await $`git -C ${this.dir} rev-list --count ${de}..${ate}`.text()).trim());
  }
}

/**
 * Resolve as media queries de largura para uma largura fixa: num shadow DOM a media query
 * olha a janela do canvas, não a peça. `(min-width:N)`/`(max-width:N)` sozinhas: o bloco
 * sai quando não vale e perde o invólucro (fica no mesmo lugar) quando vale. As outras
 * (hover, prefers-reduced-motion…) ficam como estão.
 */
export function resolverCss(css: string, largura: number): { css: string; tirados: string[]; abertos: string[] } {
  const tirados: string[] = [], abertos: string[] = [];
  let saida = "", i = 0;
  const re = /@media\s*\(\s*(min|max)-width\s*:\s*(\d+)px\s*\)\s*\{/g;
  for (let m = re.exec(css); m; m = re.exec(css)) {
    const n = Number(m[2]);
    const vale = m[1] === "min" ? largura >= n : largura <= n;
    let prof = 1, j = m.index + m[0].length;
    while (j < css.length && prof > 0) { if (css[j] === "{") prof++; else if (css[j] === "}") prof--; j++; }
    const rotulo = m[0].replace(/\s*\{$/, "");
    saida += css.slice(i, m.index);
    if (vale) { saida += css.slice(m.index + m[0].length, j - 1); abertos.push(rotulo); }
    else tirados.push(rotulo);
    i = j;
    re.lastIndex = j;
  }
  return { css: saida + css.slice(i), tirados, abertos };
}

export const CELULAR = 393;
export const DESKTOP = 1280;

export async function abrirChrome(): Promise<Browser> {
  return chromium.launch({ channel: "chrome", headless: true });
}

/** `:root` → `:host`, como a forma `widget` faz ao pôr o CSS no shadow DOM. */
export const paraHost = (css: string) => css.replace(/:root((?:\[[^\]]*\])+)/g, ":host($1)").replace(/:root\b/g, ":host");

/**
 * Desenha cada peça num shadow DOM (`:root` → `:host`, o sprite, `display:flow-root`)
 * na largura pedida e devolve a altura natural. `foto` grava um PNG por peça.
 */
export async function medir(
  browser: Browser,
  pecas: { id: string; html: string; css: string; sprite?: string; fontes?: string[]; dados?: Record<string, string | string[]>; slots?: Slot[] }[],
  largura: number,
  foto?: (id: string) => string,
): Promise<Record<string, number>> {
  const p = await browser.newPage({ viewport: { width: Math.max(largura, 1280), height: 900 }, deviceScaleFactor: 2 });
  const fontes = [...new Set(pecas.flatMap((x) => x.fontes ?? []))];
  await p.setContent(`<!doctype html><html><head><meta charset="utf-8">${fontes.map((f) => `<link rel="stylesheet" href="${f}">`).join("")}</head><body style="margin:0;background:#fff"></body></html>`, { waitUntil: "load" });
  const out: Record<string, number> = {};
  for (const x of pecas) {
    const h = await p.evaluate(async ({ html, css, sprite, largura, dados, slots }) => {
      await document.fonts.load("600 15px Manrope").catch(() => {});
      document.body.replaceChildren();
      const host = document.createElement("div");
      host.id = "host";
      host.style.width = `${largura}px`;
      document.body.append(host);
      const raiz = host.attachShadow({ mode: "open" });
      const folha = new CSSStyleSheet();
      folha.replaceSync(css);
      // as @font-face não valem dentro do shadow DOM
      for (const r of [...folha.cssRules]) if (r instanceof CSSFontFaceRule) { const d = new CSSStyleSheet(); d.replaceSync(r.cssText); document.adoptedStyleSheets = [...document.adoptedStyleSheets, d]; }
      const base = new CSSStyleSheet();
      base.replaceSync(":host{display:block}.w-sprite{position:absolute;width:0;height:0;overflow:hidden}.w-corpo{display:flow-root}");
      raiz.adoptedStyleSheets = [base, folha];
      raiz.innerHTML = `<div class="w-sprite" aria-hidden="true">${sprite ?? ""}</div><div class="w-corpo">${html}</div>`;
      const corpo = raiz.querySelector(".w-corpo") as HTMLElement;
      if (dados && slots) aplicar(corpo, slots, dados);
      await Promise.all([...raiz.querySelectorAll("img")].map((i) => (i as HTMLImageElement).decode().catch(() => {})));
      await document.fonts.ready;
      return Math.round(corpo.getBoundingClientRect().height);
      // o mesmo aplicarDados da forma `widget` (web/widgets.js do design-playground)
      function aplicar(r: Element, ss: { chave: string; seletor: string; como: string }[], d: Record<string, unknown>) {
        const txt = (v: unknown) => (Array.isArray(v) ? v.join(" ") : String(v ?? ""));
        for (const s of ss) {
          if (!(s.chave in d)) continue;
          const v = d[s.chave];
          if (s.como === "lista") {
            const todos = [...r.querySelectorAll(s.seletor)];
            if (!todos.length) continue;
            const modelo = todos[0];
            for (const o of todos.slice(1)) if (o.parentNode === modelo.parentNode) o.remove();
            const itens = Array.isArray(v) ? v : [v];
            modelo.replaceWith(...itens.map((item) => {
              const c = modelo.cloneNode(true) as Element;
              const alvos = c.matches("[data-texto]") ? [c] : [...c.querySelectorAll("[data-texto]")];
              if (alvos.length) { const partes = String(item ?? "").split(" | "); alvos.forEach((e, i) => { e.textContent = partes[i] ?? ""; }); }
              else c.textContent = String(item ?? "");
              return c;
            }));
            continue;
          }
          const e = r.querySelector(s.seletor) as HTMLElement | null;
          if (!e) continue;
          if (s.como === "texto") e.textContent = txt(v);
          else if (s.como === "html") e.innerHTML = txt(v);
          else if (s.como.startsWith("attr:")) e.setAttribute(s.como.slice(5), txt(v));
          else if (s.como.startsWith("estilo:")) e.style.setProperty(s.como.slice(7), txt(v));
        }
      }
    }, { html: x.html, css: paraHost(x.css), sprite: x.sprite, largura, dados: x.dados, slots: x.slots });
    out[x.id] = h;
    if (foto) await p.locator("#host").screenshot({ path: foto(x.id), animations: "disabled" });
  }
  await p.close();
  return out;
}
