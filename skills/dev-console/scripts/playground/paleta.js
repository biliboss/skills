// A paleta: um painel recolhível no canto superior esquerdo do canvas com os
// componentes de /api/componentes, por produto, com o estado. Arrastar um componente
// e soltar no canvas cria uma instância no ponto (dentro de um frame com pilha, vira
// filha dele); clicar a insere no fim do frame selecionado.

export const TIPO_ARRASTO = 'application/x-playground-componente'
const CHAVE_ABERTA = 'playground:paleta-aberta'

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue
    if (k === 'text') e.textContent = v
    else if (k === 'class') e.className = v
    else e.setAttribute(k, v === true ? '' : v)
  }
  e.append(...filhos.filter(Boolean))
  return e
}

/**
 * @param {{ raiz: HTMLElement,
 *   componentes: (o?: {recarregar?: boolean}) => Promise<any[]>,
 *   aoMudar?: (fn: (id: string) => void) => () => void,
 *   produtoDe: (id: string) => string,
 *   soltar: (componente: string, cliente: {x: number, y: number}) => Promise<unknown>,
 *   clicar: (componente: string) => Promise<unknown> }} opcoes
 */
export function montarPaleta({ raiz, componentes, aoMudar, produtoDe, soltar, clicar }) {
  let aberta = localStorage.getItem(CHAVE_ABERTA) !== '0'

  const botao = el('button', { type: 'button', class: 'paleta-cab', 'aria-controls': 'paleta-corpo' },
    el('span', { class: 'paleta-titulo', text: 'Componentes' }),
    el('span', { class: 'paleta-seta', 'aria-hidden': 'true' }))
  const corpo = el('div', { class: 'paleta-corpo', id: 'paleta-corpo' })
  const painel = el('section', { class: 'paleta', 'aria-label': 'Paleta de componentes' }, botao, corpo)
  raiz.append(painel)

  function mostrarEstado() {
    painel.classList.toggle('is-aberta', aberta)
    botao.setAttribute('aria-expanded', String(aberta))
    corpo.hidden = !aberta
  }

  function aviso(texto) {
    corpo.replaceChildren(el('p', { class: 'paleta-aviso', text: texto }))
  }

  function item(c) {
    const rascunho = c.estado === 'rascunho'
    return el('li', {},
      el('button', {
        type: 'button', class: 'paleta-peca', draggable: 'true',
        'data-componente': c.id,
        title: `${c.id}: arraste para o canvas, ou clique com uma tela selecionada`,
      },
        el('span', { class: 'paleta-peca-linha' },
          el('span', { class: 'paleta-peca-nome', text: c.nome ?? c.id }),
          rascunho ? el('span', { class: 'paleta-selo', text: 'rascunho' }) : null),
        c.descricao ? el('span', { class: 'paleta-peca-desc', text: c.descricao }) : null))
  }

  function desenhar(lista) {
    if (!lista.length) { aviso('Nenhum componente definido ainda.'); return }
    const porProduto = new Map()
    for (const c of lista) {
      const p = produtoDe(c.id)
      if (!porProduto.has(p)) porProduto.set(p, [])
      porProduto.get(p).push(c)
    }
    const produtos = [...porProduto.keys()].sort((a, b) => a.localeCompare(b))
    corpo.replaceChildren(...produtos.map((p) => el('div', { class: 'paleta-kit', 'data-produto': p },
      el('h3', { class: 'paleta-kit-nome', text: p }),
      el('ul', { class: 'paleta-pecas', role: 'list' }, ...porProduto.get(p).map(item)))))
  }

  let carregando = null
  let deNovo = false
  function carregar(recarregar) {
    if (carregando) { deNovo = deNovo || recarregar; return carregando }
    if (!corpo.childElementCount) aviso('Carregando…')
    carregando = componentes({ recarregar })
      .then(desenhar)
      .catch((e) => { console.warn('[paleta] componentes não carregaram', e); aviso('Os componentes não carregaram.') })
      .finally(() => {
        carregando = null
        if (deNovo) { deNovo = false; carregar(false) }
      })
    return carregando
  }

  botao.addEventListener('click', () => {
    aberta = !aberta
    localStorage.setItem(CHAVE_ABERTA, aberta ? '1' : '0')
    mostrarEstado()
    if (aberta) carregar(true)
  })

  const peca = (alvo) => alvo instanceof Element ? alvo.closest('.paleta-peca') : null

  corpo.addEventListener('click', (e) => {
    const b = peca(e.target)
    if (b) clicar(b.dataset.componente).catch((err) => console.warn('[paleta] não inseriu', err))
  })

  corpo.addEventListener('dragstart', (e) => {
    const b = peca(e.target)
    if (!b || !e.dataTransfer) return
    e.dataTransfer.setData(TIPO_ARRASTO, JSON.stringify({ componente: b.dataset.componente }))
    e.dataTransfer.effectAllowed = 'copy'
    b.classList.add('is-arrastando')
  })
  corpo.addEventListener('dragend', (e) => peca(e.target)?.classList.remove('is-arrastando'))

  // o soltar no canvas: na captura, antes do tldraw (que trata arquivos e links soltos)
  const nosso = (e) => e.dataTransfer && [...e.dataTransfer.types].includes(TIPO_ARRASTO)
  raiz.addEventListener('dragover', (e) => {
    if (!nosso(e)) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
  }, true)
  raiz.addEventListener('drop', (e) => {
    if (!nosso(e)) return
    e.preventDefault()
    e.stopPropagation()
    if (painel.contains(e.target)) return
    let item
    try { item = JSON.parse(e.dataTransfer.getData(TIPO_ARRASTO)) } catch { return }
    if (!item?.componente) return
    soltar(item.componente, { x: e.clientX, y: e.clientY }).catch((err) => console.warn('[paleta] não soltou', err))
  }, true)

  // uma definição nova ou que mudou (o SSE `componente` já releu a lista): redesenha sem buscar de novo
  aoMudar?.(() => carregar(false))

  mostrarEstado()
  carregar(false)
  return painel
}
