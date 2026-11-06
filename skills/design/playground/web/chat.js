// Chat widget do design-playground: monta o chat em #chat e o estado do motor em #motor.
// Contrato: ../CONTRATO.md (Mensagem, Motor, HTTP, SSE, Página). Sem build; dependências fixadas no esm.sh.
import { marked } from "https://esm.sh/marked@18.1.3";
import DOMPurify from "https://esm.sh/dompurify@3.4.17";

const ROTA_EVENTOS = "/api/eventos";
const ROTA_MENSAGENS = "/api/mensagens";
const PERTO_DO_FIM_PX = 48; // abaixo disso, conta como "estava no fim" e rola sozinho
const ESPERA_RECRIAR_MS = 3000; // quando o EventSource fecha de vez (não reconecta sozinho)

const TEXTO_MOTOR = {
  ouvindo: "agente ouvindo",
  ocupado: "agente ocupado",
  "sem-agente": "sem agente",
  conectando: "conectando…",
  desconectado: "sem conexão com o servidor",
};

marked.setOptions({ gfm: true, breaks: true });

// Links do agente abrem fora da página, sem dar acesso a ela.
DOMPurify.addHook("afterSanitizeAttributes", (no) => {
  if (no.tagName === "A" && no.hasAttribute("href")) {
    no.setAttribute("target", "_blank");
    no.setAttribute("rel", "noopener noreferrer");
  }
});

// ---------- estado ----------

const estado = {
  motor: "conectando",
  conectado: false,
  digitando: false,
  /** @type {Map<string, {id:string, autor:"pessoa"|"agente", texto:string, em:string, selecao?:string[]}>} */
  mensagens: new Map(),
  /** envios ainda não confirmados pelo SSE: { chave, texto, selecao, em, id? } */
  pendentes: [],
};

// ---------- DOM ----------

const raiz = document.getElementById("chat");
const cabecaMotor = document.getElementById("motor");
if (!raiz) throw new Error("chat.js: falta <aside id=\"chat\"> na página");

const el = (tag, props = {}, ...filhos) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k in n && typeof v !== "string") n[k] = v;
    else n.setAttribute(k, v);
  }
  for (const f of filhos) if (f != null) n.append(f);
  return n;
};

raiz.replaceChildren();
raiz.classList.add("chat");
if (!raiz.hasAttribute("aria-label")) raiz.setAttribute("aria-label", "Chat com o agente");

const lista = el("ol", {
  class: "chat-lista",
  role: "log",
  "aria-live": "polite",
  "aria-relevant": "additions",
  "aria-label": "Mensagens",
  tabindex: "0",
});
const vazio = el("div", { class: "chat-vazio" });
const rolagem = el("div", { class: "chat-rolagem" }, vazio, lista);

const digitando = el(
  "div",
  { class: "chat-digitando", role: "status", "aria-live": "polite" },
);
const pontosDigitando = el("span", { class: "chat-digitando-pontos", "aria-hidden": "true" },
  el("span"), el("span"), el("span"));
const textoDigitando = el("span", { class: "chat-digitando-texto" });
digitando.append(pontosDigitando, textoDigitando);

const campoId = "chat-campo";
const campo = el("textarea", {
  id: campoId,
  class: "chat-campo",
  rows: "1",
  placeholder: "Descreva uma tela ou o que mudar…",
  "aria-describedby": "chat-dica chat-erro",
  autocomplete: "off",
});
const rotulo = el("label", { class: "chat-oculto", for: campoId, text: "Mensagem para o agente" });
const botao = el("button", { class: "chat-enviar", type: "submit", text: "Enviar", disabled: true });
const dica = el("p", { id: "chat-dica", class: "chat-dica", text: "Enter envia · Shift+Enter quebra a linha" });
const erro = el("p", { id: "chat-erro", class: "chat-erro", role: "alert" });
const form = el(
  "form",
  { class: "chat-form", novalidate: true },
  rotulo,
  el("div", { class: "chat-entrada" }, campo, botao),
  erro,
  dica,
);

raiz.append(rolagem, digitando, form);

