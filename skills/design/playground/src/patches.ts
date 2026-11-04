/**
 * Patches de componente (como as PatchOperations do RimWorld): um mod não
 * reescreve o Def de outro, aplica operações num caminho. O patch é
 * declarativo, vive fora da pasta do wrapper (o build apaga a pasta) e é
 * reaplicado a cada leitura. Este módulo é puro: não lê disco e não muda a
 * entrada (trabalha num structuredClone).
 */

export type OpJson =
  | { op: "add" | "replace"; path: string; value: unknown }
  | { op: "remove"; path: string }
  | { op: "test"; path: string; value: unknown };
export type AcaoHtml = "remover" | "texto" | "attr" | "classe" | "antes" | "depois";
export type OpHtml = { op: "html"; seletor: string; acao: AcaoHtml; valor?: string; nome?: string };
export type OpCss = { op: "css"; anexar: string };
export type Op = OpJson | OpHtml | OpCss;
export type Patch = { alvo: string | string[]; seExiste?: string | string[]; porque?: string; ops: Op[] };

export type ResultadoPatches<T> = {
  componente: T;
  aplicados: string[];
  pulados: { nome: string; porque: string }[];
  erros: { nome: string; erro: string }[];
};

const ACOES: AcaoHtml[] = ["remover", "texto", "attr", "classe", "antes", "depois"];
const ID_ALVO = /^[a-z0-9]+(?:-[a-z0-9]+)*\/(?:[a-z0-9]+(?:-[a-z0-9]+)*)?\*?$|^[a-z0-9]+(?:-[a-z0-9]+)*\/\*$/;
const ID_COMP = /^[a-z0-9]+(?:-[a-z0-9]+)*\/[a-z0-9]+(?:-[a-z0-9]+)*$/;

const ehObjeto = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const ehTexto = (v: unknown): v is string => typeof v === "string" && v.length > 0;

// ---------- validação ----------

function pointerValido(p: unknown): string | null {
  if (typeof p !== "string" || !p.startsWith("/") || p === "/") return `path ${JSON.stringify(p)} precisa ser um JSON Pointer começando com "/", ex.: "/dados/rotulo"`;
  const partes = p.slice(1).split("/").map(desescapa);
  if (partes.some((x) => x === "__proto__" || x === "constructor" || x === "prototype")) return `path ${p} usa um segmento proibido`;
  if (partes[0] === "id") return `path ${p}: o id do componente não muda por patch`;
  if (partes[0] === "versao") return `path ${p}: a versão é do sistema, não do patch`;
  return null;
}

/** Os problemas do valor como patch (lista vazia = válido). Mensagens para o modelo corrigir. */
export function problemasDoPatch(v: unknown): string[] {
  if (!ehObjeto(v)) return ["o patch precisa ser um objeto JSON { alvo, ops }"];
  const out: string[] = [];
  const alvos = typeof v.alvo === "string" ? [v.alvo] : Array.isArray(v.alvo) ? v.alvo : null;
  if (!alvos || alvos.length === 0) out.push('alvo ausente: use "loja/botao", ["loja/a","loja/b"] ou "loja/*"');
  else for (const a of alvos) if (typeof a !== "string" || !ID_ALVO.test(a)) out.push(`alvo ${JSON.stringify(a)} inválido: "<produto>/<peça>" em kebab-case; "*" só no fim da peça (ex.: "loja/*", "loja/botao-*")`);
  if (v.seExiste !== undefined) {
    const l = typeof v.seExiste === "string" ? [v.seExiste] : Array.isArray(v.seExiste) ? v.seExiste : null;
    if (!l || l.some((x) => typeof x !== "string" || !ID_COMP.test(x))) out.push('seExiste precisa ser um id "<produto>/<peça>" ou uma lista deles');
  }
  if (v.porque !== undefined && typeof v.porque !== "string") out.push("porque, quando vem, precisa ser texto");
  if (!Array.isArray(v.ops) || v.ops.length === 0) { out.push("ops precisa ser uma lista não vazia"); return out; }
  v.ops.forEach((o, i) => {
    const q = (m: string) => out.push(`ops[${i}]: ${m}`);
    if (!ehObjeto(o)) return q("precisa ser um objeto { op, ... }");
    switch (o.op) {
      case "add": case "replace": case "test": {
        const e = pointerValido(o.path); if (e) q(e);
        if (!("value" in o)) q(`${o.op} precisa de value`);
        break;
      }
      case "remove": { const e = pointerValido(o.path); if (e) q(e); break; }
      case "html": {
        if (!ehTexto(o.seletor)) q("html precisa de seletor (CSS)");
        if (!ACOES.includes(o.acao as AcaoHtml)) q(`acao precisa ser uma de ${ACOES.join(", ")}`);
        else {
          if (o.acao !== "remover" && o.acao !== "attr" && typeof o.valor !== "string") q(`acao "${o.acao}" precisa de valor (texto)`);
          if (o.acao === "attr" && (!ehTexto(o.nome) || typeof o.valor !== "string")) q('acao "attr" precisa de nome e valor');
          if (o.acao === "classe" && !ehTexto(o.valor)) q('acao "classe" precisa de valor (a classe)');
        }
        break;
      }
      case "css": if (typeof o.anexar !== "string" || !o.anexar.trim()) q("css precisa de anexar (texto não vazio)"); break;
      default: q(`op ${JSON.stringify(o.op)} desconhecida: use add, replace, remove, test, html ou css`);
    }
  });
  return out;
}

