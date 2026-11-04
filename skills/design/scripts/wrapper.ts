// Os wrappers de um produto: build, conferir, pastas, foto. Rode pelo wrapper.sh (ele lê o casa.env).
//
//   wrapper.sh build <produto> [id…]   roda a receita ($DESIGN_PRODUTOS/<produto>/render.ts) contra o origin/main do
//                                      produto e grava componentes/<id>/ (componente.json, peca.html, peca.css,
//                                      desktop.css, sprite.svg) com fonte {repo, arquivo, simbolo, commit, receita}
//   wrapper.sh conferir <produto>      quais wrappers têm fonte.commit atrás do origin/main, e se os arquivos
//                                      da fonte (e os da receita) mudaram desde então
//   wrapper.sh pastas <produto>        as pastas absolutas dos componentes e dos rascunhos, uma por linha
//   wrapper.sh foto <produto> [id…] [--saida <pasta>]
//                                      cada wrapper num shadow DOM, a 393 e (com variante) a 1280, em PNG
//
// O repo do produto vem do ambiente: PRODUTO_<PRODUTO>_REPO (o checkout local, só leitura) e
// PRODUTO_<PRODUTO>_REMOTO (o nome no GitHub, que vai no fonte.repo).

import { mkdir, readdir, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { Repo, abrirChrome, medir, CELULAR, DESKTOP, type Componente, type Peca } from "./lib.ts";

// Os produtos moram fora da skill (o código deles é de cada produto, muitas vezes privado):
// DESIGN_PRODUTOS/<produto>/ com referencia.md, render.ts, componentes/ e rascunhos/.
const PRODUTOS = process.env.DESIGN_PRODUTOS;
process.env.DESIGN_LIB = join(import.meta.dir, "lib.ts");
const [cmd, produto, ...resto] = process.argv.slice(2);

function sair(msg: string, codigo = 1): never { console.error(msg); process.exit(codigo); }
if (!cmd || !produto) sair("uso: wrapper.sh build|conferir|pastas|foto <produto> [id…]");
if (!PRODUTOS) sair("falta DESIGN_PRODUTOS no casa.env (a pasta privada dos produtos)");
const pastaProduto = join(PRODUTOS, produto);
if (!existsSync(pastaProduto)) sair(`produto desconhecido: ${produto} (não há ${pastaProduto})`);

function repoDoProduto(): Repo {
  const P = produto.toUpperCase().replace(/[^A-Z0-9]/g, "_");
  const dir = process.env[`PRODUTO_${P}_REPO`], remoto = process.env[`PRODUTO_${P}_REMOTO`];
  if (!dir || !remoto) sair(`faltam PRODUTO_${P}_REPO e PRODUTO_${P}_REMOTO (casa.env)`);
  return new Repo(dir, remoto, process.env[`PRODUTO_${P}_RAMO`] ?? "main");
}

async function wrappers(tipo: "componentes" | "rascunhos"): Promise<string[]> {
  const base = join(pastaProduto, tipo);
  if (!existsSync(base)) return [];
  return (await readdir(base, { withFileTypes: true }))
    .filter((d) => d.isDirectory() && existsSync(join(base, d.name, "componente.json")))
    .map((d) => join(base, d.name)).sort();
}

async function lerJson<T>(arq: string): Promise<T> { return JSON.parse(await Bun.file(arq).text()); }

// ---------- build ----------

async function build(ids: string[]) {
  const repo = repoDoProduto();
  await repo.buscar();
  const commit = await repo.commit();
  const receita = await import(join(pastaProduto, "render.ts"));
  console.log(`${produto}: ${repo.remoto} @ ${commit.slice(0, 10)} (${repo.ref})`);
  const browser = await abrirChrome();
  try {
    const pecas: Peca[] = await receita.construir((a: string) => repo.ler(a), browser, ids);
    const hCel = await medir(browser, pecas.map((p) => ({ id: p.id, html: p.html, css: p.css, sprite: p.sprite, fontes: p.fontes, slots: p.slots, dados: p.dados })), CELULAR);
    const hDesk = await medir(browser, pecas.map((p) => ({ id: p.id, html: p.html, css: p.desktopCss, sprite: p.sprite, fontes: p.fontes, slots: p.slots, dados: p.dados })), DESKTOP);
    for (const p of pecas) {
      const pasta = join(pastaProduto, "componentes", p.id);
      await rm(pasta, { recursive: true, force: true });
      await mkdir(pasta, { recursive: true });
      const comp: Componente = {
        id: `${produto}/${p.id}`, nome: p.nome, descricao: p.descricao, estado: "real",
        w: CELULAR, h: hCel[p.id],
        variantes: { desktop: { w: DESKTOP, h: hDesk[p.id] } },
        slots: p.slots, dados: p.dados,
        fonte: { repo: repo.remoto, arquivo: p.fonte.arquivo, ...(p.fonte.simbolo ? { simbolo: p.fonte.simbolo } : {}), commit, receita: p.fonte.receita },
        ...(p.fontes?.length ? { fontes: p.fontes } : {}),
      };
      if (p.porque) (comp as any).porque = p.porque;
      await Bun.write(join(pasta, "componente.json"), JSON.stringify(comp, null, 2) + "\n");
      await Bun.write(join(pasta, "peca.html"), p.html + "\n");
      await Bun.write(join(pasta, "peca.css"), p.css);
      await Bun.write(join(pasta, "desktop.css"), p.desktopCss);
      if (p.sprite) await Bun.write(join(pasta, "sprite.svg"), p.sprite);
      console.log(`  ${comp.id.padEnd(22)} ${p.fonte.receita.padEnd(8)} ${CELULAR}×${hCel[p.id]}  desktop ${DESKTOP}×${hDesk[p.id]}`);
    }
  } finally { await browser.close(); }
}

// ---------- conferir ----------

async function conferir() {
  const repo = repoDoProduto();
  await repo.buscar();
  const main = await repo.commit();
  let receitaArquivos: string[] = [];
  try { receitaArquivos = Object.values((await import(join(pastaProduto, "render.ts"))).ARQUIVOS ?? {}) as string[]; } catch {}
  console.log(`${produto}: ${repo.ref} = ${main.slice(0, 10)}`);
  let atrasados = 0;
  for (const pasta of await wrappers("componentes")) {
    const c = await lerJson<Componente>(join(pasta, "componente.json"));
    if (!c.fonte) { console.log(`  ${c.id.padEnd(22)} SEM FONTE (um "real" precisa de fonte)`); atrasados++; continue; }
    const de = c.fonte.commit;
    if (de === main) { console.log(`  ${c.id.padEnd(22)} em dia (${de.slice(0, 10)})`); continue; }
    const n = await repo.atras(de).catch(() => NaN);
    const arquivos = [...new Set([c.fonte.arquivo, ...(c.fonte.receita === "executar" ? receitaArquivos : [])])];
    const mudaram: string[] = [];
    for (const a of arquivos) if (await repo.mudou(a, de).catch(() => true)) mudaram.push(a);
    atrasados++;
    console.log(`  ${c.id.padEnd(22)} ${de.slice(0, 10)}: ${Number.isNaN(n) ? "commit fora do main" : `${n} commits atrás`}; ` +
      (mudaram.length ? `mudou ${mudaram.map((m) => m.split("/").pop()).join(", ")} → rode build` : "a fonte não mudou (build só atualiza o commit)"));
  }
  for (const pasta of await wrappers("rascunhos")) {
    const c = await lerJson<Componente>(join(pasta, "componente.json"));
    console.log(`  ${c.id.padEnd(22)} rascunho`);
  }
  if (!atrasados) console.log("tudo em dia");
}

// ---------- pastas ----------

async function pastas() {
  for (const p of [...(await wrappers("componentes")), ...(await wrappers("rascunhos"))]) console.log(p);
}

// ---------- foto ----------

async function lerWrapper(pasta: string): Promise<Componente & { desktopCss?: string }> {
  const c = await lerJson<Componente>(join(pasta, "componente.json"));
  const arq = async (n: string) => (existsSync(join(pasta, n)) ? Bun.file(join(pasta, n)).text() : undefined);
  c.html ??= await arq("peca.html");
  c.css ??= await arq("peca.css");
  c.sprite ??= await arq("sprite.svg");
  const d = c.variantes?.desktop;
  return { ...c, desktopCss: d ? d.css ?? (await arq("desktop.css")) : undefined };
}

async function foto(args: string[]) {
  const i = args.indexOf("--saida");
  const saida = i >= 0 ? resolve(args[i + 1]) : join(tmpdir(), `design-${produto}-fotos`);
  const ids = args.filter((a, k) => k !== i && k !== i + 1);
  await mkdir(saida, { recursive: true });
  const todos = await Promise.all([...(await wrappers("componentes")), ...(await wrappers("rascunhos"))].map(lerWrapper));
  const escolhidos = ids.length ? todos.filter((c) => ids.includes(c.id.split("/").pop()!)) : todos;
  const browser = await abrirChrome();
  try {
    const nome = (id: string) => id.split("/").pop()!;
    const hc = await medir(browser, escolhidos.map((c) => ({ id: c.id, html: c.html ?? "", css: c.css ?? "", sprite: c.sprite, fontes: c.fontes, slots: c.slots, dados: c.dados })), CELULAR, (id) => join(saida, `${nome(id)}.png`));
    const comD = escolhidos.filter((c) => c.desktopCss);
    const hd = await medir(browser, comD.map((c) => ({ id: c.id, html: c.variantes!.desktop!.html ?? c.html ?? "", css: c.desktopCss!, sprite: c.sprite, fontes: c.fontes, slots: c.slots, dados: c.dados })), DESKTOP, (id) => join(saida, `${nome(id)}.desktop.png`));
    for (const c of escolhidos) console.log(`  ${c.id.padEnd(22)} ${c.estado.padEnd(9)} ${CELULAR}×${hc[c.id]} (json ${c.h})${hd[c.id] != null ? `  desktop ${DESKTOP}×${hd[c.id]}` : ""}`);
    console.log(saida);
  } finally { await browser.close(); }
}

if (cmd === "build") await build(resto);
else if (cmd === "conferir") await conferir();
else if (cmd === "pastas") await pastas();
else if (cmd === "foto") await foto(resto);
else sair(`comando desconhecido: ${cmd}`);
