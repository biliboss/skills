/**
 * Domain contract of the memory module.
 *
 * Aggregate root: AgentMemory, the reduced memory of one agent (a folder) or one session.
 * Everything outside it (transcript reading, the model, the disk) is a port.
 * The model only judges: it proposes facts; the aggregate decides what stays.
 */

export type FactType = "decisao" | "preferencia" | "correcao" | "fato" | "pendencia";

/** Fact types that are only valid when their source is an owner message. */
export const OWNER_ONLY_TYPES: readonly FactType[] = ["decisao", "preferencia", "correcao", "pendencia"];

/** `<first 8 chars of the session id>:<message uuid>`. */
export type SourceRef = string;

export type Role = "user" | "assistant";

/** One message of the transcript, already masked for secrets and personal data. */
export interface Message {
  readonly source: SourceRef;
  readonly ts: string;
  readonly role: Role;
  /** True only for words the owner wrote: no hook notice, agent relay or system text. */
  readonly fromOwner: boolean;
  readonly text: string;
}

/** A line of facts.jsonl. */
export interface Fact {
  /** Always the timestamp of `source`. */
  readonly ts: string;
  readonly type: FactType;
  readonly title: string;
  readonly fact: string;
  readonly source: SourceRef;
  readonly supersedes: SourceRef | null;
}

/** How many transcript messages are already reflected in the memory. */
export type Cursor = number;

/** Value object: the masked messages of one or many sessions, in time order. */
export interface Transcript {
  readonly messages: readonly Message[];
  /** Windows after `from`, each closing every `every` owner messages. */
  windows(from: Cursor, every: number): readonly Window[];
  /** The tail that starts at the Nth most recent owner message. */
  last(ownerMessages: number): Transcript;
}

/** Value object: a slice of the transcript. */
export interface Window {
  /** 1-based. */
  readonly index: number;
  /** Where the cursor stands once this window is absorbed. */
  readonly end: Cursor;
  /** Messages new in this window. */
  readonly messages: readonly Message[];
  /** The transcript up to the end of this window, for lookups. */
  readonly history: Transcript;
}

export type ViolationCode =
  | "invalid-shape"
  | "unknown-source"
  | "ts-mismatch"
  | "needs-owner-source"
  | "unknown-supersedes"
  | "aging-reference"
  | "redacted-content";

export interface Violation {
  readonly code: ViolationCode;
  readonly title: string;
  readonly detail: string;
}

export interface WindowReport {
  readonly window: number;
  readonly facts: number;
  readonly violations: readonly Violation[];
  readonly seconds: number;
}

/**
 * Value object: the facts the model proposes for one window.
 * It knows its window, so it checks itself against that window's history:
 * - every fact points to a message that exists, with the `ts` of that message;
 * - owner-only types come from an owner message;
 * - `supersedes` is null or points to a message that exists;
 * - no fact carries a hash, PR number, version or masked value.
 */
export interface Proposal {
  readonly window: Window;
  readonly facts: readonly Fact[];
  readonly violations: readonly Violation[];
}

/**
 * Aggregate root. One instance per scope; the only writer of its facts.
 * The cursor only moves forward, so a new run reads only what is new.
 */
export interface AgentMemory {
  /** Agent folder name, or the short id when a single session was asked. */
  readonly scope: string;
  readonly cursor: Cursor;
  readonly facts: readonly Fact[];

  /**
   * Replaces the facts with a valid proposal, without the superseded ones,
   * and moves the cursor to the end of its window.
   * Throws when the proposal has violations or its window is not the next one.
   */
  absorb(proposal: Proposal): AgentMemory;
}

/** Port: reads a session id, a session .jsonl, or an agent folder (all its sessions). */
export interface TranscriptReader {
  read(input: string): Promise<Transcript>;
}

/** What the extractor sees for one window. */
export interface ExtractionRequest {
  readonly window: Window;
  readonly current: readonly Fact[];
  /** Rules in force, which outrank any older fact. */
  readonly rules: string | null;
  /** The refused proposal on a retry, so the model repairs instead of starting over. */
  readonly rejected: Proposal | null;
}

/** Port: the model that judges a window. Implemented over the Devin SDK. */
export interface FactExtractor {
  extract(request: ExtractionRequest): Promise<Proposal>;
}

/** Port: durable state of the aggregate. */
export interface MemoryStore {
  load(scope: string): Promise<AgentMemory>;
  save(memory: AgentMemory): Promise<void>;
}
