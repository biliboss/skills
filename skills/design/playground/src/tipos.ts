/** Os tipos do CONTRATO.md, compartilhados entre o chat, o HTTP e as ferramentas. */

export type Autor = "pessoa" | "agente";

export type Mensagem = {
  id: string;
  autor: Autor;
  texto: string;
  /** ISO 8601 */
  em: string;
  /** ids das formas do tldraw selecionadas no envio */
  selecao?: string[];
  /** "atividade": uma linha de atividade do agente (chat_atividade), não uma resposta */
  tipo?: "atividade";
};

export type Motor = "ouvindo" | "ocupado" | "sem-agente";

/** Os eventos que vão pelo SSE /api/eventos. */
export type Evento =
  | { tipo: "mensagem"; dados: Mensagem }
  | { tipo: "digitando"; dados: { ativo: boolean; texto?: string } }
  | { tipo: "motor"; dados: { estado: Motor } }
  | { tipo: "apagada"; dados: { id: string } }
  | { tipo: "canvas"; dados: { pedido: string; op: Record<string, unknown> } }
  | { tipo: "componente"; dados: { id: string; versao: number } };

export type Assinante = (evento: Evento) => void;

/** Log no stderr: o stdout é só do MCP. */
export function log(...partes: unknown[]): void {
  console.error("[design-playground]", ...partes);
}
