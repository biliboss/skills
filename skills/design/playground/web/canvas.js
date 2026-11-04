// O canvas do tldraw no centro. A página é dona do desenho: carrega o que o
// servidor guardou e manda cada mudança do usuário em POST /api/canvas/diff.

import * as W from './widgets.js'
import { montarPaleta } from './paleta.js'

const TLDRAW = 'https://esm.sh/tldraw@3.15.4?deps=react@18.3.1,react-dom@18.3.1'
const REACT = 'https://esm.sh/react@18.3.1'
const REACT_DOM = 'https://esm.sh/react-dom@18.3.1/client?deps=react@18.3.1'

const raiz = document.getElementById('canvas')

// existe desde já, para o chat poder chamar antes de o editor montar
const playground = {
  editor: null,
  selecao: () => (playground.editor ? playground.editor.getSelectedShapeIds() : []),
}
window.playground = playground

function aviso(titulo, detalhe) {
  raiz.replaceChildren()
  const caixa = document.createElement('div')
  caixa.className = 'canvas-aviso'
  caixa.setAttribute('role', 'alert')
  const t = document.createElement('strong')
  t.textContent = titulo
  caixa.append(t)
  if (detalhe) {
    const d = document.createElement('code')
    d.textContent = detalhe
    caixa.append(d)
  }
  raiz.append(caixa)
}

// ---- diff para o servidor ----
// sem setTimeout: aba em segundo plano tem timer atrasado; microtask não
let put = {}
let remove = {}
let agendado = false

function enviar() {
  agendado = false
  const corpo = { put, remove: Object.keys(remove) }
  const vazio = !Object.keys(put).length && !corpo.remove.length
  put = {}
  remove = {}
  if (vazio) return
  const body = JSON.stringify(corpo)
  fetch('/api/canvas/diff', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body,
    // o navegador recusa keepalive acima de 64 KB (ex.: colar uma imagem)
    keepalive: body.length < 60_000,
  }).catch((e) => console.warn('[canvas] diff não enviado', e))
}

function agendar() {
  if (agendado) return
  agendado = true
  queueMicrotask(enviar)
}

// ---- a migração: a forma `widget` de kit ({kit, peca}) vira instância ({componente}) ----
// `via-v12/<p>` e `tmp/<p>` → `via/<p>` (CONTRATO, "Migração do canvas"); outro kit fica `<kit>/<p>`.
const KIT_PARA_PRODUTO = { 'via-v12': 'via', tmp: 'via' }

function ehWidgetDeKit(r) {
  return r?.typeName === 'shape' && r.type === 'widget' && r.props && ('kit' in r.props || 'peca' in r.props)
}

/** As props antigas ({w, h, kit, peca, dados}) nas novas ({w, h, componente, dados}). */
function migrarProps(props) {
  const { kit, peca, componente, ...resto } = props ?? {}
  const produto = KIT_PARA_PRODUTO[kit] ?? kit
  return {
    w: typeof resto.w === 'number' ? resto.w : 393,
    h: typeof resto.h === 'number' ? resto.h : 80,
    componente: typeof componente === 'string' && componente ? componente : (produto && peca ? `${produto}/${peca}` : String(peca ?? '')),
    dados: typeof resto.dados === 'string' ? resto.dados : JSON.stringify(resto.dados ?? {}),
  }
}

async function carregar(editor) {
  const migrados = []
  try {
    const r = await fetch('/api/canvas')
    if (!r.ok) throw new Error(`GET /api/canvas ${r.status}`)
    const { registros } = await r.json()
    // o tldraw valida as props no put: as formas antigas são convertidas antes
    const lista = Object.values(registros ?? {}).map((reg) => {
      if (!ehWidgetDeKit(reg)) return reg
      const novo = { ...reg, props: migrarProps(reg.props) }
      migrados.push(novo)
      return novo
    })
    if (lista.length) editor.store.mergeRemoteChanges(() => editor.store.put(lista))
  } catch (e) {
    console.warn('[canvas] não carregou o canvas salvo', e)
  }
  return migrados
}

