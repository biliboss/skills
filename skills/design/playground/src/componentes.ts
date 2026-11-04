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

/**
 * O primeiro problema do valor como definição de componente (sem olhar a
 * `versao`, que o MCP dá), ou null se casa com o contrato. A mensagem é para
 * o modelo ler e corrigir.
 */
export function problemaDoComponente(v: unknown): string | null {
  if (!ehObjeto(v)) return "o componente precisa ser um objeto JSON";
  if (typeof v.id !== "string" || !ID_COMPONENTE.test(v.id)) {
    return `id inválido ${JSON.stringify(v.id)}: use "<produto>/<peça>" em kebab-case, ex.: "loja/cartao-produto"`;
  }
  if (!ehTexto(v.nome)) return "nome ausente";
  if (typeof v.descricao !== "string") return "descricao ausente (para que serve a peça)";
  if (v.estado !== "rascunho" && v.estado !== "real") return 'estado precisa ser "rascunho" ou "real"';
  if (v.estado === "real" && v.fonte === undefined) {
    return 'estado "real" exige fonte { repo, arquivo, simbolo?, commit, receita }: de onde no código do produto a peça saiu. Sem fonte, use estado "rascunho".';
  }
  if (v.estado === "rascunho" && v.fonte !== undefined) {
    return 'um rascunho não tem fonte: tire o campo fonte, ou use estado "real" se a peça já existe no código do produto';
  }
  if (!ehTexto(v.html)) return "html ausente (ou ponha um peca.html na pasta do wrapper)";
  if (typeof v.css !== "string") return "css ausente (ou ponha um peca.css na pasta do wrapper); use \"\" se a peça não tem CSS";
  if (!ehMedida(v.w) || !ehMedida(v.h)) return "w e h precisam ser números positivos (o tamanho natural no celular, 393 de largura)";
  if (v.variantes !== undefined) {
    if (!ehObjeto(v.variantes)) return "variantes precisa ser um objeto { desktop? }";
    const estranhas = Object.keys(v.variantes).filter((k) => k !== "desktop");
    if (estranhas.length > 0) return `variantes só aceita "desktop" (veio ${estranhas.join(", ")})`;
    if (v.variantes.desktop !== undefined) {
      const p = problemaDaVariante(v.variantes.desktop, "variantes.desktop");
      if (p) return p;
    }
  }
  if (!Array.isArray(v.slots)) return "slots precisa ser uma lista (pode ser vazia)";
  for (const [i, s] of v.slots.entries()) {
    const onde = `slots[${i}]`;
    if (!ehObjeto(s) || !ehTexto(s.chave) || !ehTexto(s.seletor)) return `${onde} precisa de chave e seletor`;
    if (typeof s.como !== "string" || !COMO_VALIDO.test(s.como)) {
      return `${onde}.como inválido: use texto, html, lista, attr:<atributo> ou estilo:<propriedade>`;
    }
  }
  if (!ehObjeto(v.dados)) return "dados precisa ser um objeto chave → texto (ou lista de textos)";
  for (const [chave, valor] of Object.entries(v.dados)) {
    if (typeof valor !== "string" && !ehListaDeTextos(valor)) return `dados.${chave} precisa ser texto ou lista de textos`;
  }
  if (v.fonte !== undefined) {
    const f = v.fonte;
    if (!ehObjeto(f)) return "fonte precisa ser um objeto { repo, arquivo, simbolo?, commit, receita }";
    if (!ehTexto(f.repo) || !ehTexto(f.arquivo) || !ehTexto(f.commit)) return "fonte precisa de repo, arquivo e commit";
    if (f.simbolo !== undefined && !ehTexto(f.simbolo)) return "fonte.simbolo, quando vem, precisa ser texto";
    if (f.receita !== "executar" && f.receita !== "copiar") return 'fonte.receita precisa ser "executar" ou "copiar"';
  }
  if (v.fontes !== undefined && !ehListaDeTextos(v.fontes)) return "fontes precisa ser uma lista de URLs de folhas de estilo";
  if (v.sprite !== undefined && typeof v.sprite !== "string") return "sprite precisa ser o SVG (texto) com os <symbol>";
  return null;
}

/** Só os campos do contrato, na ordem dele (o que vier a mais fica de fora). */
function limpar(v: Record<string, unknown>, versao: number): Componente {
  const c = v as unknown as DefinicaoComponente;
  const saida: Componente = {
    id: c.id,
    nome: c.nome,
    descricao: c.descricao,
    estado: c.estado,
    versao,
    html: c.html,
    css: c.css,
    w: c.w,
    h: c.h,
    slots: c.slots.map((s) => ({ chave: s.chave, seletor: s.seletor, como: s.como })),
    dados: c.dados,
  };
  const d = c.variantes?.desktop;
  if (d) saida.variantes = { desktop: d.html === undefined ? { css: d.css, w: d.w, h: d.h } : { html: d.html, css: d.css, w: d.w, h: d.h } };
  if (c.fonte) {
    const f = c.fonte;
    saida.fonte = { repo: f.repo, arquivo: f.arquivo, ...(f.simbolo === undefined ? {} : { simbolo: f.simbolo }), commit: f.commit, receita: f.receita };
  }
  if (c.fontes) saida.fontes = c.fontes;
  if (c.sprite !== undefined) saida.sprite = c.sprite;
  return saida;
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

export type Resumo = Pick<Componente, "id" | "nome" | "descricao" | "estado" | "versao" | "w" | "h" | "dados"> & { chaves: string[] };

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
    const problema = problemaDoComponente(entrada);
    if (problema) throw new Error(problema);
    const bruto = entrada as Record<string, unknown>;
    const id = bruto.id as string;
    const anterior = this.ler(id);
    const componente = limpar(bruto, (anterior?.versao ?? 0) + 1);
    const arquivo = this.arquivo(id);
    mkdirSync(join(arquivo, ".."), { recursive: true });
    gravar(arquivo, JSON.stringify(componente, null, 2) + "\n");
    try {
      this.aoDefinir?.(componente);
    } catch (e) {
      log("aviso de componente falhou", e);
    }
    return componente;
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
    const problema = problemaDoComponente(bruto);
    if (problema) {
      log(`componente ignorado (${arquivo}): ${problema}`);
      return null;
    }
    const c = bruto as Componente;
    if (idEsperado !== undefined && c.id !== idEsperado) {
      log(`componente ignorado (${arquivo}): o id "${c.id}" não casa com o caminho`);
      return null;
    }
    const versao = typeof c.versao === "number" && Number.isInteger(c.versao) && c.versao > 0 ? c.versao : 1;
    return { ...c, versao };
  }

  /** Todas as definições válidas, em ordem de id; só de um produto, se pedido. */
  todos(produto?: string): Componente[] {
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
        if (c) saida.push(c);
      }
    }
    return saida;
  }

  /** O resumo para o modelo: sem o HTML e o CSS. */
  listar(produto?: string): Resumo[] {
    return this.todos(produto).map((c) => ({
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
    const chaves = chavesDe(c);
    const estranhas = Object.keys(dados ?? {}).filter((k) => !chaves.includes(k));
    if (estranhas.length > 0) {
      return `o componente "${id}" não tem as chaves ${estranhas.join(", ")} (chaves: ${chaves.join(", ") || "nenhuma"})`;
    }
    return null;
  }
}