let motorTexto = null;
if (cabecaMotor) {
  cabecaMotor.querySelector(".motor-estado")?.remove();
  motorTexto = el("span", { class: "motor-texto" });
  const motorEstado = el(
    "span",
    { class: "motor-estado", role: "status", "aria-live": "polite" },
    el("span", { class: "motor-ponto", "aria-hidden": "true" }),
    motorTexto,
  );
  cabecaMotor.append(motorEstado);
}

// ---------- formatação ----------

const formatoHora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
const formatoCompleto = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" });

function hora(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return el("time", { class: "chat-hora", datetime: d.toISOString(), title: formatoCompleto.format(d), text: formatoHora.format(d) });
}

function seloSelecao(selecao) {
  const n = Array.isArray(selecao) ? selecao.length : 0;
  if (!n) return null;
  return el("span", {
    class: "chat-selo",
    title: selecao.join(", "),
    text: n === 1 ? "1 forma selecionada" : `${n} formas selecionadas`,
  });
}

function corpoAgente(texto) {
  const div = el("div", { class: "chat-texto chat-md" });
  try {
    div.innerHTML = DOMPurify.sanitize(marked.parse(String(texto ?? "")));
  } catch {
    div.textContent = String(texto ?? "");
  }
  return div;
}

function itemMensagem(m) {
  if (m.tipo === "atividade") {
    return el("li", { class: "chat-msg chat-atividade", "data-id": m.id },
      el("span", { class: "chat-atividade-ponto", "aria-hidden": "true" }),
      el("span", { class: "chat-atividade-texto", text: m.texto }),
      hora(m.em));
  }
  const daPessoa = m.autor === "pessoa";
  const balao = el(
    "div",
    { class: "chat-balao" },
    el("span", { class: "chat-oculto", text: daPessoa ? "Você: " : "Agente: " }),
    daPessoa ? el("div", { class: "chat-texto", text: m.texto }) : corpoAgente(m.texto),
  );
  const meta = el("div", { class: "chat-meta" }, seloSelecao(m.selecao), hora(m.em));
  return el(
    "li",
    { class: `chat-msg ${daPessoa ? "chat-msg-pessoa" : "chat-msg-agente"}`, "data-id": m.id },
    balao,
    meta,
  );
}

function itemPendente(p) {
  const meta = el(
    "div",
    { class: "chat-meta" },
    seloSelecao(p.selecao),
    el("span", { class: "chat-enviando", text: "enviando…" }),
  );
  return el(
    "li",
    { class: "chat-msg chat-msg-pessoa chat-msg-pendente", "data-pendente": p.chave, "aria-busy": "true" },
    el("div", { class: "chat-balao" },
      el("span", { class: "chat-oculto", text: "Você (enviando): " }),
      el("div", { class: "chat-texto", text: p.texto })),
    meta,
  );
}

// ---------- render ----------

function estavaNoFim() {
  return rolagem.scrollHeight - rolagem.scrollTop - rolagem.clientHeight <= PERTO_DO_FIM_PX;
}

function rolarAoFim() {
  rolagem.scrollTop = rolagem.scrollHeight;
}

function ordenadas() {
  return [...estado.mensagens.values()].sort((a, b) => {
    const d = Date.parse(a.em) - Date.parse(b.em);
    return Number.isNaN(d) || d === 0 ? 0 : d;
  });
}

function renderVazio() {
  const semNada = estado.mensagens.size === 0 && estado.pendentes.length === 0;
  vazio.hidden = !semNada;
  if (!semNada) return;
  const filhos = [
    el("p", { class: "chat-vazio-titulo", text: "Descreva uma tela para começar." }),
    el("p", {
      text: "Por exemplo: “uma tela de login para celular, com e-mail, senha e um botão de entrar”. Depois, selecione algo no canvas e peça o que mudar.",
    }),
  ];
  if (estado.motor === "sem-agente") {
    filhos.push(
      el("div", { class: "chat-aviso" },
        el("p", { text: "Nenhum agente está conectado. Para conectar o Claude Code, rode:" }),
        el("pre", {}, el("code", { text: "claude mcp add design-playground -- bun run <caminho>/src/main.ts" })),
        el("p", { text: "e abra uma sessão; o agente passa a ouvir este chat." })),
    );
  }
  vazio.replaceChildren(...filhos);
}