// ---------- alvo ----------

/** O id casa com o alvo? "*" vale só no fim do segmento da peça ("loja/*", "loja/botao-*"). */
export function aplicaA(p: Patch, id: string): boolean {
  const alvos = Array.isArray(p.alvo) ? p.alvo : [p.alvo];
  const [prod, peca = ""] = id.split("/");
  return alvos.some((a) => {
    const i = a.indexOf("/");
    if (i < 0) return false;
    const ap = a.slice(0, i), ape = a.slice(i + 1);
    if (ap !== prod) return false;
    return ape.endsWith("*") ? peca.startsWith(ape.slice(0, -1)) : ape === peca;
  });
}

// ---------- JSON Pointer ----------

function desescapa(s: string): string { return s.replace(/~1/g, "/").replace(/~0/g, "~"); }

class FalhaOp extends Error {}
class TesteFalhou extends Error {}

type Pai = { pai: any; chave: string };
function acharPai(raiz: unknown, path: string): Pai {
  const partes = path.slice(1).split("/").map(desescapa);
  let atual: any = raiz;
  for (let i = 0; i < partes.length - 1; i++) {
    const k = partes[i]!;
    if (Array.isArray(atual)) {
      if (!/^(0|[1-9]\d*)$/.test(k) || Number(k) >= atual.length) throw new FalhaOp(`o caminho ${path} não existe (falta "${k}")`);
      atual = atual[Number(k)];
    } else if (ehObjeto(atual) && Object.hasOwn(atual, k)) atual = atual[k];
    else throw new FalhaOp(`o caminho ${path} não existe (falta "${k}")`);
    if (typeof atual !== "object" || atual === null) throw new FalhaOp(`o caminho ${path} passa por um valor que não é objeto nem lista`);
  }
  return { pai: atual, chave: partes[partes.length - 1]! };
}
function existe({ pai, chave }: Pai): boolean {
  if (Array.isArray(pai)) return /^(0|[1-9]\d*)$/.test(chave) && Number(chave) < pai.length;
  return ehObjeto(pai) && Object.hasOwn(pai, chave);
}
function igual(a: unknown, b: unknown): boolean { return Bun.deepEquals(a, b, true); }

