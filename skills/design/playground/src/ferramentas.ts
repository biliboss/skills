/**
 * O servidor MCP: as instruções do `initialize` e as ferramentas (web e chat,
 * telas, canvas, componentes e instâncias). Um McpServer por sessão (stdio,
 * cada sessão HTTP, cada cliente em memória dos testes); o motor único entre
 * elas fica no Chat (`assumir`/`terminar`).
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import type { Canvas } from "./canvas.ts";
import type { Chat } from "./chat.ts";
import { ID_COMPONENTE, type Componentes } from "./componentes.ts";
import type { Operacoes } from "./operacoes.ts";
import { log } from "./tipos.ts";

export const VERSAO = "0.2.0";
export const PROGRESSO_MS = 15_000;

export const INSTRUCOES = `Você é o motor do design-playground: uma Web com um canvas do tldraw no centro e um chat à direita, como um mini Figma. A pessoa escreve no chat e você recebe por aqui; não há outro LLM no meio. Você desenha no canvas pelas ferramentas tela_*, instancia_*, componente_* e canvas_*.

Este MCP não conhece nenhum produto. Ele guarda componentes (a definição de uma peça: HTML, CSS, tamanho, os slots que recebem dados) e desenha instâncias deles; cada instância tem os próprios dados, e mudar a definição redesenha todas as instâncias, como no Figma. Os componentes vêm de fora:
- Peça que já existe no produto: a skill design acha o widget no código do produto e escreve um wrapper (uma pasta com componente.json, peca.html, peca.css…). Chame componente_definir({pasta}) com o caminho absoluto dessa pasta. Se a skill design não estiver carregada, carregue-a.
- Peça nova, que o produto ainda não tem: escreva o HTML e o CSS e chame componente_definir({componente}) com estado "rascunho". Ela aparece no canvas com a faixa "rascunho".

Como trabalhar:
1. Abra a Web com web_abrir (ela devolve a URL; mostre-a à pessoa).
2. Fique em chat_aguardar: é uma espera longa, que só volta quando a pessoa escreve (ou volta com uma lista vazia quando o tempo acaba).
3. Enquanto trabalha, conte cada passo com chat_atividade, uma linha curta no gerúndio ("lendo os componentes do Via", "escrevendo o wrapper do cartão", "montando a tela Busca"). Isso tira a ansiedade de quem espera.
4. Antes de montar, veja o que já está definido com componente_listar (os ids, as chaves de dados e o estado de cada um). Falta uma peça: defina-a como acima.
5. Monte cada tela com tela_montar: um frame com as instâncias empilhadas de cima para baixo, cada uma com os dados do caso (textos, preços, bairros). Ajuste com instancia_mudar (só os dados que mudam), instancia_inserir (uma instância a mais numa tela) e canvas_agrupar (juntar formas num grupo). tela_criar, com um HTML inteiro, fica para um rascunho rápido de tela.
6. Toda tela sai sempre em duas versões, lado a lado: web (largura "desktop", 1280×800) e iPhone (largura "celular", 393×852). Num frame de 1024 ou mais, a instância usa a variante desktop do componente. Use canvas_criar para notas e rótulos e canvas_ler para ver o que existe.
7. Responda com chat_responder, curto, dizendo o que desenhou. Nunca diga "não consigo": se falta algo (um componente, um dado, uma ferramenta), diga que vai preparar e conte o que está fazendo.
8. Volte a chamar chat_aguardar sempre, também quando ele vier vazio. Fora de chat_aguardar, a Web mostra "agente ocupado".

Cada mensagem traz em "selecao" os ids das formas que a pessoa tinha selecionado no canvas ao enviar: "muda isso" se refere a elas (use canvas_ler com esses ids, e tela_ler para o HTML de uma tela). Use chat_historico para reler a conversa e chat_apagar para tirar uma mensagem sua.

Um motor por vez: se uma ferramenta responder "outra sessão já é o motor", outro agente está conduzindo a Web agora; diga isso a quem pediu e não insista.`;

export type ContextoFerramentas = {
  chat: Chat;
  operacoes?: Operacoes;
  /** As definições dos componentes (componente_*, tela_montar, instancia_*). */
  componentes?: Componentes;
  /** O espelho do canvas, para conferir as chaves em instancia_mudar. */
  canvas?: Canvas;
  url: string;
  /** Se outro processo já é o motor nesta porta, toda ferramenta devolve erro. */
  portaOcupada: boolean;
  /** Abre a URL no navegador (respeita ABRIR_WEB=0). Devolve se abriu. */
  abrirWeb: () => boolean;
  progressoMs?: number;
  /** O transporte desta sessão, para o log e o erro de quem é o motor. Padrão "stdio". */
  transporte?: string;
  /** Sem chamar nada por esse tempo, a sessão solta o motor (HTTP). Sem valor: só ao fechar. */
  ociosoMs?: number;
};