/** Manda as formas migradas ao servidor pelo diff de sempre (uma vez: depois disso o canvas salvo já é novo). */
function salvarMigrados(editor, migrados) {
  if (!migrados.length) return
  for (const m of migrados) {
    const atual = editor.store.get(m.id)
    if (atual) { put[atual.id] = atual; delete remove[atual.id] }
  }
  console.info(`[canvas] ${migrados.length} instância(s) migrada(s) de kit para componente`)
  agendar()
}

function ouvir(editor) {
  editor.store.listen(({ changes }) => {
    for (const r of Object.values(changes.added)) { put[r.id] = r; delete remove[r.id] }
    for (const [, r] of Object.values(changes.updated)) { put[r.id] = r; delete remove[r.id] }
    for (const r of Object.values(changes.removed)) { remove[r.id] = 1; delete put[r.id] }
    agendar()
  }, { source: 'user', scope: 'document' })
}

// ---- a forma "tela": uma prancheta com nome e o HTML num iframe isolado ----
const CABECA = 28

function criarTelaUtil(React, t) {
  const h = React.createElement
  return class TelaUtil extends t.BaseBoxShapeUtil {
    static type = 'tela'
    static props = { w: t.T.number, h: t.T.number, nome: t.T.string, html: t.T.string }
    getDefaultProps() { return { w: 390, h: 844, nome: 'Tela', html: '' } }
    canEdit() { return true }
    canResize() { return true }
    component(shape) {
      const editando = this.editor.getEditingShapeId() === shape.id
      const { w, h: alt, nome, html } = shape.props
      return h(t.HTMLContainer, { className: 'tela', style: { width: w, height: alt, pointerEvents: editando ? 'all' : 'none' } },
        h('div', { className: 'tela-nome', title: nome }, nome),
        h('iframe', {
          className: 'tela-quadro',
          srcDoc: html,
          sandbox: 'allow-scripts',
          title: nome,
          style: { width: w, height: alt - CABECA },
        }))
    }
    indicator(shape) { return h('rect', { width: shape.props.w, height: shape.props.h }) }
  }
}

// ---- a forma "widget": uma instância de um componente, num shadow DOM com o CSS da definição ----
// A altura acompanha o conteúdo: o ResizeObserver mede o corpo da instância e muda o
// `h` da forma quando a diferença passa de 1 px (o corpo não depende do `h`, então não há laço).
// Um componente não definido mostra o aviso no lugar, com a altura que a forma já tinha.

function ajustarAltura(editor, id, corpo) {
  if (!corpo.isConnected) return
  const alt = Math.ceil(corpo.offsetHeight)
  if (!alt) return // escondida (fora da vista) ou ainda sem layout
  const s = editor.getShape(id)
  if (!s || s.type !== 'widget' || Math.abs(s.props.h - alt) <= 1) return
  editor.run(() => editor.updateShape({ id, type: 'widget', props: { h: alt } }), { history: 'ignore' })
}

/** A largura do frame que contém a forma (o mais próximo, passando por groups); 0 fora de frame. */
function larguraDoFrame(editor, shape) {
  let id = shape?.parentId
  for (let i = 0; id && String(id).startsWith('shape:') && i < 50; i++) {
    const p = editor.getShape(id)
    if (!p) break
    if (p.type === 'frame') return p.props.w
    id = p.parentId
  }
  return 0
}

