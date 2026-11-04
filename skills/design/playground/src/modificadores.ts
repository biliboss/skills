// Modificadores de um componente (o "modifier" do BEM; os Comps do RimWorld): estados ligáveis por
// instância (carregando, vazio, erro, desabilitado). O componente declara o mapa; a instância
// liga os que quer, em ordem. Só a raiz da peça (o primeiro elemento do html) recebe classe e attr.

export type Modificador = {
  descricao?: string;
  classe?: string;
  attr?: Record<string, string>;
  css?: string;
  dados?: Record<string, string | string[]>;
};

const KEBAB = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const ATTR = /^[a-zA-Z_:][-a-zA-Z0-9_:.]*$/;
const CLASSE = /^-?[_a-zA-Z][-_a-zA-Z0-9]*(\s+-?[_a-zA-Z][-_a-zA-Z0-9]*)*$/;

const ehObjeto = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object" && !Array.isArray(v);

/** Valida o mapa `modificadores` de um componente; `chaves` são as chaves de dados dele. */
export function problemasDosModificadores(v: unknown, chaves: string[]): string[] {
  if (v === undefined) return [];
  if (!ehObjeto(v)) return ["modificadores: precisa ser um objeto {nome: modificador}"];
  const p: string[] = [];
  for (const [nome, m] of Object.entries(v)) {
    const q = `modificadores.${nome}`;
    if (!KEBAB.test(nome)) p.push(`${q}: o nome precisa ser kebab-case`);
    if (!ehObjeto(m)) { p.push(`${q}: precisa ser um objeto`); continue; }
    for (const k of Object.keys(m)) {
      if (!["descricao", "classe", "attr", "css", "dados"].includes(k)) p.push(`${q}: campo desconhecido "${k}"`);
    }
    if (m.descricao !== undefined && typeof m.descricao !== "string") p.push(`${q}.descricao: precisa ser texto`);
    if (m.css !== undefined && typeof m.css !== "string") p.push(`${q}.css: precisa ser texto`);
    if (m.classe !== undefined && (typeof m.classe !== "string" || !CLASSE.test(m.classe.trim()))) {
      p.push(`${q}.classe: precisa ser um ou mais nomes de classe CSS`);
    }
    if (m.attr !== undefined) {
      if (!ehObjeto(m.attr)) p.push(`${q}.attr: precisa ser um objeto {atributo: valor}`);
      else {
        for (const [a, val] of Object.entries(m.attr)) {
          if (!ATTR.test(a)) p.push(`${q}.attr: nome de atributo inválido "${a}"`);
          else if (/^on/i.test(a)) p.push(`${q}.attr: "${a}" não é permitido (manipulador de evento)`);
          if (typeof val !== "string") p.push(`${q}.attr.${a}: o valor precisa ser texto ("" = atributo booleano)`);
        }
      }
    }
    if (m.dados !== undefined) {
      if (!ehObjeto(m.dados)) p.push(`${q}.dados: precisa ser um objeto`);
      else {
        for (const [k, val] of Object.entries(m.dados)) {
          if (!chaves.includes(k)) p.push(`${q}.dados.${k}: não é chave de dados do componente`);
          const ok = typeof val === "string" || (Array.isArray(val) && val.every((x) => typeof x === "string"));
          if (!ok) p.push(`${q}.dados.${k}: precisa ser texto ou lista de textos`);
        }
      }
    }
  }
  return p;
}

/** Valida a lista `modificadores` de uma instância contra os nomes que o componente declara. */
export function problemasDaEscolha(nomes: unknown, disponiveis: string[]): string[] {
  if (nomes === undefined) return [];
  if (!Array.isArray(nomes) || nomes.some((n) => typeof n !== "string")) {
    return ["modificadores: precisa ser uma lista de nomes"];
  }
  const p: string[] = [];
  const vistos = new Set<string>();
  for (const n of nomes as string[]) {
    if (vistos.has(n)) p.push(`modificadores: "${n}" repetido`);
    vistos.add(n);
    if (!disponiveis.includes(n)) {
      p.push(`modificadores: "${n}" não existe (disponíveis: ${disponiveis.join(", ") || "nenhum"})`);
    }
  }
  return p;
}

const escAttr = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/** Soma classe e atributos ao primeiro tag de abertura do html. */
function naRaiz(html: string, classes: string[], attrs: Record<string, string>): string {
  const m = /<([a-zA-Z][^\s/>]*)((?:"[^"]*"|'[^']*'|[^>"'])*)>/.exec(html);
  if (!m) return html;
  let resto = m[2];
  const auto = resto.trimEnd().endsWith("/");
  if (auto) resto = resto.replace(/\s*\/\s*$/, "");
  if (classes.length) {
    const re = /(\sclass\s*=\s*)(?:"([^"]*)"|'([^']*)')/i;
    const achou = re.exec(resto);
    if (achou) {
      const atual = (achou[2] ?? achou[3] ?? "").trim();
      const novo = [...new Set([...atual.split(/\s+/).filter(Boolean), ...classes])].join(" ");
      resto = resto.replace(re, `$1"${escAttr(novo)}"`);
    } else resto += ` class="${escAttr(classes.join(" "))}"`;
  }
  for (const [a, val] of Object.entries(attrs)) {
    const re = new RegExp(`\\s${a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:\\s*=\\s*(?:"[^"]*"|'[^']*'|[^\\s"'>]+))?(?=\\s|$)`, "i");
    resto = resto.replace(re, "");
    resto += val === "" ? ` ${a}` : ` ${a}="${escAttr(val)}"`;
  }
  return html.slice(0, m.index) + `<${m[1]}${resto}${auto ? " /" : ""}>` + html.slice(m.index + m[0].length);
}

/** Liga os modificadores (em ordem) a um componente: html com classe/attr na raiz, css somado e dados por baixo. */
export function aplicarModificadores(
  c: { html: string; css: string; dados: Record<string, unknown>; modificadores?: Record<string, Modificador> },
  ligados: string[],
): { html: string; css: string; dados: Record<string, unknown> } {
  const mapa = c.modificadores ?? {};
  const classes: string[] = [];
  const attrs: Record<string, string> = {};
  let css = c.css;
  let baixo: Record<string, unknown> = {};
  for (const nome of ligados) {
    const m = mapa[nome];
    if (!m) continue;
    if (m.classe) classes.push(...m.classe.trim().split(/\s+/));
    Object.assign(attrs, m.attr ?? {});
    if (m.css) css += `\n${m.css}`;
    baixo = { ...baixo, ...(m.dados ?? {}) };
  }
  return {
    html: classes.length || Object.keys(attrs).length ? naRaiz(c.html, classes, attrs) : c.html,
    css,
    dados: { ...baixo, ...c.dados }, // a instância (dados do componente + os dela) ganha
  };
}
