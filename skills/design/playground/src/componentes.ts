/**
 * Os componentes (CONTRATO.md, "Componentes e instâncias"): as definições que
 * chegam de fora, de um wrapper da skill `design` (uma pasta) ou do JSON de um
 * rascunho. Valida o tipo `Componente`, lê a pasta do wrapper sem sair dela e
 * guarda a cópia em <dadosDir>/componentes/<produto>/<peça>.json com a
 * `versao` (+1 a cada definição). A cópia é cache; a verdade é a pasta da skill.
 */
import { existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, statSync, writeFileSync } from "node:fs";
import { isAbsolute, join, sep } from "node:path";
import { log } from "./tipos.ts";

export type Slot = { chave: string; seletor: string; como: string };
export type Dados = Record<string, string | string[]>;
export type Variante = { html?: string; css: string; w: number; h: number };
export type Fonte = { repo: string; arquivo: string; simbolo?: string; commit: string; receita: "executar" | "copiar" };
export type Componente = {
  id: string;
  nome: string;
  descricao: string;
  estado: "rascunho" | "real";
  versao: number;
  html: string;
  css: string;
  w: number;
  h: number;
  variantes?: { desktop?: Variante };
  slots: Slot[];
  dados: Dados;
  fonte?: Fonte;
  fontes?: string[];
  sprite?: string;
  /** "<produto>/<peça>" do pai: o que o filho não diz vem dele (Abstract + ParentName do RimWorld). */
  herda?: string;
  /** Base para herdar: não aparece no listar padrão e não se instancia. */
  abstrato?: boolean;
  /** Ids de componentes que precisam estar definidos (o About.xml). */
  requer?: string[];
};
/** O que o wrapper (ou o agente) manda: tudo menos a `versao`, que o MCP dá. */
export type DefinicaoComponente = Omit<Componente, "versao">;

/** Um pedaço kebab-case: letras minúsculas e números, separados por um hífen. */
const KEBAB = "[a-z0-9]+(?:-[a-z0-9]+)*";
/** `<produto>/<peça>`, os dois em kebab-case: "loja/cartao-produto". */
export const ID_COMPONENTE = new RegExp(`^${KEBAB}/${KEBAB}$`);
export const COMO_VALIDO = /^(?:texto|html|lista|attr:[A-Za-z_:][-\w:.]*|estilo:-{0,2}[A-Za-z][-\w]*)$/;
/** O maior arquivo que a pasta de um wrapper pode ter (o CSS real de um produto passa de 70 KB). */
const MAIOR_ARQUIVO = 4 * 1024 * 1024;

/** Os arquivos de papel fixo na pasta do wrapper, lidos quando o campo falta no JSON. */
export const ARQUIVOS_DO_WRAPPER = {
  json: "componente.json",
  html: "peca.html",
  css: "peca.css",
  desktop: "desktop.css",
  sprite: "sprite.svg",
} as const;

// ---------- validação ----------