function criarWidgetUtil(React, t) {
  const h = React.createElement

  function Instancia({ editor, id, componente, dados, larguraFrame, w, alt }) {
    const host = React.useRef(null)
    const corpoAtual = React.useRef(null)
    const [geracao, setGeracao] = React.useState(0)
    const [estado, setEstado] = React.useState(null)
    // a definição mudou (SSE `componente`): redesenha
    React.useEffect(() => W.aoMudar((cid) => { if (cid === componente) setGeracao((g) => g + 1) }), [componente])
    // só a escolha da variante importa, não cada pixel da largura do frame
    const desktop = larguraFrame >= W.LARGURA_DESKTOP
    React.useLayoutEffect(() => {
      const el = host.current
      const raiz = el.shadowRoot ?? el.attachShadow({ mode: 'open' })
      let vivo = true
      let obs = null
      W.desenhar(raiz, { componente, dados, larguraFrame }).then((r) => {
        if (!vivo || !r) return
        setEstado(r.def?.estado ?? null)
        corpoAtual.current = r.definido ? r.corpo : null
        if (!r.definido) return
        obs = new ResizeObserver(() => ajustarAltura(editor, id, r.corpo))
        obs.observe(r.corpo)
        ajustarAltura(editor, id, r.corpo)
      })
      return () => { vivo = false; obs?.disconnect() }
    }, [componente, dados, desktop, geracao])
    // alguém mudou o h (redimensionar, `mudar`): volta para a altura do conteúdo
    React.useEffect(() => { if (corpoAtual.current) ajustarAltura(editor, id, corpoAtual.current) }, [w, alt])
    return h(React.Fragment, null,
      h('div', { ref: host, className: 'widget-host', 'data-componente': componente }),
      estado === 'rascunho' ? h('span', { className: 'widget-rascunho', 'aria-label': `${componente} é um rascunho` }, 'rascunho') : null)
  }

  const props = { w: t.T.number, h: t.T.number, componente: t.T.string, dados: t.T.string }
  // um registro antigo que chegue por snapshot ou colagem (com o schema) também migra
  let migrations
  if (t.createShapePropsMigrationIds && t.createShapePropsMigrationSequence) {
    const versoes = t.createShapePropsMigrationIds('widget', { Componente: 1 })
    migrations = t.createShapePropsMigrationSequence({
      sequence: [{
        id: versoes.Componente,
        up(p) {
          if (!('kit' in p) && !('peca' in p)) return
          const novo = migrarProps(p)
          for (const k of Object.keys(p)) delete p[k]
          Object.assign(p, novo)
        },
      }],
    })
  }

  return class WidgetUtil extends t.BaseBoxShapeUtil {
    static type = 'widget'
    static props = props
    static migrations = migrations
    getDefaultProps() { return { w: 393, h: 80, componente: '', dados: '{}' } }
    canEdit() { return true }
    canResize() { return true }
    component(shape) {
      const editando = this.editor.getEditingShapeId() === shape.id
      const { w, h: alt, componente, dados } = shape.props
      const larguraFrame = larguraDoFrame(this.editor, shape)
      return h(t.HTMLContainer, { className: 'widget', style: { width: w, height: alt, pointerEvents: editando ? 'all' : 'none' } },
        h(Instancia, { editor: this.editor, id: shape.id, componente, dados, larguraFrame, w, alt }))
    }
    indicator(shape) { return h('rect', { width: shape.props.w, height: shape.props.h }) }
  }
}

// ---- a pilha: um frame com meta.pilha = true empilha os filhos na vertical ----
// Ordena pelo meio de cada filho em y (com tudo empilhado, é a mesma ordem do y),
// põe x = 0, w = largura do frame e y acumulado, sem espaço. Um group entra como um bloco.
// Com meta.lateral = L, são duas pilhas: a lateral (x = 0, w = L) e a principal
// (x = L, w = largura − L), cada filho com meta.coluna. Um filho fora do x da coluna
// dele (arrastado, ou que acabou de entrar) vai para a lateral se o meio cair em x < L.

const ESTICA = new Set(['widget', 'geo', 'frame', 'tela'])

function ehPilha(s) { return s?.type === 'frame' && s.meta?.pilha === true }

/** A largura da coluna lateral de um frame com pilha; 0 sem lateral. */
function larguraLateral(f) {
  const l = f?.meta?.lateral
  return ehPilha(f) && typeof l === 'number' && l > 0 ? l : 0
}

/** O x e a largura de uma coluna num frame com lateral `L`. */
function faixa(f, L, coluna) {
  return coluna === 'lateral' ? { x: 0, w: L } : { x: L, w: Math.max(1, f.props.w - L) }
}

/**
 * A coluna de um filho ({s, b} de filhosOrdenados) num frame com lateral `L`: a registrada
 * em meta.coluna enquanto ele está no x dela; senão, pelo meio em x.
 */
function colunaDoFilho({ s, b }, L) {
  const registrada = s.meta?.coluna === 'lateral' ? 'lateral' : 'principal'
  const esquerda = s.x + b.minX
  if (Math.abs(esquerda - (registrada === 'lateral' ? 0 : L)) <= 0.5) return registrada
  return esquerda + b.w / 2 < L ? 'lateral' : 'principal'
}

