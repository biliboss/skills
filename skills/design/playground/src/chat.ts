/**
 * O estado do chat: as mensagens, quais já foram entregues ao agente, o
 * "digitando…", o motor (as sessões MCP e qual delas é o motor), os assinantes
 * do SSE e a espera longa do chat_aguardar. Persiste em
 * <dadosDir>/conversa.jsonl e recarrega no início.
 *
 * Um motor por vez, entre transportes: cada sessão MCP (stdio, HTTP ou em
 * memória) entra com `entrar`; a primeira que chama uma ferramenta (`assumir`)
 * vira o motor, e as outras são recusadas enquanto ela estiver conectada. Uma
 * sessão com `ociosoMs` (a de HTTP) solta a vez quando passa esse tempo sem
 * chamar nada e sem ferramenta em curso (um chat_aguardar pendente conta).
 *
 * Formato do conversa.jsonl, uma linha por registro:
 *   - uma Mensagem (tem `id` e `autor`);
 *   - `{ "entregue": ["<id>", ...] }`: mensagens da pessoa já entregues ao agente;
 *   - `{ "apagada": "<id>" }`: uma mensagem que o agente apagou.
 */
import { appendFile, mkdir } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { log, type Assinante, type Evento, type Mensagem, type Motor } from "./tipos.ts";

type Espera = {
  resolver: (mensagens: Mensagem[]) => void;
};

type Sessao = {
  id: string;
  rotulo: string;
  /** Sem chamar nada por esse tempo, a sessão fica ociosa e solta o motor. Sem valor: nunca. */
  ociosoMs?: number;
  /** Conta para o estado do motor ("ocupado" em vez de "sem-agente"). */
  ativa: boolean;
  /** Ferramentas em curso agora (um chat_aguardar pendente conta). */
  emCurso: number;
  timer?: ReturnType<typeof setTimeout>;
};

/** O resultado de `assumir`: a vez de ser o motor, ou quem está com ela. */
export type Vez = { ok: true } | { ok: false; dono: string };

export class Chat {
  private readonly mensagens: Mensagem[] = [];
  private readonly entregues = new Set<string>();
  private readonly esperas: Espera[] = [];
  private readonly assinantes = new Set<Assinante>();
  private readonly arquivo: string;
  private gravacao: Promise<void> = Promise.resolve();
  private readonly sessoes = new Map<string, Sessao>();
  private dono: string | null = null;
  private _digitando = false;
  private _atividade: string | undefined;
  private ultimoMotor: Motor = "sem-agente";

  constructor(dadosDir: string) {
    this.arquivo = join(dadosDir, "conversa.jsonl");
    this.recarregar();
    this.gravacao = mkdir(dadosDir, { recursive: true }).then(() => undefined);
  }

  // ---------- leitura ----------

  /**
   * Segue o motor atual: "ouvindo" com um chat_aguardar pendente, "ocupado"
   * sem. Sem motor, "ocupado" se alguma sessão está conectada e ativa (entre o
   * initialize e a primeira ferramenta), "sem-agente" se não.
   */
  get motor(): Motor {
    if (this.dono === null) {
      for (const s of this.sessoes.values()) if (s.ativa) return "ocupado";
      return "sem-agente";
    }
    return this.esperas.length > 0 ? "ouvindo" : "ocupado";
  }

  /** O rótulo da sessão que é o motor agora, ou null. */
  get donoDoMotor(): string | null {
    return this.dono === null ? null : (this.sessoes.get(this.dono)?.rotulo ?? null);
  }

  /** Quantas sessões MCP estão conectadas. */
  get sessoesConectadas(): number {
    return this.sessoes.size;
  }

  get digitando(): boolean {
    return this._digitando;
  }

  todas(): Mensagem[] {
    return [...this.mensagens];
  }

  ultimas(limite: number): Mensagem[] {
    if (limite <= 0) return [];
    return this.mensagens.slice(-limite);
  }

  estado(): { motor: Motor; digitando: boolean; atividade?: string; mensagens: Mensagem[] } {
    return { motor: this.motor, digitando: this.digitando, atividade: this._atividade, mensagens: this.todas() };
  }

  /** Quantas páginas estão com o SSE aberto. */
  get ouvintes(): number {
    return this.assinantes.size;
  }

  /** Manda um evento a todas as páginas abertas (ex.: `componente`). */
  transmitir(evento: Evento): void {
    this.emitir(evento);
  }

  /** Manda um evento só para a página aberta mais recente (operações do canvas). */
  transmitirParaUm(evento: Evento): boolean {
    const ultimo = [...this.assinantes].at(-1);
    if (!ultimo) return false;
    try {
      ultimo(evento);
      return true;
    } catch (erro) {
      log("assinante falhou", erro);
      return false;
    }
  }

  // ---------- assinantes (SSE) ----------

  assinar(assinante: Assinante): () => void {
    this.assinantes.add(assinante);
    return () => {
      this.assinantes.delete(assinante);
    };
  }