function texto(conteudo: string): CallToolResult {
  return { content: [{ type: "text", text: conteudo }] };
}

function falha(conteudo: string): CallToolResult {
  return { content: [{ type: "text", text: conteudo }], isError: true };
}

const mensagemDe = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function criarMcp(ctx: ContextoFerramentas): McpServer {
  const mcp = new McpServer({ name: "design-playground", version: VERSAO }, { instructions: INSTRUCOES });
  const progressoMs = ctx.progressoMs ?? PROGRESSO_MS;
  const transporte = ctx.transporte ?? "stdio";

  // ---------- a sessão e o motor ----------

  let sessao: string | null = null;
  let fechada = false;
  const rotulo = () => {
    const cliente = mcp.server.getClientVersion()?.name;
    return cliente ? `${transporte} (${cliente})` : transporte;
  };
  const entrar = () => {
    if (sessao === null && !fechada) sessao = ctx.chat.entrar(rotulo(), ctx.ociosoMs);
    return sessao;
  };

  // O motor acompanha a sessão: "ocupado" depois do initialize, "sem-agente" quando fecha.
  mcp.server.oninitialized = () => void entrar();
  mcp.server.onclose = () => {
    fechada = true;
    if (sessao === null) return;
    const id = sessao;
    sessao = null;
    ctx.chat.sair(id);
  };

  let jaChamou = false;
  /** Se a Web abriu nesta chamada (lido pelo web_abrir antes de qualquer await). */
  let abriuAgora = false;

  /**
   * Registra uma ferramenta que passa pela porta do motor: recusa se outro
   * processo tem a porta ou se outra sessão é o motor; senão esta sessão vira o
   * motor durante a chamada, e a Web abre na primeira chamada.
   */
  const registrar = ((nome: string, config: Record<string, unknown>, cb: (...a: unknown[]) => Promise<CallToolResult>) =>
    mcp.registerTool(nome, config as never, (async (...a: unknown[]) => {
      if (ctx.portaOcupada) return falha(`outra sessão já é o motor em ${ctx.url}`);
      const id = entrar();
      if (id === null) return falha("esta sessão já foi fechada");
      const vez = ctx.chat.assumir(id);
      if (!vez.ok) {
        return falha(
          `outra sessão já é o motor (${vez.dono}) em ${ctx.url}. Só uma sessão conduz a Web por vez: diga isso a quem pediu e não insista; a vez fica livre quando a outra sessão fecha${transporte === "stdio" ? "" : " ou fica ociosa"}.`,
        );
      }
      try {
        abriuAgora = false;
        if (!jaChamou) {
          jaChamou = true;
          abriuAgora = ctx.abrirWeb();
        }
        return await cb(...a);
      } finally {
        ctx.chat.terminar(id);
      }
    }) as never)) as McpServer["registerTool"];

  // ---------- web e chat ----------

  registrar(
    "web_abrir",
    {
      title: "Abrir a Web",
      description:
        "Abre a Web do design-playground (canvas no centro, chat à direita) no navegador da pessoa e devolve a URL. Chame no começo da sessão; depois fique em chat_aguardar.",
    },
    async () => {
      const abriu = abriuAgora || ctx.abrirWeb();
      return texto(
        abriu
          ? `Web aberta em ${ctx.url}. Agora chame chat_aguardar.`
          : `A Web está em ${ctx.url} (não abri o navegador: ABRIR_WEB=0). Agora chame chat_aguardar.`,
      );
    },
  );

  registrar(
    "chat_aguardar",
    {
      title: "Aguardar a pessoa",
      description:
        'Espera longa pela próxima mensagem da pessoa no chat. Volta assim que ela escreve, com {"mensagens": [...]}: as mensagens ainda não entregues a você, cada uma com id, texto, em (ISO) e selecao (ids das formas selecionadas no canvas no envio). Se o tempo acabar sem mensagem, volta com {"mensagens": []}: chame de novo. Depois de responder com chat_responder, volte sempre a chamar chat_aguardar.',
      inputSchema: {
        timeout_s: z.number().min(1).max(3600).optional().describe("Quantos segundos esperar antes de voltar vazio. Padrão 50."),
      },
    },
    async ({ timeout_s }, extra) => {
      const timeoutMs = (timeout_s ?? 50) * 1000;
      const token = extra._meta?.progressToken;
      let progresso = 0;
      const aviso =
        token === undefined
          ? undefined
          : setInterval(() => {
              progresso++;
              extra
                .sendNotification({
                  method: "notifications/progress",
                  params: { progressToken: token, progress: progresso, message: "aguardando a pessoa no chat" },
                })
                .catch((e) => log("não consegui mandar o progresso", e));
            }, progressoMs);

      try {
        const mensagens = await ctx.chat.aguardar(timeoutMs, extra.signal);
        return texto(JSON.stringify({ mensagens }));
      } finally {
        if (aviso) clearInterval(aviso);
      }
    },
  );

  registrar(
    "chat_responder",
    {
      title: "Responder no chat",
      description:
        'Publica a sua resposta no chat da Web, em Markdown, e esconde o "digitando…". Depois de responder, volte a chamar chat_aguardar.',
      inputSchema: {
        texto: z.string().describe("A resposta, em Markdown."),
      },
    },
    async ({ texto: conteudo }) => {
      if (conteudo.trim() === "") return falha("texto vazio: nada foi publicado");
      const mensagem = ctx.chat.responderComoAgente(conteudo);
      return texto(JSON.stringify({ mensagem }));
    },
  );

  registrar(
    "chat_digitando",
    {
      title: 'Mostrar "digitando…"',
      description:
        'Mostra (ativo: true) ou esconde (ativo: false) o "digitando…" no chat da Web. Use antes de um trabalho demorado; chat_responder e chat_aguardar escondem sozinhos.',
      inputSchema: {
        ativo: z.boolean().describe("true mostra, false esconde."),
      },
    },
    async ({ ativo }) => {
      ctx.chat.definirDigitando(ativo);
      return texto(ativo ? "digitando… visível" : "digitando… escondido");
    },
  );

  registrar(
    "chat_historico",
    {
      title: "Histórico do chat",
      description:
        'Devolve a conversa até aqui, da mais antiga para a mais nova, como {"mensagens": [...]} (autor "pessoa" ou "agente"). Não marca nada como entregue: para receber mensagens novas, use chat_aguardar.',
      inputSchema: {
        limite: z.number().int().min(1).max(10_000).optional().describe("Quantas mensagens, contando do fim. Padrão 50."),
      },
    },
    async ({ limite }) => texto(JSON.stringify({ mensagens: ctx.chat.ultimas(limite ?? 50) })),
  );

  registrar(
    "chat_atividade",
    {
      title: "Contar o que está fazendo",
      description:
        'Põe uma linha de atividade no chat (ex.: "montando a tela Busca") e mostra esse texto no lugar do "digitando…". Use a cada passo de um trabalho que leva mais que alguns segundos.',
      inputSchema: { texto: z.string().min(1).max(200).describe("Uma linha curta, no gerúndio.") },
    },
    async ({ texto: linha }) => texto(JSON.stringify({ mensagem: ctx.chat.atividade(linha) })),
  );

  registrar(
    "chat_apagar",
    {
      title: "Apagar uma mensagem",
      description: "Apaga uma mensagem do chat pelo id (por exemplo, uma resposta sua que estava errada).",
      inputSchema: { id: z.string().describe("O id da mensagem (veja chat_historico).") },
    },
    async ({ id }) => (ctx.chat.apagar(id) ? texto(`apagada: ${id}`) : falha(`não achei a mensagem ${id}`)),
  );

  // ---------- canvas ----------

  /** Manda uma operação à página aberta e devolve o que ela respondeu. */
  async function operar(op: Record<string, unknown>): Promise<CallToolResult> {
    if (!ctx.operacoes) return falha("o canvas não está ligado neste servidor");
    try {
      const resultado = await ctx.operacoes.executar(op);
      return texto(JSON.stringify(resultado));
    } catch (e) {
      const msg = mensagemDe(e);
      if (msg.includes("não respondeu a tempo")) {
        return texto(
          "A operação foi enviada, mas a aba da Web está em segundo plano e ainda não confirmou. Ela será aplicada quando a aba voltar: NÃO reenvie (duplicaria). Confira depois com canvas_ler.",
        );
      }
      return falha(msg);
    }
  }

  const LARGURAS = { celular: 393, tablet: 768, desktop: 1280 } as const;
  const ALTURAS = { celular: 852, tablet: 1024, desktop: 800 } as const;
  const largura = z
    .union([z.enum(["celular", "tablet", "desktop"]), z.number().min(120).max(4000)])
    .describe('"celular" (iPhone, 393×852), "tablet" (768), "desktop" (web, 1280×800) ou a largura em px.');
  const medida = (l: unknown) => (typeof l === "number" ? l : LARGURAS[(l as keyof typeof LARGURAS) ?? "celular"]);
  const alturaPadrao = (l: unknown) => (typeof l === "number" ? 800 : ALTURAS[(l as keyof typeof ALTURAS) ?? "celular"]);

  registrar(
    "tela_criar",
    {
      title: "Criar uma tela de HTML livre",
      description:
        "Põe uma tela nova no canvas: uma prancheta com nome que mostra o seu HTML num iframe isolado. Mande um documento HTML completo, com o CSS em <style>, sem recursos externos. Serve a um rascunho rápido; para telas com as peças do produto, use tela_montar. Sem x/y, ela vai à direita das outras. Devolve o id.",
      inputSchema: {
        nome: z.string().min(1).max(80).describe("O nome da tela, mostrado acima dela."),
        html: z.string().min(1).describe("O HTML completo da tela."),
        largura: largura.optional(),
        altura: z.number().min(80).max(8000).optional().describe("Altura em px. Padrão pela largura."),
        x: z.number().optional(),
        y: z.number().optional(),
      },
    },
    async ({ nome, html, largura: l, altura, x, y }) =>
      operar({ tipo: "tela_criar", nome, html, w: medida(l), h: altura ?? alturaPadrao(l), x, y }),
  );

  registrar(
    "tela_mudar",
    {
      title: "Mudar uma tela de HTML livre",
      description: "Troca o HTML (inteiro), o nome ou o tamanho de uma tela criada com tela_criar.",
      inputSchema: {
        id: z.string().describe('O id da tela ("shape:...").'),
        html: z.string().min(1).optional(),
        nome: z.string().min(1).max(80).optional(),
        largura: largura.optional(),
        altura: z.number().min(80).max(8000).optional(),
      },
    },
    async ({ id, html, nome, largura: l, altura }) =>
      operar({ tipo: "tela_mudar", id, html, nome, w: l === undefined ? undefined : medida(l), h: altura }),
  );

  registrar(
    "tela_ler",
    {
      title: "Ler uma tela de HTML livre",
      description: "Devolve o nome, o tamanho e o HTML atual de uma tela criada com tela_criar.",
      inputSchema: { id: z.string() },
    },
    async ({ id }) => operar({ tipo: "tela_ler", id }),
  );

  registrar(
    "canvas_ler",
    {
      title: "Ler o canvas",
      description:
        'Devolve as formas da página atual, de forma simples (id, tipo, x, y, w, h, nome ou texto, cor, pai; nas instâncias, componente e dados; numa tela com lateral, a tela traz lateral (a largura da coluna) e cada filho traz coluna, "lateral" ou "principal"), e a seleção da pessoa. O HTML das telas não vem aqui: use tela_ler.',
      inputSchema: { ids: z.array(z.string()).optional().describe("Só estas formas.") },
    },
    async ({ ids }) => operar({ tipo: "ler", ids }),
  );

  const forma = z.object({
    tipo: z.enum(["geo", "text", "note", "frame"]).describe("geo = retângulo/elipse; text; note = post-it; frame = moldura."),
    x: z.number(),
    y: z.number(),
    w: z.number().optional(),
    h: z.number().optional(),
    texto: z.string().optional().describe("O texto (ou o nome, num frame)."),
    cor: z
      .enum(["black", "grey", "light-violet", "violet", "blue", "light-blue", "yellow", "orange", "green", "light-green", "light-red", "red"])
      .optional(),
    geo: z.enum(["rectangle", "ellipse", "diamond", "triangle", "star", "cloud"]).optional(),
  });

  registrar(
    "canvas_criar",
    {
      title: "Criar formas",
      description: "Cria formas nativas do tldraw (notas, textos, retângulos, molduras) para anotar e rascunhar. Devolve os ids.",
      inputSchema: { formas: z.array(forma).min(1).max(200) },
    },
    async ({ formas }) => operar({ tipo: "criar", formas }),
  );

  registrar(
    "canvas_mudar",
    {
      title: "Mudar formas",
      description: "Muda posição, tamanho, texto ou cor de formas existentes (telas também: x, y). Para os dados de uma instância, use instancia_mudar.",
      inputSchema: {
        mudancas: z
          .array(
            z.object({
              id: z.string(),
              x: z.number().optional(),
              y: z.number().optional(),
              w: z.number().optional(),
              h: z.number().optional(),
              texto: z.string().optional(),
              cor: forma.shape.cor,
            }),
          )
          .min(1),
      },
    },
    async ({ mudancas }) => operar({ tipo: "mudar", mudancas }),
  );

  registrar(
    "canvas_apagar",
    {
      title: "Apagar formas",
      description: "Apaga formas, instâncias e telas pelo id.",
      inputSchema: { ids: z.array(z.string()).min(1) },
    },
    async ({ ids }) => operar({ tipo: "apagar", ids }),
  );

  registrar(
    "canvas_focar",
    {
      title: "Enquadrar",
      description: "Move a câmera para mostrar estas formas (ou tudo, sem ids).",
      inputSchema: { ids: z.array(z.string()).optional() },
    },
    async ({ ids }) => operar({ tipo: "focar", ids }),
  );

  registrar(
    "canvas_agrupar",
    {
      title: "Agrupar formas",
      description:
        "Junta formas (instâncias, notas, telas) num grupo do tldraw, que anda junto e abre com duplo clique, como no Figma. Use para uma peça composta (um cartão com foto, preço e ações). Devolve o id do grupo.",
      inputSchema: { ids: z.array(z.string()).min(2).describe("Os ids das formas, pelo menos duas.") },
    },
    async ({ ids }) => operar({ tipo: "agrupar", ids }),
  );

  // ---------- componentes ----------

  const semComponentes = () => falha("os componentes não estão ligados neste servidor");
  const idComponente = z
    .string()
    .regex(ID_COMPONENTE, 'use "<produto>/<peça>" em kebab-case, ex.: "loja/cartao-produto"')
    .describe('O id do componente, "<produto>/<peça>" (ex.: "loja/cartao-produto"). Veja componente_listar.');

  registrar(
    "componente_definir",
    {
      title: "Definir um componente",
      description: `Cria ou troca a definição de um componente; todas as instâncias dele no canvas se redesenham. Mande UM dos dois:
- pasta: o caminho absoluto da pasta de um wrapper escrito pela skill design (o jeito normal para uma peça que existe no produto). A pasta tem componente.json e, se o JSON não traz o campo, peca.html (html), peca.css (css), desktop.css (variantes.desktop.css) e sprite.svg (sprite).
- componente: o JSON da definição, para um rascunho que você acabou de escrever (estado "rascunho", sem fonte).
O formato: { id: "<produto>/<peça>" em kebab-case, nome, descricao, estado: "rascunho" | "real", html (o markup, com os ancestrais de que o CSS precisa), css (vai num shadow DOM: classes próprias; :root vira :host), w e h (o tamanho natural no celular, 393 de largura), variantes?: { desktop?: { css, html?, w, h } } (a web, 1280), slots: [{ chave, seletor, como }] com como = texto | html | lista | attr:<atributo> | estilo:<propriedade>, dados: { chave: texto ou lista } (o padrão), fonte?: { repo, arquivo, simbolo?, commit, receita: "executar" | "copiar" } (obrigatória no estado "real"), fontes?: [URLs de CSS], sprite?: SVG com <symbol> }. Não mande versao: o MCP sobe a cada definição. Devolve { id, versao, estado }. Não precisa da Web aberta.`,
      inputSchema: {
        pasta: z.string().min(1).optional().describe("O caminho absoluto da pasta do wrapper."),
        componente: z
          .record(z.string(), z.unknown())
          .optional()
          .describe('O JSON da definição (um rascunho, com estado "rascunho").'),
      },
    },
    async ({ pasta, componente }) => {
      if (!ctx.componentes) return semComponentes();
      if ((pasta === undefined) === (componente === undefined)) {
        return falha("mande pasta (o caminho absoluto do wrapper) ou componente (o JSON do rascunho), um dos dois");
      }
      try {
        const c = pasta !== undefined ? ctx.componentes.definirDaPasta(pasta) : ctx.componentes.definir(componente);
        return texto(JSON.stringify({ id: c.id, versao: c.versao, estado: c.estado }));
      } catch (e) {
        return falha(`componente recusado: ${mensagemDe(e)}`);
      }
    },
  );

  registrar(
    "componente_listar",
    {
      title: "Listar os componentes",
      description:
        'Lista os componentes definidos (de um produto, ou todos): id, nome, descricao, estado ("real" ou "rascunho"), versao, w×h no celular, chaves (o que uma instância aceita em dados) e os dados padrão. Chame antes de tela_montar. Não precisa da Web aberta.',
      inputSchema: {
        produto: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "kebab-case, ex.: via").optional().describe('Só os de um produto (ex.: "loja").'),
      },
    },
    async ({ produto }) => {
      if (!ctx.componentes) return semComponentes();
      const componentes = ctx.componentes.listar(produto);
      if (componentes.length === 0) {
        return texto(
          JSON.stringify({
            componentes,
            dica: "nenhum componente definido ainda: use a skill design para escrever o wrapper de uma peça do produto e chame componente_definir({pasta}), ou escreva um rascunho e chame componente_definir({componente})",
          }),
        );
      }
      return texto(JSON.stringify({ componentes }));
    },
  );

  registrar(
    "componente_ler",
    {
      title: "Ler um componente",
      description: "Devolve a definição inteira de um componente (html, css, variantes, slots, dados, fonte, versao). Não precisa da Web aberta.",
      inputSchema: { id: idComponente },
    },
    async ({ id }) => {
      if (!ctx.componentes) return semComponentes();
      const c = ctx.componentes.ler(id);
      return c ? texto(JSON.stringify(c)) : falha(ctx.componentes.conferir(id, undefined) ?? `não existe o componente "${id}"`);
    },
  );

  // ---------- telas montadas e instâncias ----------

  const dados = z
    .record(z.string(), z.union([z.string(), z.array(z.string())]))
    .describe("Os valores dos slots, por chave (veja as chaves em componente_listar): texto, ou lista de textos nas chaves do tipo lista. Mande só o que muda em relação ao padrão.");
  const peca = z.object({
    componente: idComponente,
    dados: dados.optional(),
  });

  /** Confere no servidor, sem ir à página, cada componente e as chaves dos dados. */
  function conferirPecas(pecas: { componente: string; dados?: Record<string, unknown> }[], onde = ""): string | null {
    if (!ctx.componentes) return "os componentes não estão ligados neste servidor";
    for (const [i, p] of pecas.entries()) {
      const problema = ctx.componentes.conferir(p.componente, p.dados);
      if (problema) return onde + (pecas.length > 1 ? `peça ${i + 1}: ` : "") + problema;
    }
    return null;
  }

  const LATERAL_MIN = 80;
  /** A coluna lateral cabe entre 80 e a largura da tela − 200 (sobra uma área principal de pelo menos 200). */
  function conferirLateral(larguraLateral: number, larguraTela: number): string | null {
    const max = larguraTela - 200;
    if (max < LATERAL_MIN) return `a tela de ${larguraTela} px é estreita demais para uma coluna lateral (precisa de pelo menos ${LATERAL_MIN + 200})`;
    if (larguraLateral < LATERAL_MIN || larguraLateral > max) {
      return `lateral.largura deve ficar entre ${LATERAL_MIN} e ${max} (a largura da tela, ${larguraTela}, − 200); veio ${larguraLateral}`;
    }
    return null;
  }

  registrar(
    "tela_montar",
    {
      title: "Montar uma tela com instâncias",
      description:
        'O jeito preferido de desenhar uma tela: cria um frame com nome e tamanho e empilha dentro dele, de cima para baixo e sem espaço, uma instância de cada componente, cada uma com os seus dados. Faça sempre a versão web (largura "desktop") e a iPhone ("celular"). Para um layout de web com barra à esquerda, mande lateral: { largura, pecas }: essas peças ficam numa coluna à esquerda (x = 0, largura `largura`), empilhadas do topo, e as `pecas` normais ficam à direita (x = largura, o resto da tela). A variante desktop de todas as instâncias, inclusive as da lateral, vem da largura da tela (1024 ou mais). Sem x/y, ela vai à direita do que existe. Recusa componente ou chave de dados que não existe (veja componente_listar), também na lateral. Devolve { id, pecas: [ids das instâncias] } (as da lateral vêm em `lateral`).',
      inputSchema: {
        nome: z.string().min(1).max(80).describe("O nome da tela, mostrado acima dela."),
        largura: largura.optional(),
        altura: z.number().min(80).max(8000).optional().describe("Altura em px. Padrão pela largura."),
        x: z.number().optional(),
        y: z.number().optional(),
        pecas: z.array(peca).min(1).max(100).describe("As instâncias, na ordem de cima para baixo (na área à direita, se houver lateral)."),
        lateral: z
          .object({
            largura: z.number().describe("A largura da coluna lateral em px: de 80 até a largura da tela − 200."),
            pecas: z.array(peca).min(1).max(100).describe("As instâncias da coluna lateral, de cima para baixo."),
          })
          .optional()
          .describe("Uma coluna à esquerda (a barra lateral de um layout de web)."),
      },
    },
    async ({ nome, largura: l, altura, x, y, pecas, lateral }) => {
      const w = medida(l);
      const problema =
        (lateral ? conferirLateral(lateral.largura, w) : null) ??
        conferirPecas(pecas) ??
        (lateral ? conferirPecas(lateral.pecas, "lateral, ") : null);
      if (problema) return falha(problema);
      return operar({ tipo: "tela_montar", nome, w, h: altura ?? alturaPadrao(l), x, y, pecas, lateral });
    },
  );

  registrar(
    "instancia_inserir",
    {
      title: "Inserir uma instância numa tela",
      description:
        'Põe uma instância de um componente dentro de uma tela montada (tela_montar), na posição `indice` da pilha (0 = no topo; sem indice, no fim). Numa tela com lateral, coluna escolhe a pilha: "lateral" (a coluna à esquerda) ou "principal" (a área à direita, o padrão). Devolve o id da instância.',
      inputSchema: {
        tela: z.string().min(1).describe('O id da tela ("shape:...").'),
        componente: idComponente,
        dados: dados.optional(),
        indice: z.number().int().min(0).optional().describe("A posição na pilha, contando do topo a partir de 0."),
        coluna: z
          .enum(["lateral", "principal"])
          .optional()
          .describe('Numa tela com lateral: "lateral" ou "principal" (padrão). Uma tela sem lateral recusa "lateral".'),
      },
    },
    async ({ tela, componente, dados: d, indice, coluna }) => {
      const problema = conferirPecas([{ componente, dados: d }]);
      if (problema) return falha(problema);
      return operar({ tipo: "instancia_inserir", tela, componente, dados: d, indice, coluna });
    },
  );

  registrar(
    "instancia_mudar",
    {
      title: "Mudar os dados de uma instância",
      description:
        "Muda os dados de uma instância que já está no canvas: o que você manda se junta aos dados atuais (mande só o que muda), e ela se redesenha. Para mudar todas as instâncias de um componente, mude a definição com componente_definir.",
      inputSchema: {
        id: z.string().min(1).describe('O id da instância ("shape:...").'),
        dados,
      },
    },
    async ({ id, dados: d }) => {
      // Se o espelho do canvas conhece a instância e o componente está definido, as chaves são conferidas aqui.
      const registro = ctx.canvas?.ler()[id] as { props?: { componente?: unknown } } | undefined;
      const componente = registro?.props?.componente;
      if (typeof componente === "string" && ctx.componentes?.ler(componente)) {
        const problema = ctx.componentes.conferir(componente, d);
        if (problema) return falha(problema);
      }
      return operar({ tipo: "instancia_mudar", id, dados: d });
    },
  );

  return mcp;
}
