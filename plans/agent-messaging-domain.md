# Caixa de entrada dos agentes: contrato de domínio

**Repositório:** `biliboss/skills` · **Entrega:** `libs/messaging/interface.ts` · **Responsável:** CTO

## Para executivos

**O que é.** Uma caixa de entrada interna para os agentes. Eles conversam de forma assíncrona, retomam conversas e sabem o que ainda não leram, sem depender de e-mail.

**O que será entregue.** Um único arquivo TypeScript que descreve todo o domínio. Não há banco, servidor, tela nem implementação nesta etapa.

**Como funciona para os agentes.**
- Um agente abre uma conversa com pelo menos outro agente.
- Qualquer participante pode trazer mais agentes, e cada um pode sair quando quiser.
- Quem entra recebe todo o histórico como não lido e zera a fila com uma única ação.
- Quem sai deixa de ver a conversa até ser adicionado de novo.

**Decisões suas, já incorporadas.**

| Tema | Decisão |
|---|---|
| Participantes | Ciclo completo: entrar e sair |
| Quem entra | Vê tudo, e tudo chega como não lido |
| Leitura | Marcada como "lido até aqui" |
| Criação | A conversa nasce com o comando `start` |

**Um ajuste no seu rascunho.** Consultar as mensagens agora exige dizer quem está lendo. Sem isso, a regra de que quem saiu não vê a conversa não teria como valer.

**Pronto quando.** O arquivo compila e uma ferramenta extrai dele o aggregate, os comandos, os eventos e as consultas, sem executar código. A decisão que falta é aprovar este documento.

---

## Decisões técnicas

Origem: **CEO** foi escolhida por você; **CTO** foi assumida por mim.

### 1. Fronteira do domínio (CEO)
**Decisão:** mensagens entre agentes, com vocabulário próprio.
- **Modelar e-mail (remetente, CC, assunto):** traz conceitos que agentes não usam.
- **Framework genérico de mensageria:** vetado no pedido; não há segundo caso de uso.

### 2. Um único arquivo (CEO)
**Decisão:** todo o domínio em `interface.ts`.
- **Um arquivo por conceito:** fragmenta a leitura e a extração estática.
- **Schema JSON ou Protobuf:** exige gerador e não expressa o aggregate com comandos.

### 3. Aggregate principal: `Conversation` (CEO)
**Decisão:** a conversa é a fronteira de consistência.
- **`Mailbox` por agente:** uma mensagem alteraria várias caixas e perderia a consistência.
- **`Message` como aggregate:** as regras de participação ficariam sem dono.

### 4. Criação (CEO)
**Decisão:** zero eventos geram uma conversa em branco; `start` só vale nesse estado.
- **Função `start` fora do aggregate:** cria um segundo conceito e foge do rascunho.
- **`decide(state, command)`:** comandos deixam de ser métodos, e a extração fica indireta.

### 5. Formato de retorno dos comandos (CTO)
**Decisão:** tuplas explícitas, como `[MessageSent]`.
- **`ConversationEvent[]` genérico:** esconde quais eventos cada comando produz.
- **Evento único sem array:** não expressa o caso sem efeito.

### 6. Mudança de participantes (CEO)
**Decisão:** `addParticipant` e `leave`, com eventos próprios.
- **Lista fixa no início:** obriga a abrir outra conversa e perde o histórico.
- **Só adicionar:** um agente ficaria preso para sempre a conversas encerradas para ele.

### 7. Quem pode adicionar (CTO)
**Decisão:** qualquer participante atual.
- **Só quem iniciou:** se essa pessoa sair, a conversa não recebe mais ninguém.
- **Papel de administrador:** cria papéis sem nenhuma regra que os exija.

### 8. Quem pode remover (CTO)
**Decisão:** cada agente só remove a si mesmo.
- **Qualquer participante remove outro:** abre disputa entre agentes sem regra para resolver.
- **Quem iniciou remove:** reintroduz autoridade sem invariante que a justifique.

### 9. Conversa sem participantes (CTO)
**Decisão:** fica congelada, porque todo comando exige um ator participante.
- **Evento `ConversationClosed`:** adiciona estado para um efeito que já existe.
- **Apagar a conversa:** contraria eventos como fatos imutáveis.

### 10. Mínimo para começar (CTO)
**Decisão:** dois agentes distintos, incluindo o ator.
- **Permitir um só:** vira bloco de notas, fora do objetivo.
- **Ator implícito:** esconde parte da lista e obriga a deduzi-la no replay.

### 11. Histórico de quem entra (CEO; "tudo" interpretado como histórico inteiro e não lido)
**Decisão:** vê tudo, e tudo conta como não lido.
- **Histórico visível, não lidas só as novas:** o agente pode perder contexto que precisa processar.
- **Só a partir da entrada:** ele chega sem contexto e alguém precisa resumir.

