/**
 * Os patches no disco (a pasta Patches/ do RimWorld): cada produto é um "mod" e
 * guarda os seus em <produto>/patches/*.json. As pastas vêm de PATCHES_DIRS
 * (lista separada por ":") ou, sem ela, de $DESIGN_PRODUTOS/<produto>/patches/.
 * Ordem de carga: produto em ordem alfabética (ou a ordem de PATCHES_DIRS),
 * arquivo por nome. A leitura é a cada chamada, com cache por mtime.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { problemasDoPatch, type Patch } from "./patches.ts";

export type PatchCarregado = { nome: string; arquivo: string; patch: Patch };
export type PatchInvalido = { arquivo: string; problemas: string[] };
export type PatchesCarregados = { patches: PatchCarregado[]; invalidos: PatchInvalido[]; assinatura: string };

/** As pastas de patches pelo ambiente, lido a cada chamada. */
export function pastasDePatches(env: NodeJS.ProcessEnv = process.env): string[] {
  const lista = env.PATCHES_DIRS;
  if (lista !== undefined && lista.trim() !== "") return lista.split(":").filter((p) => p.trim() !== "");
  const produtos = env.DESIGN_PRODUTOS;
  if (!produtos) return [];
  try {
    return readdirSync(produtos)
      .sort()
      .map((p) => join(produtos, p, "patches"))
      .filter((p) => existsSync(p));
  } catch {
    return [];
  }
}

type Entrada = { mtimeMs: number; size: number; patch?: Patch; problemas?: string[] };

export class PatchesDoDisco {
  private readonly cache = new Map<string, Entrada>();

  /** `pastas`: quem diz as pastas a cada chamada (padrão: o ambiente). */
  constructor(private readonly pastas: () => string[] = () => pastasDePatches()) {}

  carregar(): PatchesCarregados {
    const patches: PatchCarregado[] = [];
    const invalidos: PatchInvalido[] = [];
    const partes: string[] = [];
    for (const pasta of this.pastas()) {
      let arquivos: string[];
      try {
        arquivos = readdirSync(pasta).filter((a) => a.endsWith(".json")).sort();
      } catch {
        continue;
      }
      const produto = basename(pasta) === "patches" ? basename(dirname(pasta)) : basename(pasta);
      for (const a of arquivos) {
        const caminho = join(pasta, a);
        let st;
        try {
          st = statSync(caminho);
        } catch {
          continue;
        }
        if (!st.isFile()) continue;
        partes.push(`${caminho}:${st.mtimeMs}:${st.size}`);
        let e = this.cache.get(caminho);
        if (!e || e.mtimeMs !== st.mtimeMs || e.size !== st.size) {
          e = { mtimeMs: st.mtimeMs, size: st.size };
          try {
            const bruto = JSON.parse(readFileSync(caminho, "utf8"));
            const problemas = problemasDoPatch(bruto);
            if (problemas.length > 0) e.problemas = problemas;
            else e.patch = bruto as Patch;
          } catch (err) {
            e.problemas = [`não li o JSON: ${err instanceof Error ? err.message : err}`];
          }
          this.cache.set(caminho, e);
        }
        if (e.patch) patches.push({ nome: `${produto}/${a.slice(0, -".json".length)}`, arquivo: caminho, patch: e.patch });
        else invalidos.push({ arquivo: caminho, problemas: e.problemas ?? [] });
      }
    }
    return { patches, invalidos, assinatura: partes.join("|") };
  }
}