function filhosOrdenados(editor, frameId) {
  return editor.getSortedChildIdsForParent(frameId)
    .map((id) => editor.getShape(id)).filter(Boolean)
    .map((s, i) => {
      const b = editor.getShapeGeometry(s).bounds
      return { s, b, meio: s.y + b.minY + b.h / 2, i }
    })
    .sort((a, b) => a.meio - b.meio || a.s.x - b.s.x || a.i - b.i)
}

// O groupShapes do tldraw, dentro de um frame fora da origem, cria o group com x/y da
// página e os filhos compensados (ex.: group x = 929, filhos x = -929). Na página fica
// certo, mas o `ler` mostraria um x sem sentido: põe a origem do group no canto dos filhos.
function normalizarGrupo(editor, g) {
  const b = editor.getShapeGeometry(g).bounds
  if (Math.abs(b.minX) <= 0.5 && Math.abs(b.minY) <= 0.5) return
  const filhos = editor.getSortedChildIdsForParent(g.id).map((id) => editor.getShape(id)).filter(Boolean)
  editor.updateShapes([
    { id: g.id, type: 'group', x: g.x + b.minX, y: g.y + b.minY },
    ...filhos.map((c) => ({ id: c.id, type: c.type, x: c.x - b.minX, y: c.y - b.minY })),
  ])
}

/** Empilha os filhos de um frame com pilha; `livres` são os que estão sendo arrastados. */
function empilhar(editor, frameId, livres) {
  const f = editor.getShape(frameId)
  if (!ehPilha(f)) return 0
  for (const id of editor.getSortedChildIdsForParent(f.id)) {
    const g = editor.getShape(id)
    if (g?.type === 'group' && !livres?.has(g.id) && !g.rotation) normalizarGrupo(editor, g)
  }
  const L = larguraLateral(f)
  const ys = { lateral: 0, principal: 0 }
  const parciais = []
  for (const it of filhosOrdenados(editor, f.id)) {
    const { s, b } = it
    const coluna = L ? colunaDoFilho(it, L) : 'principal'
    const { x: x0, w: largura } = L ? faixa(f, L, coluna) : { x: 0, w: f.props.w }
    if (!livres?.has(s.id)) {
      const p = { id: s.id, type: s.type }
      let mudou = false
      const nx = x0 - b.minX
      const ny = ys[coluna] - b.minY
      if (Math.abs(s.x - nx) > 0.5) { p.x = nx; mudou = true }
      if (Math.abs(s.y - ny) > 0.5) { p.y = ny; mudou = true }
      if (ESTICA.has(s.type) && typeof s.props.w === 'number' && Math.abs(s.props.w - largura) > 0.5) {
        p.props = { w: largura }; mudou = true
      }
      if (L && s.meta?.coluna !== coluna) { p.meta = { ...s.meta, coluna }; mudou = true }
      if (mudou) parciais.push(p)
    }
    ys[coluna] += b.h
  }
  if (parciais.length) editor.updateShapes(parciais)
  return parciais.length
}

function empilharTodas(editor) {
  const pilhas = editor.getCurrentPageShapes().filter(ehPilha)
  if (pilhas.length) editor.run(() => { for (const f of pilhas) empilhar(editor, f.id) })
}