### 12. Acesso de quem saiu (CTO)
**Decisão:** perde a conversa em todas as consultas até voltar.
- **Manter acesso permanente:** sair deixaria de ter efeito prático.
- **Manter o que viu até sair:** exige recorte por período, sem necessidade concreta.

### 13. Quem volta à conversa (CTO)
**Decisão:** mantém a marca de leitura anterior.
- **Zerar a marca:** obriga a reprocessar o que já leu.
- **Marcar tudo como lido ao voltar:** esconde o que chegou durante a ausência.

### 14. Granularidade da leitura (CEO)
**Decisão:** `upTo`, "lido até X".
- **Mensagem a mensagem:** 200 mensagens antigas exigiriam 200 comandos.
- **Lista de mensagens:** aumenta eventos e projeção; leitura fora de ordem não é requisito.

### 15. Mensagem própria (CTO)
**Decisão:** nunca conta como não lida.
- **Exigir marcação do remetente:** cria trabalho sem significado.
- **Evento automático `MessageRead` no envio:** dobra os eventos e afeta a regra de um evento por comando.

### 16. Identidade do autor (CTO)
**Decisão:** `actor` explícito em cada comando, informado por quem chama.
- **Contexto de autenticação:** autenticação está fora do escopo.
- **Assinatura criptográfica:** é infraestrutura de autenticação.

### 17. Identificadores e horário (CTO)
**Decisão:** vêm prontos no comando.
- **Gerados pelo aggregate:** tornam o replay e o aggregate dependentes de ambiente.
- **Porta `Clock` ou `IdGenerator`:** é a abstração prematura vetada no pedido.

### 18. Ordem dos eventos (CTO)
**Decisão:** `sequence` por conversa, começando em 1 e sem lacunas.
- **Ordenar por horário:** relógios colidem e divergem entre agentes.
- **Sequência global:** impõe coordenação entre conversas independentes.

### 19. Reconstrução do estado (CTO)
**Decisão:** `replay(events)` retorna nova instância.
- **`apply(event)`:** cada consumidor reescreve o mesmo laço.
- **Fora do contrato:** cada implementação resolveria de um jeito.

### 20. Comando recusado (CTO)
**Decisão:** retorno tipado `Rejection<...>`, nunca armazenado.
- **Exceções:** os motivos de falha somem da assinatura.
- **Evento `CommandRejected`:** tentativa recusada não é fato do domínio.

### 21. Comando sem efeito (CTO)
**Decisão:** retorna `[]`.
- **Rejeitar:** novas tentativas após falha de rede virariam erro.
- **Emitir evento repetido:** polui o histórico com fatos falsos.

### 22. Descoberta estática (CTO)
**Decisão:** tags JSDoc (`@aggregate`, `@command`, `@event`) e tipos explícitos.
- **Só convenção de nomes:** frágil, e `Message` não revela sua categoria.
- **Decorators:** exigem classes e código de execução.

### 23. Tipos de identificadores (CTO)
**Decisão:** strings com marca de tipo.
- **`string` simples:** permite trocar `AgentId` por `MessageId` sem erro.
- **Classes:** adicionam código de execução ao contrato.

### 24. Consulta de mensagens (CTO)
**Decisão:** `messages(id, agent)`, com vazio para quem não participa.
- **`messages(id)` do rascunho:** impede aplicar a regra de visibilidade.
- **Autorização fora do contrato:** a regra de domínio ficaria invisível.

### 25. Retorno de `unread` (CTO)
**Decisão:** mensagens completas de todas as conversas atuais do agente.
- **Apenas contagem:** o agente precisaria de mais consultas para agir.
- **Agrupado por conversa:** `Message` já traz a conversa, então seria duplicação.

### 26. Conteúdo da mensagem (CTO)
**Decisão:** `body: string`.
- **Anexos e tipos de conteúdo:** nenhum requisito pede.
- **Payload genérico:** o contrato deixaria de descrever o que é uma mensagem.

### 27. Entrega (CTO)
**Decisão:** Bili Skills adiciona só este arquivo na `main`, a partir de base atualizada.
- **Commit direto no checkout local:** ele está 28 commits atrás e tem alterações de outras sessões.
- **Pacote com `package.json` e `tsconfig`:** é infraestrutura sem necessidade nesta etapa.

---

## Contrato a entregar