function renderTudo() {
  const noFim = estavaNoFim();
  lista.replaceChildren(...ordenadas().map(itemMensagem), ...estado.pendentes.map(itemPendente));
  renderVazio();
  if (noFim) rolarAoFim();
}

function acrescentar(m) {
  if (estado.mensagens.has(m.id)) return;
  const noFim = estavaNoFim();
  estado.mensagens.set(m.id, m);
  const removidos = conciliarPendentes();
  const item = itemMensagem(m);
  // Normalmente chega em ordem; se não, encaixa antes da primeira mais nova.
  const t = Date.parse(m.em);
  let antes = null;
  if (!Number.isNaN(t)) {
    for (const li of lista.querySelectorAll(".chat-msg[data-id]")) {
      const outra = estado.mensagens.get(li.dataset.id);
      if (outra && Date.parse(outra.em) > t) { antes = li; break; }
    }
  }
  antes ??= lista.querySelector(".chat-msg-pendente");
  lista.insertBefore(item, antes);
  for (const chave of removidos) lista.querySelector(`[data-pendente="${chave}"]`)?.remove();
  renderVazio();
  if (noFim || m.autor === "pessoa") rolarAoFim();
}

/** Tira os pendentes que já voltaram pelo SSE. Devolve as chaves removidas. */
function conciliarPendentes() {
  const removidos = [];
  const usadas = new Set();
  estado.pendentes = estado.pendentes.filter((p) => {
    let chegou = p.id ? estado.mensagens.has(p.id) : false;
    if (!chegou && !p.id) {
      // Antes do 201 não há id: casa pela primeira mensagem nova da pessoa com o mesmo texto.
      for (const m of estado.mensagens.values()) {
        if (m.autor === "pessoa" && m.texto === p.texto && !p.conhecidas.has(m.id) && !usadas.has(m.id)) {
          usadas.add(m.id);
          chegou = true;
          break;
        }
      }
    }
    if (chegou) removidos.push(p.chave);
    return !chegou;
  });
  return removidos;
}

function renderDigitando() {
  const noFim = estavaNoFim();
  digitando.classList.toggle("ativo", estado.digitando);
  textoDigitando.textContent = estado.digitando ? (estado.atividade ? `${estado.atividade}…` : "agente digitando…") : "";
  if (noFim) rolarAoFim();
}

function renderMotor() {
  const chave = estado.conectado ? estado.motor : (estado.motor === "conectando" ? "conectando" : "desconectado");
  if (cabecaMotor) {
    cabecaMotor.dataset.motor = chave;
    if (motorTexto) motorTexto.textContent = TEXTO_MOTOR[chave] ?? String(chave);
  }
  raiz.dataset.motor = chave;
  renderVazio();
}

// ---------- SSE ----------

let fonte = null;
let recriar = null;

function lerJSON(ev) {
  try { return JSON.parse(ev.data); } catch { return null; }
}

function conectar() {
  clearTimeout(recriar);
  fonte?.close();
  fonte = new EventSource(ROTA_EVENTOS);

  fonte.addEventListener("open", () => {
    estado.conectado = true;
    renderMotor();
  });

  fonte.addEventListener("ola", (ev) => {
    const d = lerJSON(ev);
    if (!d) return;
    estado.conectado = true;
    estado.motor = d.motor ?? estado.motor;
    estado.digitando = Boolean(d.digitando);
    estado.atividade = d.atividade ?? null;
    estado.mensagens = new Map((d.mensagens ?? []).map((m) => [m.id, m]));
    conciliarPendentes();
    renderTudo();
    renderDigitando();
    renderMotor();
  });

  fonte.addEventListener("mensagem", (ev) => {
    const m = lerJSON(ev);
    if (m?.id) acrescentar(m);
  });

  fonte.addEventListener("digitando", (ev) => {
    const d = lerJSON(ev);
    if (!d) return;
    estado.digitando = Boolean(d.ativo);
    estado.atividade = d.texto ?? null;
    renderDigitando();
  });

  // As operações do canvas vão para o canvas.js (uma conexão SSE por aba).
  fonte.addEventListener("canvas", (ev) => {
    const d = lerJSON(ev);
    if (d?.pedido) window.dispatchEvent(new CustomEvent("playground:canvas", { detail: d }));
  });

  // Uma definição de componente mudou: o canvas.js redesenha as instâncias daquele id (todas as abas recebem).
  fonte.addEventListener("componente", (ev) => {
    const d = lerJSON(ev);
    if (d?.id) window.dispatchEvent(new CustomEvent("playground:componente", { detail: d }));
  });

  fonte.addEventListener("apagada", (ev) => {
    const d = lerJSON(ev);
    if (!d?.id || !estado.mensagens.delete(d.id)) return;
    lista.querySelector(`.chat-msg[data-id="${CSS.escape(d.id)}"]`)?.remove();
    renderVazio();
  });

  fonte.addEventListener("motor", (ev) => {
    const d = lerJSON(ev);
    if (!d?.estado) return;
    estado.motor = d.estado;
    renderMotor();
  });

  fonte.addEventListener("error", () => {
    estado.conectado = false;
    if (estado.motor === "conectando") estado.motor = "desconectado";
    renderMotor();
    // CONNECTING: o navegador reconecta sozinho. CLOSED (ex.: resposta não-SSE): recria aqui.
    if (fonte.readyState === EventSource.CLOSED) recriar = setTimeout(conectar, ESPERA_RECRIAR_MS);
  });
}