// Recalcula quando um filho entra, sai, muda de tamanho ou é arrastado. Só olha os
// frames tocados; o empilhar não muda nada quando já está certo, então não há laço.
function ouvirPilhas(editor) {
  const sujos = new Set()
  let agendado = false
  let soltarPendente = false

  const marcar = (id) => {
    // a forma e os ancestrais (um filho de um group dentro da pilha muda o bloco do group)
    for (let i = 0; id && String(id).startsWith('shape:') && i < 50; i++) {
      sujos.add(id)
      id = editor.getShape(id)?.parentId
    }
  }

  function rodar() {
    agendado = false
    const arrastando = editor.isIn('select.translating')
    const livres = arrastando ? new Set(editor.getSelectedShapeIds()) : null
    if (arrastando) soltarPendente = true
    const ids = [...sujos]
    sujos.clear()
    const pilhas = ids.map((id) => editor.getShape(id)).filter(ehPilha)
    if (pilhas.length) editor.run(() => { for (const f of pilhas) empilhar(editor, f.id, livres) })
  }

  editor.store.listen(({ changes }) => {
    for (const r of Object.values(changes.added)) if (r.typeName === 'shape') marcar(r.id)
    for (const [antes, depois] of Object.values(changes.updated)) {
      if (depois.typeName !== 'shape') continue
      marcar(depois.id)
      if (antes.parentId !== depois.parentId) marcar(antes.parentId)
    }
    for (const r of Object.values(changes.removed)) if (r.typeName === 'shape') marcar(r.parentId)
    if (sujos.size && !agendado) { agendado = true; queueMicrotask(rodar) }
  }, { source: 'user', scope: 'document' })

  // ao soltar um arrasto, quem estava livre entra no lugar
  function soltar() {
    if (editor.isIn('select.translating')) { setTimeout(soltar, 30); return }
    soltarPendente = false
    empilharTodas(editor)
  }
  editor.on('event', (e) => {
    if (soltarPendente && e?.name === 'pointer_up') queueMicrotask(soltar)
  })

  empilharTodas(editor)
}

function dadosDe(s) {
  try { return JSON.parse(s.props.dados || '{}') } catch { return {} }
}

function propsDaInstancia(def, larguraFrame, dados) {
  const { w, h } = W.tamanho(def, larguraFrame)
  // a instância guarda só os próprios dados; os padrões vêm da definição atual
  return { w, h, componente: def.id, dados: JSON.stringify(dados && typeof dados === 'object' ? dados : {}) }
}

/** Cria a instância dentro de um frame (na `coluna`, se ele tem lateral); sem `indice` vai para o fim. */
function inserirNoFrame(editor, frameId, def, dados, indice, coluna) {
  const f = editor.getShape(frameId)
  const L = larguraLateral(f)
  if (coluna === 'lateral' && !L) throw new Error(`a tela ${frameId} não tem coluna lateral`)
  const col = L ? (coluna === 'lateral' ? 'lateral' : 'principal') : null
  const itens = filhosOrdenados(editor, frameId).filter((it) => !col || colunaDoFilho(it, L) === col)
  let borda = 0 // onde a instância entra: o topo do item no índice, ou o fim
  if (itens.length) {
    const i = indice == null ? itens.length : Math.max(0, Math.min(itens.length, Math.trunc(indice)))
    const it = itens[Math.min(i, itens.length - 1)]
    borda = i < itens.length ? it.s.y + it.b.minY : it.s.y + it.b.maxY
  }
  const props = propsDaInstancia(def, f.props.w, dados)
  const id = T.createShapeId()
  editor.run(() => {
    editor.createShape({
      id, type: 'widget', parentId: frameId, x: col ? faixa(f, L, col).x : 0,
      // o meio da instância cai na borda: fica depois do anterior e antes do seguinte
      y: ehPilha(f) ? borda - props.h / 2 : borda,
      props,
      ...(col ? { meta: { coluna: col } } : {}),
    })
    empilhar(editor, frameId)
  })
  return id
}

function pilhaNoPonto(editor, ponto) {
  const pilhas = editor.getCurrentPageShapesSorted().filter(ehPilha).reverse()
  return pilhas.find((f) => {
    const b = editor.getShapePageBounds(f.id)
    return b && ponto.x >= b.minX && ponto.x <= b.maxX && ponto.y >= b.minY && ponto.y <= b.maxY
  })
}

/** A paleta soltou um componente num ponto da página: dentro de um frame com pilha vira filha dele. */
async function soltarComponente(editor, componenteId, ponto) {
  const def = await W.exigirComponente(componenteId)
  editor.markHistoryStoppingPoint('paleta')
  const f = pilhaNoPonto(editor, ponto)
  const id = T.createShapeId()
  if (f) {
    const local = editor.getPointInShapeSpace(f.id, ponto)
    const props = propsDaInstancia(def, f.props.w)
    const L = larguraLateral(f)
    const col = L ? (local.x < L ? 'lateral' : 'principal') : null
    editor.run(() => {
      editor.createShape({
        id, type: 'widget', parentId: f.id, x: col ? faixa(f, L, col).x : 0, y: local.y - props.h / 2, props,
        ...(col ? { meta: { coluna: col } } : {}),
      })
      empilhar(editor, f.id)
    })
  } else {
    const props = propsDaInstancia(def, 0)
    editor.createShape({ id, type: 'widget', x: ponto.x - props.w / 2, y: ponto.y - props.h / 2, props })
  }
  editor.select(id)
  return id
}

