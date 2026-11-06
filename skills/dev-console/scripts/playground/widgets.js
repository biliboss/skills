// Os componentes: carrega GET /playground/api/componentes (as definições, com versão), prepara
// o CSS de cada definição (com `:root` trocado por `:host`) como um CSSStyleSheet
// construível, põe as fontes no <head> e desenha uma instância {componente, dados}
// num shadowRoot aplicando os dados pelos slots (CONTRATO.md, "Componentes e instâncias").

export const LARGURA_DESKTOP = 1024 // a instância num frame com largura >= isto usa variantes.desktop
const ESPERA_RELER_MS = 1000 // um id desconhecido só busca a lista de novo depois disto

const defs = new Map()   // id → Componente (a definição atual)
const folhas = new Map() // `${id}@${versao}:${variante}` → CSSStyleSheet
const fontesPostas = new Set()
const ouvintes = new Set() // (id) => void, chamados quando uma definição muda
let pedido = null          // a busca da lista em andamento
let buscadaEm = 0          // quando a última busca terminou
let carregou = false

// a base de cada instância dentro do shadow DOM: o corpo é medido para a altura
const BASE = new CSSStyleSheet()
BASE.replaceSync(`
:host { display: block; }
.w-sprite { position: absolute; width: 0; height: 0; overflow: hidden; }
.w-corpo { display: flow-root; }
.w-erro { box-sizing: border-box; height: 100%; display: flex; align-items: center; padding: 10px 12px; font: 12px/1.4 system-ui, sans-serif; color: #9f1239; background: #fff1f2; border: 1px dashed #fda4af; }
`)

// as @font-face do componente não valem dentro de um shadow DOM: vão para o documento
const FONTES_DOC = new CSSStyleSheet()
document.adoptedStyleSheets = [...document.adoptedStyleSheets, FONTES_DOC]

/** O produto de um id: o prefixo antes da barra ("via/cartao" → "via"). */
export function produtoDe(id) {
  const i = String(id).indexOf('/')
  return i > 0 ? String(id).slice(0, i) : String(id)
}

/** Avisa quando a definição de um id muda (o retorno desliga). */
export function aoMudar(fn) {
  ouvintes.add(fn)
  return () => ouvintes.delete(fn)
}

function avisar(id) {
  for (const fn of ouvintes) { try { fn(id) } catch (e) { console.warn('[widgets] ouvinte falhou', e) } }
}

function esquecerFolhas(id, manterVersao) {
  for (const chave of folhas.keys()) {
    if (chave.startsWith(`${id}@`) && chave !== `${id}@${manterVersao}:padrao` && chave !== `${id}@${manterVersao}:desktop`) folhas.delete(chave)
  }
}

/** Busca a lista no servidor e troca o cache; devolve os ids que mudaram (novos, de versão nova ou sumidos). */
function buscar() {
  if (pedido) return pedido
  pedido = fetch('/playground/api/componentes', { cache: 'no-store' })
    .then((r) => { if (!r.ok) throw new Error(`GET /playground/api/componentes ${r.status}`); return r.json() })
    .then((j) => {
      const lista = Array.isArray(j?.componentes) ? j.componentes : []
      const mudados = []
      const vistos = new Set()
      for (const c of lista) {
        if (!c?.id) continue
        vistos.add(c.id)
        const antes = defs.get(c.id)
        if (!antes || antes.versao !== c.versao || JSON.stringify(antes) !== JSON.stringify(c)) {
          mudados.push(c.id)
          esquecerFolhas(c.id, c.versao)
        }
        defs.set(c.id, c)
      }
      for (const id of [...defs.keys()]) if (!vistos.has(id)) { defs.delete(id); esquecerFolhas(id, -1); mudados.push(id) }
      carregou = true
      return mudados
    })
    .finally(() => { pedido = null; buscadaEm = Date.now() })
  return pedido
}

/**
 * As definições, por ordem de id. `{ recarregar: true }` busca de novo; `fresco` não
 * aproveita uma busca que já estava em andamento (ela pode ter saído antes da mudança).
 */