// ---------- envio ----------

let seqPendente = 0;

function selecaoAtual() {
  try {
    const s = window.playground?.selecao?.() ?? [];
    return Array.isArray(s) ? s.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function ajustarAltura() {
  campo.style.height = "auto";
  campo.style.height = `${campo.scrollHeight}px`; // o max-height do CSS limita e liga a rolagem
}

function atualizarBotao() {
  botao.disabled = campo.value.trim() === "";
}

function mostrarErro(texto) {
  erro.textContent = texto;
  erro.hidden = !texto;
}

async function enviar() {
  const texto = campo.value;
  if (texto.trim() === "") return;
  const selecao = selecaoAtual();
  const p = { chave: `p${++seqPendente}`, texto, selecao, conhecidas: new Set(estado.mensagens.keys()) };

  mostrarErro("");
  estado.pendentes.push(p);
  lista.append(itemPendente(p));
  renderVazio();
  rolarAoFim();
  campo.value = "";
  ajustarAltura();
  atualizarBotao();

  try {
    const r = await fetch(ROTA_MENSAGENS, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ texto, selecao }),
    });
    if (r.status !== 201) {
      let motivo = `${r.status} ${r.statusText}`.trim();
      try {
        const corpo = await r.json();
        if (corpo?.erro || corpo?.error) motivo = corpo.erro ?? corpo.error;
      } catch {}
      throw new Error(motivo);
    }
    const { mensagem } = await r.json();
    if (mensagem?.id) {
      p.id = mensagem.id;
      if (estado.mensagens.has(mensagem.id) || !estado.conectado) {
        // Já veio pelo SSE, ou o SSE está fora: mostra a confirmada no lugar da pendente.
        if (!estado.mensagens.has(mensagem.id)) acrescentar(mensagem);
        const removidos = conciliarPendentes();
        for (const chave of removidos) lista.querySelector(`[data-pendente="${chave}"]`)?.remove();
        renderVazio();
      }
      // Senão, a pendente some quando a mensagem chegar pelo SSE.
    }
  } catch (e) {
    estado.pendentes = estado.pendentes.filter((x) => x !== p);
    lista.querySelector(`[data-pendente="${p.chave}"]`)?.remove();
    renderVazio();
    // Devolve o texto ao campo sem apagar o que a pessoa já começou a digitar de novo.
    campo.value = campo.value.trim() ? `${texto}\n${campo.value}` : texto;
    ajustarAltura();
    atualizarBotao();
    mostrarErro(`Não foi possível enviar: ${e instanceof Error ? e.message : String(e)}. O texto voltou para o campo.`);
    campo.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  enviar();
});

campo.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
    e.preventDefault();
    enviar();
  }
});

campo.addEventListener("input", () => {
  ajustarAltura();
  atualizarBotao();
});

// ---------- início ----------

mostrarErro("");
renderTudo();
renderDigitando();
renderMotor();
conectar();