/** Clique na paleta: com um frame com pilha selecionado (ou algo dentro dele), entra no fim; senão, no meio da vista. */
async function clicarComponente(editor, componenteId) {
  const sel = editor.getOnlySelectedShape()
  let f = ehPilha(sel) ? sel : null
  let coluna
  if (!f && sel) {
    const pai = editor.getShape(sel.parentId)
    if (ehPilha(pai)) { f = pai; if (larguraLateral(pai) && sel.meta?.coluna === 'lateral') coluna = 'lateral' }
  }
  if (!f) return soltarComponente(editor, componenteId, editor.getViewportPageBounds().center)
  const def = await W.exigirComponente(componenteId)
  editor.markHistoryStoppingPoint('paleta')
  const id = inserirNoFrame(editor, f.id, def, undefined, undefined, coluna)
  editor.select(id)
  return id
}

// ---- as operações que o agente manda pelo MCP (via SSE, repassado pelo chat.js) ----
let T = null
const fila = []

function texto(editor, s) {
  const r = s.props?.richText
  if (r && T.renderPlaintextFromRichText) { try { return T.renderPlaintextFromRichText(editor, r) } catch {} }
  return s.props?.text ?? undefined
}

function simples(editor, s) {
  const b = editor.getShapePageBounds(s.id)
  const o = { id: s.id, tipo: s.type, x: Math.round(s.x), y: Math.round(s.y), w: Math.round(b?.w ?? 0), h: Math.round(b?.h ?? 0) }
  if (s.type === 'tela') o.nome = s.props.nome
  else if (s.type === 'frame') { o.nome = s.props.name; o.pilha = ehPilha(s); if (larguraLateral(s)) o.lateral = larguraLateral(s) }
  else if (s.type === 'widget') { o.componente = s.props.componente; o.dados = dadosDe(s) }
  else { const t = texto(editor, s); if (t) o.texto = t }
  if (s.props?.color) o.cor = s.props.color
  if (s.props?.geo) o.geo = s.props.geo
  if (s.parentId && !String(s.parentId).startsWith('page:')) {
    o.pai = s.parentId
    if (larguraLateral(editor.getShape(s.parentId))) o.coluna = s.meta?.coluna === 'lateral' ? 'lateral' : 'principal'
  }
  return o
}

function aDireita(editor) {
  const b = editor.getCurrentPageBounds()
  return b ? { x: b.maxX + 80, y: b.minY } : { x: 0, y: 0 }
}

function focar(editor, ids) {
  const anim = { animation: { duration: 300 } }
  if (ids?.length) {
    const b = T.Box.Common(ids.map((id) => editor.getShapePageBounds(id)).filter(Boolean))
    if (b) editor.zoomToBounds(b, { ...anim, inset: 80, targetZoom: 1 })
  } else editor.zoomToFit(anim)
}

function precisa(editor, id, tipo) {
  const s = editor.getShape(id)
  if (!s) throw new Error(`não achei a forma ${id}`)
  if (tipo && s.type !== tipo) throw new Error(`${id} é ${s.type}, não ${tipo}`)
  return s
}