function ehObjeto(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
const ehTexto = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;
const ehListaDeTextos = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");
const ehMedida = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v > 0 && v <= 20_000;

function problemaDaVariante(v: unknown, onde: string): string | null {
  if (!ehObjeto(v)) return `${onde} precisa ser um objeto { css, w, h, html? }`;
  if (typeof v.css !== "string") return `${onde}.css ausente (ou ponha um desktop.css na pasta do wrapper)`;
  if (v.html !== undefined && !ehTexto(v.html)) return `${onde}.html, quando vem, precisa ser texto`;
  if (!ehMedida(v.w) || !ehMedida(v.h)) return `${onde}.w e .h precisam ser números positivos`;
  return null;
}

/** Procura a definição crua (como foi guardada, com `herda`) de um id; null se não existe. */
export type Buscar = (id: string) => Record<string, unknown> | null;

/** Mescla o filho sobre o pai resolvido (o RimWorld: Abstract + ParentName). */
function mesclar(pai: Record<string, unknown>, filho: Record<string, unknown>): Record<string, unknown> {
  const saida: Record<string, unknown> = { ...pai };
  for (const [k, val] of Object.entries(filho)) if (val !== undefined) saida[k] = val;
  saida.id = filho.id;
  saida.abstrato = filho.abstrato;
  if (typeof pai.css === "string" && typeof filho.css === "string") saida.css = `${pai.css}\n${filho.css}`;
  if (ehObjeto(pai.dados) && ehObjeto(filho.dados)) saida.dados = { ...pai.dados, ...filho.dados };
  if (ehObjeto(pai.variantes) && ehObjeto(filho.variantes)) saida.variantes = { ...pai.variantes, ...filho.variantes };
  const slotsOk = (l: unknown): l is Record<string, unknown>[] => Array.isArray(l) && l.every(ehObjeto);
  if (slotsOk(pai.slots) && slotsOk(filho.slots)) {
    const novos = filho.slots;
    const trocados = pai.slots.map((s) => novos.find((n) => n.chave === s.chave) ?? s);
    saida.slots = [...trocados, ...novos.filter((n) => !(pai.slots as Record<string, unknown>[]).some((s) => s.chave === n.chave))];
  }
  if (Array.isArray(pai.requer) || Array.isArray(filho.requer)) {
    const lista = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
    saida.requer = [...new Set([...lista(pai.requer), ...lista(filho.requer)])];
  }
  return saida;
}

/** Resolve a herança de uma definição crua: o resultado e os problemas (ciclo, pai ausente). */
export function resolverHeranca(v: Record<string, unknown>, buscar?: Buscar): { resolvido: Record<string, unknown>; problemas: string[] } {
  const cadeia: Record<string, unknown>[] = [v];
  const vistos = [String(v.id)];
  let atual = v;
  while (atual.herda !== undefined) {
    const h = atual.herda;
    const de = atual === v ? "herda" : `herda (de ${String(atual.id)})`;
    if (typeof h !== "string" || !ID_COMPONENTE.test(h)) {
      return { resolvido: v, problemas: [`${de} inválido ${JSON.stringify(h)}: use "<produto>/<peça>" em kebab-case`] };
    }
    if (vistos.includes(h)) return { resolvido: v, problemas: [`ciclo de herança: ${[...vistos, h].join(" -> ")}`] };
    if (!buscar) return { resolvido: v, problemas: [`herda ${h}, mas não há armazém para procurar o pai`] };
    const pai = buscar(h);
    if (!pai) return { resolvido: v, problemas: [`herda ${h}, que não está definido (defina o pai antes do filho)`] };
    vistos.push(h);
    cadeia.push(pai);
    atual = pai;
  }
  let r = cadeia[cadeia.length - 1]!;
  for (let i = cadeia.length - 2; i >= 0; i--) r = mesclar(r, cadeia[i]!);
  return { resolvido: r, problemas: [] };
}

/** Os símbolos que o html pede com `<use href="#x">` e que o sprite não tem. */
function simbolosFaltando(htmls: (string | undefined)[], sprite: unknown): string[] {
  const usados = new Set<string>();
  for (const h of htmls) {
    if (typeof h !== "string") continue;
    for (const m of h.matchAll(/<use\b[^>]*?\b(?:xlink:)?href\s*=\s*["']#([^"']+)["']/gi)) usados.add(m[1]!);
  }
  if (usados.size === 0) return [];
  const tem = new Set<string>();
  if (typeof sprite === "string") for (const m of sprite.matchAll(/<symbol\b[^>]*?\bid\s*=\s*["']([^"']+)["']/gi)) tem.add(m[1]!);
  return [...usados].filter((id) => !tem.has(id));
}

/** Todos os problemas de uma definição já resolvida (sem a herança), na ordem em que o contrato pede. */
function problemasDoResolvido(v: Record<string, unknown>): string[] {
  const p: string[] = [];
  if (!ehTexto(v.nome)) p.push("nome ausente");
  if (typeof v.descricao !== "string") p.push("descricao ausente (para que serve a peça)");
  if (v.estado !== "rascunho" && v.estado !== "real") p.push('estado precisa ser "rascunho" ou "real"');
  else if (v.estado === "real" && v.fonte === undefined) {
    p.push('estado "real" exige fonte { repo, arquivo, simbolo?, commit, receita }: de onde no código do produto a peça saiu. Sem fonte, use estado "rascunho".');
  } else if (v.estado === "rascunho" && v.fonte !== undefined) {
    p.push('um rascunho não tem fonte: tire o campo fonte, ou use estado "real" se a peça já existe no código do produto');
  }
  if (!ehTexto(v.html)) p.push("html ausente (ou ponha um peca.html na pasta do wrapper)");
  if (typeof v.css !== "string") p.push('css ausente (ou ponha um peca.css na pasta do wrapper); use "" se a peça não tem CSS');
  if (!ehMedida(v.w) || !ehMedida(v.h)) p.push("w e h precisam ser números positivos (o tamanho natural no celular, 393 de largura)");
  if (v.variantes !== undefined) {
    if (!ehObjeto(v.variantes)) p.push("variantes precisa ser um objeto { desktop? }");
    else {
      const estranhas = Object.keys(v.variantes).filter((k) => k !== "desktop");
      if (estranhas.length > 0) p.push(`variantes só aceita "desktop" (veio ${estranhas.join(", ")})`);
      if (v.variantes.desktop !== undefined) {
        const pv = problemaDaVariante(v.variantes.desktop, "variantes.desktop");
        if (pv) p.push(pv);
      }
    }
  }
  if (!Array.isArray(v.slots)) p.push("slots precisa ser uma lista (pode ser vazia)");
  else {
    for (const [i, s] of v.slots.entries()) {
      const onde = `slots[${i}]`;
      if (!ehObjeto(s) || !ehTexto(s.chave) || !ehTexto(s.seletor)) p.push(`${onde} precisa de chave e seletor`);
      else if (typeof s.como !== "string" || !COMO_VALIDO.test(s.como)) {
        p.push(`${onde}.como inválido: use texto, html, lista, attr:<atributo> ou estilo:<propriedade>`);
      }
    }
  }
  if (!ehObjeto(v.dados)) p.push("dados precisa ser um objeto chave → texto (ou lista de textos)");
  else {
    for (const [chave, valor] of Object.entries(v.dados)) {
      if (typeof valor !== "string" && !ehListaDeTextos(valor)) p.push(`dados.${chave} precisa ser texto ou lista de textos`);
    }
  }
  if (v.fonte !== undefined) {
    const f = v.fonte;
    if (!ehObjeto(f)) p.push("fonte precisa ser um objeto { repo, arquivo, simbolo?, commit, receita }");
    else {
      if (!ehTexto(f.repo) || !ehTexto(f.arquivo) || !ehTexto(f.commit)) p.push("fonte precisa de repo, arquivo e commit");
      if (f.simbolo !== undefined && !ehTexto(f.simbolo)) p.push("fonte.simbolo, quando vem, precisa ser texto");
      if (f.receita !== "executar" && f.receita !== "copiar") p.push('fonte.receita precisa ser "executar" ou "copiar"');
    }
  }
  if (v.fontes !== undefined && !ehListaDeTextos(v.fontes)) p.push("fontes precisa ser uma lista de URLs de folhas de estilo");
  if (v.sprite !== undefined && typeof v.sprite !== "string") p.push("sprite precisa ser o SVG (texto) com os <symbol>");
  if (v.abstrato !== undefined && typeof v.abstrato !== "boolean") p.push("abstrato precisa ser true ou false");
  if (v.requer !== undefined && !ehListaDeTextos(v.requer)) p.push("requer precisa ser uma lista de ids de componente");
  const desktop = ehObjeto(v.variantes) && ehObjeto(v.variantes.desktop) ? v.variantes.desktop.html : undefined;
  for (const id of simbolosFaltando([typeof v.html === "string" ? v.html : undefined, typeof desktop === "string" ? desktop : undefined], v.sprite)) {
    p.push(`o html usa <use href="#${id}">, mas o sprite não tem <symbol id="${id}">`);
  }
  return p;
}

/**
 * TODOS os problemas do valor como definição de componente (sem olhar a
 * `versao`, que o MCP dá), como o RimWorld lista cada config error na carga;
 * lista vazia se casa com o contrato. Com `herda`, a validação olha o
 * resultado resolvido, e `buscar` acha os pais e os `requer`. A mensagem é
 * para o modelo ler e corrigir.
 */
export function problemasDoComponente(v: unknown, buscar?: Buscar): string[] {
  if (!ehObjeto(v)) return ["o componente precisa ser um objeto JSON"];
  if (typeof v.id !== "string" || !ID_COMPONENTE.test(v.id)) {
    return [`id inválido ${JSON.stringify(v.id)}: use "<produto>/<peça>" em kebab-case, ex.: "loja/cartao-produto"`];
  }
  const { resolvido, problemas } = resolverHeranca(v, buscar);
  if (problemas.length > 0) return problemas;
  const todos = problemasDoResolvido(resolvido);
  if (ehListaDeTextos(v.requer) && buscar) {
    for (const r of v.requer) {
      if (r === v.id) continue;
      if (!ID_COMPONENTE.test(r)) todos.push(`requer ${JSON.stringify(r)} não é um id "<produto>/<peça>"`);
      else if (!buscar(r)) todos.push(`requer ${r}, que não está definido`);
    }
  }
  return todos;
}

/** O primeiro problema da definição, ou null (compatibilidade). */
export function problemaDoComponente(v: unknown, buscar?: Buscar): string | null {
  return problemasDoComponente(v, buscar)[0] ?? null;
}

/** Só os campos do contrato, na ordem dele (o que vier a mais fica de fora). Aceita a definição crua, com campos faltando. */
function limpar(v: Record<string, unknown>, versao: number): Componente {
  const c = v as unknown as Partial<DefinicaoComponente>;
  const saida: Record<string, unknown> = { id: c.id, nome: c.nome, descricao: c.descricao, estado: c.estado, versao };
  if (c.herda !== undefined) saida.herda = c.herda;
  if (c.abstrato === true) saida.abstrato = true;
  if (c.requer !== undefined) saida.requer = c.requer;
  if (c.html !== undefined) saida.html = c.html;
  if (c.css !== undefined) saida.css = c.css;
  if (c.w !== undefined) saida.w = c.w;
  if (c.h !== undefined) saida.h = c.h;
  const d = c.variantes?.desktop;
  if (d) saida.variantes = { desktop: d.html === undefined ? { css: d.css, w: d.w, h: d.h } : { html: d.html, css: d.css, w: d.w, h: d.h } };
  if (c.slots) saida.slots = c.slots.map((s) => ({ chave: s.chave, seletor: s.seletor, como: s.como }));
  if (c.dados) saida.dados = c.dados;
  if (c.fonte) {
    const f = c.fonte;
    saida.fonte = { repo: f.repo, arquivo: f.arquivo, ...(f.simbolo === undefined ? {} : { simbolo: f.simbolo }), commit: f.commit, receita: f.receita };
  }
  if (c.fontes) saida.fontes = c.fontes;
  if (c.sprite !== undefined) saida.sprite = c.sprite;
  return saida as unknown as Componente;
}

/** As chaves que uma instância aceita em `dados`: as dos slots e as dos dados padrão. */
export function chavesDe(c: Pick<Componente, "slots" | "dados">): string[] {
  return [...new Set([...c.slots.map((s) => s.chave), ...Object.keys(c.dados)])];
}

// ---------- a pasta do wrapper ----------

/**
 * Lê a pasta de um wrapper: `componente.json` e, quando o campo falta no JSON,
 * `peca.html` (html), `peca.css` (css), `desktop.css` (variantes.desktop.css)
 * e `sprite.svg` (sprite). A pasta é um caminho absoluto; nenhum arquivo pode
 * sair dela (link simbólico para fora é recusado). Não valida: devolve o
 * objeto montado, para `problemaDoComponente`. Erra com uma mensagem clara.
 */
export function lerPasta(pasta: string): Record<string, unknown> {
  if (typeof pasta !== "string" || pasta.includes("\0")) throw new Error("pasta inválida");
  if (!isAbsolute(pasta)) throw new Error(`a pasta precisa ser um caminho absoluto (veio "${pasta}")`);
  if (pasta.split(/[\\/]/).includes("..")) throw new Error(`a pasta não pode ter ".." no caminho (veio "${pasta}")`);
  let raiz: string;
  try {
    raiz = realpathSync(pasta);
  } catch {
    throw new Error(`a pasta não existe: ${pasta}`);
  }
  if (!statSync(raiz).isDirectory()) throw new Error(`não é uma pasta: ${pasta}`);

  /** O conteúdo de um arquivo da pasta, ou undefined se ele não existe. */
  const ler = (nome: string): string | undefined => {
    const caminho = join(raiz, nome);
    let info;
    try {
      info = lstatSync(caminho);
    } catch {
      return undefined;
    }
    let real: string;
    try {
      real = realpathSync(caminho);
    } catch {
      throw new Error(`${nome} aponta para um arquivo que não existe`);
    }
    if (!real.startsWith(raiz + sep)) throw new Error(`${nome} aponta para fora da pasta do wrapper (recusado)`);
    const alvo = info.isSymbolicLink() ? statSync(real) : info;
    if (!alvo.isFile()) throw new Error(`${nome} não é um arquivo`);
    if (alvo.size > MAIOR_ARQUIVO) throw new Error(`${nome} passa de ${MAIOR_ARQUIVO / 1024 / 1024} MB`);
    return readFileSync(real, "utf8");
  };

  const json = ler(ARQUIVOS_DO_WRAPPER.json);
  if (json === undefined) throw new Error(`a pasta não tem ${ARQUIVOS_DO_WRAPPER.json}: ${pasta}`);
  let bruto: unknown;
  try {
    bruto = JSON.parse(json);
  } catch (e) {
    throw new Error(`${ARQUIVOS_DO_WRAPPER.json} não é JSON válido: ${e instanceof Error ? e.message : e}`);
  }
  if (!ehObjeto(bruto)) throw new Error(`${ARQUIVOS_DO_WRAPPER.json} precisa ser um objeto`);
  const c: Record<string, unknown> = { ...bruto };

  if (c.html === undefined) c.html = ler(ARQUIVOS_DO_WRAPPER.html);
  if (c.css === undefined) c.css = ler(ARQUIVOS_DO_WRAPPER.css);
  if (c.sprite === undefined) {
    const sprite = ler(ARQUIVOS_DO_WRAPPER.sprite);
    if (sprite !== undefined) c.sprite = sprite;
  }
  const variantes = ehObjeto(c.variantes) ? { ...c.variantes } : c.variantes;
  const desktop = ehObjeto(variantes) && ehObjeto(variantes.desktop) ? { ...variantes.desktop } : undefined;
  if (desktop) {
    if (desktop.css === undefined) desktop.css = ler(ARQUIVOS_DO_WRAPPER.desktop);
    c.variantes = { ...(variantes as Record<string, unknown>), desktop };
  } else if (variantes === undefined) {
    // Sem a variante no JSON, um desktop.css na pasta vira a variante web (1280), com a altura do celular.
    const css = ler(ARQUIVOS_DO_WRAPPER.desktop);
    if (css !== undefined) c.variantes = { desktop: { css, w: 1280, h: c.h } };
  }
  return c;
}

// ---------- o armazém ----------

/** Grava por arquivo temporário e rename, para nunca deixar um arquivo pela metade. */
function gravar(arquivo: string, conteudo: string): void {
  const temporario = `${arquivo}.${process.pid}.tmp`;
  writeFileSync(temporario, conteudo);
  renameSync(temporario, arquivo);
}

export type Resumo = Pick<Componente, "id" | "nome" | "descricao" | "estado" | "versao" | "w" | "h" | "dados" | "herda" | "abstrato"> & { chaves: string[] };

export class Componentes {
  readonly dir: string;
  /** Chamado a cada definição gravada (o servidor manda o SSE `componente`). */
  aoDefinir?: (c: Componente) => void;

  constructor(dadosDir: string) {
    this.dir = join(dadosDir, "componentes");
  }

  private arquivo(id: string): string {
    const [produto, peca] = id.split("/") as [string, string];
    return join(this.dir, produto, `${peca}.json`);
  }

  /** Valida e grava uma definição, com a versão seguinte. Erra com o problema. */
  definir(entrada: unknown): Componente {
    const problemas = problemasDoComponente(entrada, (id) => this.cru(id));
    if (problemas.length === 1) throw new Error(problemas[0]);
    if (problemas.length > 1) throw new Error(`${problemas.length} problemas:\n${problemas.map((p) => `- ${p}`).join("\n")}`);
    const bruto = entrada as Record<string, unknown>;
    const id = bruto.id as string;
    const anterior = this.cru(id);
    const guardado = limpar(bruto, ((anterior?.versao as number | undefined) ?? 0) + 1);
    const arquivo = this.arquivo(id);
    mkdirSync(join(arquivo, ".."), { recursive: true });
    gravar(arquivo, JSON.stringify(guardado, null, 2) + "\n");
    const componente = this.ler(id) ?? guardado;
    const avisar = (c: Componente) => {
      try {
        this.aoDefinir?.(c);
      } catch (e) {
        log("aviso de componente falhou", e);
      }
    };
    avisar(componente);
    // Quem herda deste (direto ou de longe) muda junto: a Web redesenha cada um.
    for (const filho of this.todos(undefined, true)) {
      if (filho.id !== id && this.descendeDe(filho.id, id)) avisar(filho);
    }
    return componente;
  }

  /** O pai de `id`, subindo a cadeia, passa por `ancestral`? */
  private descendeDe(id: string, ancestral: string): boolean {
    const vistos = new Set<string>();
    let atual = this.cru(id);
    while (atual && typeof atual.herda === "string" && !vistos.has(atual.herda)) {
      if (atual.herda === ancestral) return true;
      vistos.add(atual.herda);
      atual = this.cru(atual.herda);
    }
    return false;
  }

  /** A definição como foi guardada (com `herda`, sem resolver), ou null. */
  private cru(id: string): Record<string, unknown> | null {
    if (!ID_COMPONENTE.test(id)) return null;
    const arquivo = this.arquivo(id);
    if (!existsSync(arquivo)) return null;
    try {
      const bruto = JSON.parse(readFileSync(arquivo, "utf8"));
      return ehObjeto(bruto) && bruto.id === id ? bruto : null;
    } catch {
      return null;
    }
  }

  /** Lê a pasta de um wrapper e grava a definição. */
  definirDaPasta(pasta: string): Componente {
    return this.definir(lerPasta(pasta));
  }

  /** A definição atual, ou null. */
  ler(id: string): Componente | null {
    if (!ID_COMPONENTE.test(id)) return null;
    const arquivo = this.arquivo(id);
    if (!existsSync(arquivo)) return null;
    return this.lerArquivo(arquivo, id);
  }

  private lerArquivo(arquivo: string, idEsperado?: string): Componente | null {
    let bruto: unknown;
    try {
      bruto = JSON.parse(readFileSync(arquivo, "utf8"));
    } catch (e) {
      log(`componente ignorado (${arquivo}): não li o JSON:`, e instanceof Error ? e.message : e);
      return null;
    }
    const problemas = problemasDoComponente(bruto, (id) => this.cru(id));
    if (problemas.length > 0) {
      log(`componente ignorado (${arquivo}): ${problemas.join("; ")}`);
      return null;
    }
    const c = bruto as Record<string, unknown>;
    if (idEsperado !== undefined && c.id !== idEsperado) {
      log(`componente ignorado (${arquivo}): o id "${c.id}" não casa com o caminho`);
      return null;
    }
    const versao = typeof c.versao === "number" && Number.isInteger(c.versao) && c.versao > 0 ? c.versao : 1;
    // A herança se resolve na leitura: o que está no disco é a definição como veio.
    return limpar(resolverHeranca(c, (id) => this.cru(id)).resolvido, versao);
  }

  /** Todas as definições válidas, em ordem de id; só de um produto, se pedido. */
  todos(produto?: string, incluirAbstratos = false): Componente[] {
    let produtos: string[];
    try {
      produtos = readdirSync(this.dir).sort();
    } catch {
      return [];
    }
    if (produto !== undefined) produtos = produtos.filter((p) => p === produto);
    const saida: Componente[] = [];
    for (const p of produtos) {
      const pastaProduto = join(this.dir, p);
      let arquivos: string[];
      try {
        if (!statSync(pastaProduto).isDirectory()) continue;
        arquivos = readdirSync(pastaProduto).filter((a) => a.endsWith(".json")).sort();
      } catch {
        continue;
      }
      for (const a of arquivos) {
        const c = this.lerArquivo(join(pastaProduto, a), `${p}/${a.slice(0, -".json".length)}`);
        if (c && (incluirAbstratos || !c.abstrato)) saida.push(c);
      }
    }
    return saida;
  }

  /** O resumo para o modelo: sem o HTML e o CSS. */
  listar(produto?: string, incluirAbstratos = false): Resumo[] {
    return this.todos(produto, incluirAbstratos).map((c) => ({
      ...(c.herda === undefined ? {} : { herda: c.herda }),
      ...(c.abstrato ? { abstrato: true } : {}),
      id: c.id,
      nome: c.nome,
      descricao: c.descricao,
      estado: c.estado,
      versao: c.versao,
      w: c.w,
      h: c.h,
      chaves: chavesDe(c),
      dados: c.dados,
    }));
  }

  /**
   * Confere que o componente existe e que as chaves de `dados` são dele.
   * Devolve a mensagem de erro para o modelo, ou null.
   */
  conferir(id: string, dados: Record<string, unknown> | undefined): string | null {
    const c = this.ler(id);
    if (!c) {
      const produto = id.split("/")[0];
      const todos = this.todos();
      const doProduto = todos.filter((x) => x.id.split("/")[0] === produto);
      const lista = (doProduto.length > 0 ? doProduto : todos).map((x) => x.id);
      const existentes = lista.length > 0 ? lista.join(", ") : "nenhum ainda";
      return `não existe o componente "${id}" (${doProduto.length > 0 ? `do produto ${produto}` : "definidos"}: ${existentes}). Defina com componente_definir: a pasta do wrapper da skill design, ou o JSON com estado "rascunho" para uma peça nova.`;
    }
    if (c.abstrato) return `o componente "${id}" é abstrato, use um filho (que herda dele)`;
    const chaves = chavesDe(c);
    const estranhas = Object.keys(dados ?? {}).filter((k) => !chaves.includes(k));
    if (estranhas.length > 0) {
      return `o componente "${id}" não tem as chaves ${estranhas.join(", ")} (chaves: ${chaves.join(", ") || "nenhuma"})`;
    }
    return null;
  }
}
