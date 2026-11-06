// A linha viva com o servidor (SSE): repassa ao canvas.js as operações do agente (`canvas`) e as definições novas
// de componente (`componente`) como eventos da window. Faz o papel que o chat.js fazia, sem o chat.
const ESPERA_RECRIAR_MS = 3000 // quando o EventSource fecha de vez (não reconecta sozinho)

function conectar() {
  const fonte = new EventSource('/playground/api/eventos')
  const repassar = (tipo, nome, chave) => fonte.addEventListener(tipo, (ev) => {
    try {
      const d = JSON.parse(ev.data)
      if (d?.[chave]) window.dispatchEvent(new CustomEvent(nome, { detail: d }))
    } catch (e) { console.warn(`[eventos] ${tipo} ilegível`, e) }
  })
  repassar('canvas', 'playground:canvas', 'pedido')
  repassar('componente', 'playground:componente', 'id')
  fonte.onerror = () => { if (fonte.readyState === EventSource.CLOSED) setTimeout(conectar, ESPERA_RECRIAR_MS) }
}

conectar()