async function aplicar(editor, op) {
  switch (op.tipo) {
    case 'tela_criar': {
      const id = T.createShapeId()
      const pos = op.x != null && op.y != null ? { x: op.x, y: op.y } : aDireita(editor)
      editor.createShape({ id, type: 'tela', x: pos.x, y: pos.y, props: { w: op.w, h: op.h, nome: op.nome, html: op.html } })
      editor.select(id)
      focar(editor, [id])
      return { id }
    }
    case 'tela_mudar': {
      const s = precisa(editor, op.id, 'tela')
      const props = {}
      for (const k of ['html', 'nome', 'w', 'h']) if (op[k] != null) props[k] = op[k]
      editor.updateShape({ id: s.id, type: 'tela', props })
      return { id: s.id }
    }
    case 'tela_ler': {
      const s = precisa(editor, op.id, 'tela')
      return { id: s.id, nome: s.props.nome, w: s.props.w, h: s.props.h, html: s.props.html }
    }
    case 'ler': {
      const formas = op.ids?.length ? op.ids.map((id) => editor.getShape(id)).filter(Boolean) : editor.getCurrentPageShapesSorted()
      return { formas: formas.map((s) => simples(editor, s)), selecao: editor.getSelectedShapeIds() }
    }
    case 'criar': {
      const ids = []
      const formas = op.formas.map((f) => {
        const id = T.createShapeId(); ids.push(id)
        const props = {}
        if (f.cor) props.color = f.cor
        if (f.tipo === 'geo') { props.geo = f.geo ?? 'rectangle'; props.w = f.w ?? 200; props.h = f.h ?? 120; if (f.texto) props.richText = T.toRichText(f.texto) }
        if (f.tipo === 'text') { props.richText = T.toRichText(f.texto ?? ''); if (f.w) { props.w = f.w; props.autoSize = false } }
        if (f.tipo === 'note') props.richText = T.toRichText(f.texto ?? '')
        if (f.tipo === 'frame') { props.w = f.w ?? 400; props.h = f.h ?? 300; if (f.texto) props.name = f.texto; delete props.color }
        return { id, type: f.tipo, x: f.x, y: f.y, props }
      })
      editor.createShapes(formas)
      return { ids }
    }
    case 'mudar': {
      const parciais = op.mudancas.map((m) => {
        const s = precisa(editor, m.id)
        const p = { id: s.id, type: s.type }
        if (m.x != null) p.x = m.x
        if (m.y != null) p.y = m.y
        const props = {}
        if (m.w != null && 'w' in s.props) props.w = m.w
        if (m.h != null && 'h' in s.props) props.h = m.h
        if (m.cor && 'color' in s.props) props.color = m.cor
        if (m.texto != null) {
          if ('richText' in s.props) props.richText = T.toRichText(m.texto)
          else if (s.type === 'frame') props.name = m.texto
          else if (s.type === 'tela') props.nome = m.texto
        }
        if (Object.keys(props).length) p.props = props
        return p
      })
      editor.updateShapes(parciais)
      return { ids: parciais.map((p) => p.id) }
    }
    case 'apagar': {
      const ids = op.ids.filter((id) => editor.getShape(id))
      editor.deleteShapes(ids)
      return { apagadas: ids }
    }
    case 'focar':
      focar(editor, op.ids)
      return { ok: true }
    case 'tela_montar': {
      const resolver = (lista) => Promise.all((lista ?? []).map(async (p) => ({ def: await W.exigirComponente(p.componente), dados: p.dados })))
      const pecas = await resolver(op.pecas)
      const lateral = op.lateral ? await resolver(op.lateral.pecas) : null
      const id = T.createShapeId()
      const pos = op.x != null && op.y != null ? { x: op.x, y: op.y } : aDireita(editor)
      const w = op.w ?? 393
      const L = lateral ? Number(op.lateral.largura) : 0
      if (lateral && !(L > 0 && L < w)) throw new Error(`lateral.largura ${op.lateral.largura} não cabe numa tela de ${w}`)
      const ids = []
      const idsLateral = []
      editor.run(() => {
        const meta = lateral ? { pilha: true, lateral: L } : { pilha: true }
        editor.createShape({ id, type: 'frame', x: pos.x, y: pos.y, props: { w, h: op.h ?? 852, name: op.nome ?? 'Tela' }, meta })
        // a variante vem da largura do frame (w), inclusive na coluna lateral
        const coluna = (lista, guardar, nome) => {
          let y = 0
          return lista.map(({ def, dados }) => {
            const pid = T.createShapeId(); guardar.push(pid)
            const props = propsDaInstancia(def, w, dados)
            const forma = { id: pid, type: 'widget', parentId: id, x: nome === 'lateral' ? 0 : L, y, props }
            if (lateral) forma.meta = { coluna: nome }
            y += props.h
            return forma
          })
        }
        const formas = [...(lateral ? coluna(lateral, idsLateral, 'lateral') : []), ...coluna(pecas, ids, 'principal')]
        if (formas.length) editor.createShapes(formas)
        empilhar(editor, id)
      })
      editor.select(id)
      focar(editor, [id])
      return lateral ? { id, pecas: ids, lateral: idsLateral } : { id, pecas: ids }
    }
    case 'instancia_inserir': {
      const f = precisa(editor, op.tela, 'frame')
      const def = await W.exigirComponente(op.componente)
      return { id: inserirNoFrame(editor, f.id, def, op.dados, op.indice, op.coluna) }
    }
    case 'instancia_mudar': {
      const s = precisa(editor, op.id, 'widget')
      const dados = { ...dadosDe(s), ...(op.dados ?? {}) }
      editor.updateShape({ id: s.id, type: 'widget', props: { dados: JSON.stringify(dados) } })
      return { id: s.id }
    }
    case 'agrupar': {
      const ids = (op.ids ?? []).filter((id) => editor.getShape(id))
      if (ids.length < 2) throw new Error('agrupar precisa de pelo menos duas formas que existam')
      const gid = T.createShapeId()
      editor.groupShapes(ids, { groupId: gid, select: true })
      const g = editor.getShape(gid)
      if (!g) throw new Error('o tldraw não agrupou essas formas')
      empilhar(editor, g.parentId)
      return { id: gid }
    }
    default:
      throw new Error(`operação desconhecida: ${op.tipo}`)
  }
}