  private emitir(evento: Evento): void {
    for (const assinante of this.assinantes) {
      try {
        assinante(evento);
      } catch (erro) {
        log("assinante falhou", erro);
      }
    }
  }

  private conferirMotor(): void {
    const agora = this.motor;
    if (agora !== this.ultimoMotor) {
      this.ultimoMotor = agora;
      this.emitir({ tipo: "motor", dados: { estado: agora } });
    }
  }

  // ---------- sessões e o motor ----------

  /** Uma sessão MCP entrou (depois do `initialize`). Devolve o id dela. */
  entrar(rotulo: string, ociosoMs?: number): string {
    const id = crypto.randomUUID();
    const sessao: Sessao = { id, rotulo, ociosoMs, ativa: true, emCurso: 0 };
    this.sessoes.set(id, sessao);
    this.armarOcio(sessao);
    this.conferirMotor();
    return id;
  }

  /** A sessão fechou (o transporte caiu, DELETE /mcp, stdin fechado). Solta o motor, se era ela. */
  sair(id: string): void {
    const sessao = this.sessoes.get(id);
    if (!sessao) return;
    if (sessao.timer) clearTimeout(sessao.timer);
    this.sessoes.delete(id);
    if (this.dono === id) {
      this.dono = null;
      this.definirDigitando(false);
    }
    if (this.sessoes.size === 0) this.definirDigitando(false);
    this.conferirMotor();
  }

  /**
   * A sessão vai chamar uma ferramenta: vira o motor se a vez está livre (ou
   * já é dela) e marca a ferramenta como em curso, até `terminar`. Se outra
   * sessão é o motor, devolve quem.
   */
  assumir(id: string): Vez {
    const sessao = this.sessoes.get(id);
    if (!sessao) return { ok: false, dono: "esta sessão ainda não terminou o initialize" };
    sessao.ativa = true;
    if (this.dono !== null && this.dono !== id) {
      this.armarOcio(sessao);
      return { ok: false, dono: this.sessoes.get(this.dono)?.rotulo ?? "outra sessão" };
    }
    if (this.dono !== id) log(`o motor agora é a sessão ${sessao.rotulo}`);
    this.dono = id;
    sessao.emCurso++;
    if (sessao.timer) clearTimeout(sessao.timer);
    sessao.timer = undefined;
    this.conferirMotor();
    return { ok: true };
  }

  /** A ferramenta que `assumir` liberou terminou: o tempo ocioso volta a contar. */
  terminar(id: string): void {
    const sessao = this.sessoes.get(id);
    if (!sessao) return;
    sessao.emCurso = Math.max(0, sessao.emCurso - 1);
    if (sessao.emCurso === 0) this.armarOcio(sessao);
  }

  private armarOcio(sessao: Sessao): void {
    if (sessao.ociosoMs === undefined || sessao.emCurso > 0) return;
    if (sessao.timer) clearTimeout(sessao.timer);
    sessao.timer = setTimeout(() => {
      sessao.timer = undefined;
      if (!this.sessoes.has(sessao.id) || sessao.emCurso > 0) return;
      sessao.ativa = false;
      if (this.dono === sessao.id) {
        this.dono = null;
        log(`a sessão ${sessao.rotulo} ficou ociosa e soltou o motor`);
        this.definirDigitando(false);
      }
      this.conferirMotor();
    }, sessao.ociosoMs);
    sessao.timer.unref?.();
  }

  // ---------- escrita ----------

  /** A pessoa escreveu na Web. Acorda quem está em chat_aguardar. */
  receberDaPessoa(texto: string, selecao?: string[]): Mensagem {
    const mensagem = this.nova("pessoa", texto, selecao);
    this.publicar(mensagem);
    this.acordar();
    return mensagem;
  }

  /** O agente respondeu (chat_responder). */
  responderComoAgente(texto: string): Mensagem {
    const mensagem = this.nova("agente", texto);
    this.publicar(mensagem);
    this.definirDigitando(false);
    return mensagem;
  }

  definirDigitando(ativo: boolean, texto?: string): void {
    const novoTexto = ativo ? texto : undefined;
    if (this._digitando === ativo && this._atividade === novoTexto) return;
    this._digitando = ativo;
    this._atividade = novoTexto;
    this.emitir({ tipo: "digitando", dados: novoTexto ? { ativo, texto: novoTexto } : { ativo } });
  }

  /** Uma linha de atividade do agente: fica na conversa e vira o texto do "digitando…". */
  atividade(texto: string): Mensagem {
    const mensagem = this.nova("agente", texto);
    mensagem.tipo = "atividade";
    this.publicar(mensagem);
    this.definirDigitando(true, texto);
    return mensagem;
  }

  /** Apaga uma mensagem (da conversa, do arquivo na recarga e das páginas abertas). */
  apagar(id: string): boolean {
    const i = this.mensagens.findIndex((m) => m.id === id);
    if (i < 0) return false;
    this.mensagens.splice(i, 1);
    this.gravar({ apagada: id });
    this.emitir({ tipo: "apagada", dados: { id } });
    return true;
  }