function opJson(c: any, o: OpJson): void {
  const p = acharPai(c, o.path);
  if (o.op === "add") {
    const v = structuredClone(o.value);
    if (Array.isArray(p.pai)) {
      if (p.chave === "-") p.pai.push(v);
      else if (/^(0|[1-9]\d*)$/.test(p.chave) && Number(p.chave) <= p.pai.length) p.pai.splice(Number(p.chave), 0, v);
      else throw new FalhaOp(`add: índice ${p.chave} fora da lista em ${o.path}`);
    } else p.pai[p.chave] = v;
    return;
  }
  if (!existe(p)) throw new FalhaOp(`${o.op}: o caminho ${o.path} não existe`);
  if (o.op === "test") {
    if (!igual(p.pai[p.chave], o.value)) throw new TesteFalhou(`test em ${o.path} não bateu`);
  } else if (o.op === "replace") p.pai[p.chave] = structuredClone(o.value);
  else if (Array.isArray(p.pai)) p.pai.splice(Number(p.chave), 1);
  else delete p.pai[p.chave];
}

// ---------- html ----------

function reescreve(html: string, o: OpHtml): { html: string; achou: number } {
  let achou = 0;
  const valor = o.valor ?? "";
  const r = new HTMLRewriter().on(o.seletor, {
    element(el) {
      achou++;
      switch (o.acao) {
        case "remover": el.remove(); break;
        case "texto": el.setInnerContent(valor); break;
        case "attr": el.setAttribute(o.nome!, valor); break;
        case "classe": { const a = el.getAttribute("class"); el.setAttribute("class", a ? `${a} ${valor}` : valor); break; }
        case "antes": el.before(valor, { html: true }); break;
        case "depois": el.after(valor, { html: true }); break;
      }
    },
  });
  const saida = r.transform(html) as unknown;
  if (typeof saida !== "string") throw new FalhaOp("o HTMLRewriter não devolveu texto nesta versão do Bun");
  return { html: saida, achou };
}

function opHtml(c: any, o: OpHtml, id: string): void {
  let total = 0;
  try {
    for (const alvo of [c, c.variantes?.desktop]) {
      if (!alvo || typeof alvo.html !== "string") continue;
      const r = reescreve(alvo.html, o);
      alvo.html = r.html;
      total += r.achou;
    }
  } catch (e) {
    if (e instanceof FalhaOp) throw e;
    throw new FalhaOp(`seletor "${o.seletor}" inválido: ${(e as Error).message}`);
  }
  if (total === 0) throw new FalhaOp(`o seletor ${o.seletor} não achou nada em ${id}`);
}

function opCss(c: any, o: OpCss): void {
  const soma = (css: unknown) => `${typeof css === "string" ? css : ""}${typeof css === "string" && css && !css.endsWith("\n") ? "\n" : ""}${o.anexar}`;
  c.css = soma(c.css);
  if (c.variantes?.desktop) c.variantes.desktop.css = soma(c.variantes.desktop.css);
}

// ---------- aplicar ----------

export function aplicarPatches<T extends { id: string }>(
  c: T,
  patches: { nome: string; patch: Patch }[],
  existeComponente: (id: string) => boolean,
): ResultadoPatches<T> {
  let atual = structuredClone(c);
  const aplicados: string[] = [];
  const pulados: { nome: string; porque: string }[] = [];
  const erros: { nome: string; erro: string }[] = [];
  for (const { nome, patch } of patches) {
    if (!aplicaA(patch, c.id)) continue;
    const exige = patch.seExiste === undefined ? [] : typeof patch.seExiste === "string" ? [patch.seExiste] : patch.seExiste;
    const falta = exige.find((id) => !existeComponente(id));
    if (falta) { pulados.push({ nome, porque: `seExiste: ${falta} não existe` }); continue; }
    const copia = structuredClone(atual);
    let i = 0;
    try {
      for (; i < patch.ops.length; i++) {
        const o = patch.ops[i]!;
        if (o.op === "html") opHtml(copia, o, c.id);
        else if (o.op === "css") opCss(copia, o);
        else opJson(copia, o);
      }
      atual = copia;
      aplicados.push(nome);
    } catch (e) {
      if (e instanceof TesteFalhou) pulados.push({ nome, porque: `ops[${i}]: ${e.message}` });
      else erros.push({ nome, erro: `ops[${i}]: ${(e as Error).message}` });
    }
  }
  return { componente: atual, aplicados, pulados, erros };
}