async function responder(pedido, corpo) {
  const body = JSON.stringify({ pedido, ...corpo })
  await fetch('/api/canvas/resposta', { method: 'POST', headers: { 'content-type': 'application/json' }, body, keepalive: body.length < 60_000 })
    .catch((e) => console.warn('[canvas] resposta não enviada', e))
}

async function executar({ pedido, op }) {
  const editor = playground.editor
  if (!editor || !T) { fila.push({ pedido, op }); return }
  let r
  try { r = { ok: true, resultado: await aplicar(editor, op) } } catch (e) { r = { ok: false, erro: String(e?.message ?? e) } }
  responder(pedido, r)
}

window.addEventListener('playground:canvas', (ev) => executar(ev.detail))
// uma definição mudou (o chat.js repassa o SSE `componente`): as instâncias daquele id se redesenham
window.addEventListener('playground:componente', (ev) => { W.receber(ev.detail) })

async function montar() {
  let React, createRoot, Tldraw, TelaUtil, WidgetUtil
  try {
    const [r, rd, t] = await Promise.all([import(REACT), import(REACT_DOM), import(TLDRAW)])
    React = r.default
    createRoot = rd.createRoot
    Tldraw = t.Tldraw
    T = t
    TelaUtil = criarTelaUtil(React, t)
    WidgetUtil = criarWidgetUtil(React, t)
  } catch (e) {
    console.error('[canvas] tldraw não carregou', e)
    aviso('O canvas não carregou.', `Não deu para baixar o tldraw do esm.sh (${e?.message ?? e}). O chat continua funcionando.`)
    return
  }

  const caixa = document.createElement('div')
  caixa.className = 'canvas-raiz'
  raiz.replaceChildren(caixa)

  async function onMount(editor) {
    playground.editor = editor
    const migrados = await carregar(editor)
    ouvir(editor)
    salvarMigrados(editor, migrados)
    ouvirPilhas(editor)
    montarPaleta({
      raiz,
      componentes: W.componentes,
      aoMudar: W.aoMudar,
      produtoDe: W.produtoDe,
      soltar: (componente, cliente) => soltarComponente(editor, componente, editor.screenToPage(cliente)),
      clicar: (componente) => clicarComponente(editor, componente),
    })
    for (const item of fila.splice(0)) executar(item)
  }

  try {
    createRoot(caixa).render(React.createElement(Tldraw, { onMount, shapeUtils: [TelaUtil, WidgetUtil] }))
  } catch (e) {
    console.error('[canvas] tldraw não montou', e)
    aviso('O canvas não montou.', String(e?.message ?? e))
  }
}

montar()