```typescript
/** @valueObject */ export type ConversationId = string & { readonly __brand: 'ConversationId' };
/** @valueObject */ export type AgentId = string & { readonly __brand: 'AgentId' };
/** @valueObject */ export type MessageId = string & { readonly __brand: 'MessageId' };
/** @valueObject ISO-8601 UTC. */ export type Timestamp = string & { readonly __brand: 'Timestamp' };

/** @valueObject */
export interface Participant { readonly agent: AgentId; }

/** @valueObject */
export interface Message {
  readonly id: MessageId;
  readonly conversation: ConversationId;
  readonly sender: AgentId;
  readonly body: string;
  readonly sentAt: Timestamp;
}

/** @command */
export interface StartConversation {
  readonly conversation: ConversationId;
  readonly actor: AgentId;
  readonly participants: readonly Participant[];
  readonly at: Timestamp;
}
/** @command */
export interface SendMessage {
  readonly conversation: ConversationId;
  readonly actor: AgentId;
  readonly message: MessageId;
  readonly body: string;
  readonly at: Timestamp;
}
/** @command Marks every message up to and including `upTo` as read for `actor`. */
export interface MarkMessageRead {
  readonly conversation: ConversationId;
  readonly actor: AgentId;
  readonly upTo: MessageId;
  readonly at: Timestamp;
}
/** @command */
export interface AddParticipant {
  readonly conversation: ConversationId;
  readonly actor: AgentId;
  readonly participant: Participant;
  readonly at: Timestamp;
}
/** @command */
export interface LeaveConversation {
  readonly conversation: ConversationId;
  readonly actor: AgentId;
  readonly at: Timestamp;
}

/** Fields shared by every fact. `sequence` starts at 1 and has no gaps. */
export interface EventMetadata {
  readonly conversation: ConversationId;
  readonly sequence: number;
  readonly occurredAt: Timestamp;
}
/** @event */
export interface ConversationStarted extends EventMetadata {
  readonly type: 'ConversationStarted';
  readonly startedBy: AgentId;
  readonly participants: readonly Participant[];
}
/** @event */
export interface MessageSent extends EventMetadata {
  readonly type: 'MessageSent';
  readonly message: Message;
}
/** @event */
export interface MessageRead extends EventMetadata {
  readonly type: 'MessageRead';
  readonly reader: AgentId;
  readonly upTo: MessageId;
}
/** @event */
export interface ParticipantAdded extends EventMetadata {
  readonly type: 'ParticipantAdded';
  readonly addedBy: AgentId;
  readonly participant: Participant;
}
/** @event */
export interface ParticipantLeft extends EventMetadata {
  readonly type: 'ParticipantLeft';
  readonly agent: AgentId;
}
export type ConversationEvent =
  | ConversationStarted | MessageSent | MessageRead | ParticipantAdded | ParticipantLeft;

/** @rejection */
export type RejectionReason =
  | 'AlreadyStarted' | 'InvalidParticipants' | 'NotStarted'
  | 'NotParticipant' | 'DuplicateMessage' | 'UnknownMessage';
/** @rejection */
export interface Rejection<R extends RejectionReason> { readonly rejected: R; }

/** @aggregate */
export interface Conversation {
  /** @command */ start(input: StartConversation):
    [ConversationStarted] | Rejection<'AlreadyStarted' | 'InvalidParticipants'>;
  /** @command */ send(input: SendMessage):
    [MessageSent] | Rejection<'NotStarted' | 'NotParticipant' | 'DuplicateMessage'>;
  /** @command Returns [] when `upTo` is already covered. */ markRead(input: MarkMessageRead):
    [MessageRead] | [] | Rejection<'NotStarted' | 'NotParticipant' | 'UnknownMessage'>;
  /** @command Returns [] when already a participant. */ addParticipant(input: AddParticipant):
    [ParticipantAdded] | [] | Rejection<'NotStarted' | 'NotParticipant'>;
  /** @command Returns [] when not a participant. */ leave(input: LeaveConversation):
    [ParticipantLeft] | [] | Rejection<'NotStarted'>;
  /** @replay Applies ordered events and returns a new instance. */
  replay(events: readonly ConversationEvent[]): Conversation;
}

/** @readModel */
export interface ConversationSummary {
  readonly conversation: ConversationId;
  readonly participants: readonly Participant[];
  readonly unreadCount: number;
  readonly lastMessageAt: Timestamp | null;
}

/** @readPort Queries never mutate aggregate state. Messages are returned in sequence order. */
export interface ConversationReader {
  /** @query Conversations where `agent` is a current participant. */
  list(agent: AgentId): Promise<ConversationSummary[]>;
  /** @query Empty when `agent` is not a current participant. */
  messages(id: ConversationId, agent: AgentId): Promise<Message[]>;
  /** @query Unread messages across the agent's current conversations. */
  unread(agent: AgentId): Promise<Message[]>;
}
```

## Verificação

Fora do repositório, no scratchpad, contra o arquivo entregue:

1. `tsc --noEmit --strict` compila sem erros.
2. Um script descartável de AST extrai o aggregate, os cinco comandos com entradas e eventos, os cinco eventos, o replay e as três consultas, só por tags e tipos.
3. O arquivo não tem imports nem instruções de execução, e é o único do commit.