  // ---------- espera longa ----------

  /** As mensagens da pessoa que o agente ainda não recebeu. */
  naoEntregues(): Mensagem[] {
    return this.mensagens.filter((m) => m.autor === "pessoa" && !this.entregues.has(m.id));
  }

  /**
   * Espera a próxima mensagem da pessoa. Volta na hora se já houver não
   * entregues; senão, quando chegar uma, quando o tempo acabar (`[]`) ou
   * quando o `signal` abortar (`[]`). As devolvidas ficam marcadas como entregues.
   */
  aguardar(timeoutMs: number, signal?: AbortSignal): Promise<Mensagem[]> {
    this.definirDigitando(false);
    const prontas = this.naoEntregues();
    if (prontas.length > 0) {
      this.marcarEntregues(prontas);
      return Promise.resolve(prontas);
    }
    if (signal?.aborted) return Promise.resolve([]);

    return new Promise<Mensagem[]>((resolve) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const sair = () => {
        if (timer) clearTimeout(timer);
        signal?.removeEventListener("abort", aoAbortar);
        const i = this.esperas.indexOf(espera);
        if (i >= 0) this.esperas.splice(i, 1);
        this.conferirMotor();
      };
      const espera: Espera = {
        resolver: (mensagens) => {
          sair();
          resolve(mensagens);
        },
      };
      const aoAbortar = () => espera.resolver([]);
      timer = setTimeout(() => espera.resolver([]), Math.max(0, timeoutMs));
      signal?.addEventListener("abort", aoAbortar, { once: true });
      this.esperas.push(espera);
      this.conferirMotor();
    });
  }

  /** Quantas chamadas de chat_aguardar estão pendentes. */
  get esperando(): number {
    return this.esperas.length;
  }

  /** Solta todas as esperas com `[]` e os relógios das sessões (ao encerrar). */
  soltarEsperas(): void {
    for (const espera of [...this.esperas]) espera.resolver([]);
    for (const s of this.sessoes.values()) {
      if (s.timer) clearTimeout(s.timer);
      s.timer = undefined;
    }
  }

  private acordar(): void {
    const espera = this.esperas[0];
    if (!espera) return;
    const prontas = this.naoEntregues();
    if (prontas.length === 0) return;
    this.marcarEntregues(prontas);
    espera.resolver(prontas);
  }

  private marcarEntregues(mensagens: Mensagem[]): void {
    const ids = mensagens.map((m) => m.id);
    for (const id of ids) this.entregues.add(id);
    this.gravar({ entregue: ids });
  }

  // ---------- persistência ----------

  private nova(autor: Mensagem["autor"], texto: string, selecao?: string[]): Mensagem {
    const mensagem: Mensagem = {
      id: crypto.randomUUID(),
      autor,
      texto,
      em: new Date().toISOString(),
    };
    if (selecao !== undefined) mensagem.selecao = selecao;
    return mensagem;
  }

  private publicar(mensagem: Mensagem): void {
    this.mensagens.push(mensagem);
    this.gravar(mensagem);
    this.emitir({ tipo: "mensagem", dados: mensagem });
  }

  private gravar(registro: unknown): void {
    const linha = JSON.stringify(registro) + "\n";
    this.gravacao = this.gravacao
      .then(() => appendFile(this.arquivo, linha, "utf8"))
      .catch((erro) => log("não consegui gravar", this.arquivo, erro));
  }

  /** Espera as gravações pendentes terminarem. */
  async descarregar(): Promise<void> {
    await this.gravacao;
  }

  private recarregar(): void {
    if (!existsSync(this.arquivo)) return;
    let texto: string;
    try {
      texto = readFileSync(this.arquivo, "utf8");
    } catch (erro) {
      log("não consegui ler", this.arquivo, erro);
      return;
    }
    let ruins = 0;
    for (const linha of texto.split("\n")) {
      if (!linha.trim()) continue;
      try {
        const registro = JSON.parse(linha) as Record<string, unknown>;
        if (typeof registro.apagada === "string") {
          const i = this.mensagens.findIndex((m) => m.id === registro.apagada);
          if (i >= 0) this.mensagens.splice(i, 1);
        } else if (Array.isArray(registro.entregue)) {
          for (const id of registro.entregue) if (typeof id === "string") this.entregues.add(id);
        } else if (
          typeof registro.id === "string" &&
          (registro.autor === "pessoa" || registro.autor === "agente") &&
          typeof registro.texto === "string" &&
          typeof registro.em === "string"
        ) {
          this.mensagens.push(registro as unknown as Mensagem);
        } else {
          ruins++;
        }
      } catch {
        ruins++;
      }
    }
    if (ruins > 0) log(`${ruins} linha(s) ignoradas em ${this.arquivo}`);
    log(`conversa recarregada: ${this.mensagens.length} mensagem(ns)`);
  }
}