export async function componentes({ recarregar = false, fresco = false } = {}) {
  if (!carregou || recarregar) {
    const primeira = !carregou
    if (fresco && pedido) await pedido.catch(() => {})
    const mudados = await buscar()
    if (!primeira) for (const id of mudados) avisar(id)
  }
  return [...defs.values()].sort((a, b) => String(a.id).localeCompare(String(b.id)))
}

/**
 * A definição de um id. Se não conhece, busca a lista de novo (uma vez, sem repetir
 * em menos de 1 s: um canvas com dez instâncias de um id indefinido faz uma busca só).
 * Devolve `null` quando o componente não está definido.
 */
export async function acharComponente(id) {
  if (!carregou) await componentes()
  if (defs.has(id)) return defs.get(id)
  if (pedido) await pedido.catch(() => {})
  else if (Date.now() - buscadaEm > ESPERA_RELER_MS) await componentes({ recarregar: true })
  return defs.get(id) ?? null
}

/** Como `acharComponente`, mas falha quando não existe (as operações do agente). */
export async function exigirComponente(id) {
  const c = await acharComponente(id)
  if (!c) throw new Error(`componente ${id} não definido`)
  return c
}

/**
 * O SSE `componente` {id, versao}: busca a definição nova (se a do cache for mais velha);
 * quem desenha instâncias daquele id é avisado pelo `aoMudar`.
 */
export async function receber({ id, versao } = {}) {
  if (!id) return
  const atual = defs.get(id)
  if (atual && versao != null && atual.versao >= versao) return
  try { await componentes({ recarregar: true, fresco: true }) } catch (e) { console.warn('[widgets] não releu os componentes', e) }
}

/** A variante que a instância usa: `desktop` quando o frame dela tem largura >= 1024 e a definição tem a variante. */
export function variante(def, larguraFrame) {
  return larguraFrame >= LARGURA_DESKTOP && def?.variantes?.desktop ? 'desktop' : 'padrao'
}

/** O tamanho natural da instância (o da variante, se ela for usada). */
export function tamanho(def, larguraFrame) {
  const v = variante(def, larguraFrame) === 'desktop' ? def.variantes.desktop : def
  return { w: Number(v.w) || Number(def.w) || 393, h: Number(v.h) || Number(def.h) || 80 }
}

