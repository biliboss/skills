/**
 * As operações do canvas: o servidor não desenha; manda a operação à página
 * aberta (SSE `canvas`), a página aplica com o editor do tldraw e responde em
 * POST /api/canvas/resposta. Cada operação espera a resposta com tempo limite.
 */
import type { Chat } from "./chat.ts";

export const OPERACAO_MS = 15_000;

type Pendente = { resolver: (r: unknown) => void; falhar: (e: Error) => void; timer: ReturnType<typeof setTimeout> };

export class Operacoes {
  private readonly pendentes = new Map<string, Pendente>();
  constructor(private readonly chat: Chat, private readonly limiteMs = OPERACAO_MS) {}

  executar(op: Record<string, unknown>): Promise<unknown> {
    const pedido = crypto.randomUUID();
    return new Promise((resolver, falhar) => {
      if (this.chat.ouvintes === 0) {
        falhar(new Error("a Web não está aberta: chame web_abrir e espere a página carregar"));
        return;
      }
      const timer = setTimeout(() => {
        this.pendentes.delete(pedido);
        falhar(new Error("a página não respondeu a tempo (o canvas carregou?)"));
      }, this.limiteMs);
      this.pendentes.set(pedido, { resolver, falhar, timer });
      if (!this.chat.transmitirParaUm({ tipo: "canvas", dados: { pedido, op } })) {
        clearTimeout(timer);
        this.pendentes.delete(pedido);
        falhar(new Error("nenhuma página para receber a operação"));
      }
    });
  }

  /** A resposta da página. Devolve false se o pedido não existe (já venceu). */
  responder(pedido: string, ok: boolean, resultado: unknown, erro?: string): boolean {
    const p = this.pendentes.get(pedido);
    if (!p) return false;
    clearTimeout(p.timer);
    this.pendentes.delete(pedido);
    if (ok) p.resolver(resultado);
    else p.falhar(new Error(erro || "a página recusou a operação"));
    return true;
  }

  soltar(): void {
    for (const [pedido, p] of this.pendentes) {
      clearTimeout(p.timer);
      p.falhar(new Error("o servidor está encerrando"));
      this.pendentes.delete(pedido);
    }
  }
}
