/**
 * A cópia do canvas no servidor: os registros do tldraw (escopo `document`)
 * que a página manda por POST /api/canvas/diff, guardados em
 * <dadosDir>/canvas.json. A página é a dona do desenho; isto é só o espelho.
 */
import { mkdir, rename, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { log } from "./tipos.ts";

export type Registros = Record<string, unknown>;

export class Canvas {
  private registros: Registros = {};
  private readonly arquivo: string;
  private readonly dadosDir: string;
  private gravacao: Promise<void> = Promise.resolve();
  private sujo = false;

  constructor(dadosDir: string) {
    this.dadosDir = dadosDir;
    this.arquivo = join(dadosDir, "canvas.json");
    this.recarregar();
  }

  ler(): Registros {
    return { ...this.registros };
  }

  aplicar(diff: { put?: Registros; remove?: string[] }): void {
    for (const [id, registro] of Object.entries(diff.put ?? {})) this.registros[id] = registro;
    for (const id of diff.remove ?? []) delete this.registros[id];
    this.agendarGravacao();
  }

  /** Grava em série; várias mudanças seguidas viram uma gravação só. */
  private agendarGravacao(): void {
    if (this.sujo) return;
    this.sujo = true;
    this.gravacao = this.gravacao
      .then(async () => {
        this.sujo = false;
        const json = JSON.stringify({ registros: this.registros });
        await mkdir(this.dadosDir, { recursive: true });
        const temporario = `${this.arquivo}.${process.pid}.tmp`;
        await writeFile(temporario, json, "utf8");
        await rename(temporario, this.arquivo);
      })
      .catch((erro) => log("não consegui gravar", this.arquivo, erro));
  }

  async descarregar(): Promise<void> {
    await this.gravacao;
  }

  private recarregar(): void {
    if (!existsSync(this.arquivo)) return;
    try {
      const dados = JSON.parse(readFileSync(this.arquivo, "utf8")) as { registros?: unknown };
      if (dados.registros && typeof dados.registros === "object" && !Array.isArray(dados.registros)) {
        this.registros = dados.registros as Registros;
      }
      log(`canvas recarregado: ${Object.keys(this.registros).length} registro(s)`);
    } catch (erro) {
      log("canvas.json ilegível, começando vazio", erro);
    }
  }
}