// `:root` → `:host` (e `:root[x]` → `:host([x])`); url() relativa passa a valer a partir da página
function adaptarCss(css) {
  return String(css ?? '')
    .replace(/:root((?:\[[^\]]*\])+)/g, ':host($1)')
    .replace(/:root\b/g, ':host')
    .replace(/url\(\s*(['"]?)([^'")]+)\1\s*\)/g, (todo, aspas, alvo) => {
      if (/^(data:|blob:|https?:|\/|#)/i.test(alvo.trim())) return todo
      return `url("${new URL(alvo.trim(), location.href).href}")`
    })
}

function porFontes(def) {
  for (const href of def.fontes ?? []) {
    const abs = new URL(href, location.href).href
    if (fontesPostas.has(abs)) continue
    fontesPostas.add(abs)
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = abs
    link.dataset.componente = def.id
    document.head.append(link)
  }
}

const fontFacesPostas = new Set()
function levarFontFaces(folha) {
  for (const regra of folha.cssRules) {
    if (regra instanceof CSSFontFaceRule && !fontFacesPostas.has(regra.cssText)) {
      fontFacesPostas.add(regra.cssText)
      try { FONTES_DOC.insertRule(regra.cssText, FONTES_DOC.cssRules.length) } catch {}
    }
  }
}

function folhaDe(def, qual) {
  const chave = `${def.id}@${def.versao}:${qual}`
  let f = folhas.get(chave)
  if (!f) {
    const css = qual === 'desktop' ? def.variantes.desktop.css : def.css
    f = new CSSStyleSheet()
    f.replaceSync(adaptarCss(css))
    levarFontFaces(f)
    folhas.set(chave, f)
  }
  return f
}

function comoTexto(v) { return Array.isArray(v) ? v.join(' ') : String(v ?? '') }

/** Aplica os dados pelos slots, como o CONTRATO diz. */
export function aplicarDados(raiz, slots, dados) {
  for (const slot of slots ?? []) {
    if (!slot?.seletor || !(slot.chave in dados)) continue
    const v = dados[slot.chave]
    const como = String(slot.como ?? 'texto')
    if (como === 'lista') {
      const todos = [...raiz.querySelectorAll(slot.seletor)]
      if (!todos.length) continue
      const modelo = todos[0]
      for (const outro of todos.slice(1)) if (outro.parentNode === modelo.parentNode) outro.remove()
      const itens = Array.isArray(v) ? v : [v]
      modelo.replaceWith(...itens.map((item) => {
        const c = modelo.cloneNode(true)
        const texto = String(item ?? '')
        // [data-texto]: o item vai nesses elementos (" | " separa as partes) e o resto do clone (ícones) fica
        const alvos = c.matches?.('[data-texto]') ? [c] : [...c.querySelectorAll('[data-texto]')]
        if (alvos.length) {
          const partes = texto.split(' | ')
          alvos.forEach((el, i) => { el.textContent = partes[i] ?? '' })
        } else c.textContent = texto
        return c
      }))
      continue
    }
    const el = raiz.querySelector(slot.seletor)
    if (!el) continue
    if (como === 'texto') el.textContent = comoTexto(v)
    else if (como === 'html') el.innerHTML = comoTexto(v)
    else if (como.startsWith('attr:')) el.setAttribute(como.slice(5), comoTexto(v))
    else if (como.startsWith('estilo:')) el.style.setProperty(como.slice(7), comoTexto(v))
  }
}

/** Os dados da instância (objeto ou JSON em string) por cima dos padrões da definição. */
export function juntarDados(def, dados) {
  let proprios = dados
  if (typeof dados === 'string') { try { proprios = JSON.parse(dados || '{}') } catch { proprios = {} } }
  return { ...(def?.dados ?? {}), ...(proprios && typeof proprios === 'object' ? proprios : {}) }
}

const pedidos = new WeakMap() // shadowRoot → número do último pedido (o mais novo vence)

/**
 * Preenche o shadowRoot com a instância: a folha da definição (ou da variante desktop),
 * o sprite, o HTML e os dados. Devolve `{ corpo, def, definido }`: `corpo` (o `.w-corpo`)
 * tem a altura natural; `definido` é falso quando o componente não existe (o aviso no lugar).
 * Devolve `null` se um pedido mais novo passou na frente.
 */
export async function desenhar(raiz, { componente, dados, larguraFrame = 0 }) {
  const meu = (pedidos.get(raiz) ?? 0) + 1
  pedidos.set(raiz, meu)
  const erro = (texto) => {
    raiz.adoptedStyleSheets = [BASE]
    const corpo = document.createElement('div')
    corpo.className = 'w-corpo w-indefinido'
    corpo.style.height = '100%'
    const caixa = document.createElement('div')
    caixa.className = 'w-erro'
    caixa.setAttribute('role', 'note')
    caixa.textContent = texto
    corpo.append(caixa)
    raiz.replaceChildren(corpo)
    return corpo
  }
  try {
    const def = await acharComponente(componente)
    if (pedidos.get(raiz) !== meu) return null
    if (!def) return { corpo: erro(`componente ${componente || '(sem id)'} não definido`), def: null, definido: false }
    const qual = variante(def, larguraFrame)
    porFontes(def)
    raiz.adoptedStyleSheets = [BASE, folhaDe(def, qual)]
    const caixaSprite = document.createElement('div')
    caixaSprite.className = 'w-sprite'
    caixaSprite.setAttribute('aria-hidden', 'true')
    caixaSprite.innerHTML = def.sprite ?? ''
    const corpo = document.createElement('div')
    corpo.className = 'w-corpo'
    corpo.dataset.variante = qual
    corpo.innerHTML = (qual === 'desktop' ? def.variantes.desktop.html : null) ?? def.html ?? ''
    aplicarDados(corpo, def.slots, juntarDados(def, dados))
    raiz.replaceChildren(caixaSprite, corpo)
    return { corpo, def, definido: true }
  } catch (e) {
    if (pedidos.get(raiz) !== meu) return null
    return { corpo: erro(`${componente}: ${e?.message ?? e}`), def: null, definido: false }
  }
}
