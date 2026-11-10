#!/usr/bin/env python3
"""map.py - measure a repo's tracked files and keep a code-map wiki page honest (stdlib only).

Lists the files git tracks (`git ls-files`, never the untracked ones, so the result does
not depend on the checkout), estimates tokens as bytes/4 and sums them per top-level
folder. Output is text or JSON.

With `--check <page>` it reads the page's frontmatter (`last_mapped`, `total_arquivos`)
and the `modules` list, then asks git which of those top-level folders had a commit after
`last_mapped` (`git log --since`). Exit 2 and one `<page>: mapa-velho: <module> mudou em
<short sha>` line per stale module when any did; exit 0 when the map is up to date.
`--repo` points `--check` at the repo the page describes (default: the page's folder).

Derived from Luiz Ribeiro Coelho's `mapear.py` (viacorretor/the-viacorretor#143), itself
an adaptation of kingbootoshi's Cartographer (MIT). See ../ATTRIBUTION.md.

Usage:
    python3 -I map.py [root] [--format texto|json] [--max-tokens 50000]
    python3 -I map.py --check <page> [--repo <root>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PASTAS_IGNORADAS = {
    "node_modules", ".git", "dist", "build", ".next", "coverage", "vendor", ".venv",
}
LOCKFILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock",
    "Cargo.lock", "poetry.lock", "Pipfile.lock", "composer.lock", "Gemfile.lock",
    "go.sum", "uv.lock",
}
EXTENSOES_IGNORADAS = {
    # imagens
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico", ".tiff", ".psd", ".heic",
    # fontes
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # vídeo e áudio
    ".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v", ".mp3", ".wav", ".ogg",
    # mapas e minificados
    ".map",
    # binários comuns
    ".pdf", ".zip", ".gz", ".tar", ".tgz", ".7z", ".exe", ".dll", ".so", ".dylib", ".bin",
    ".wasm", ".sqlite", ".db",
}
FM_RE = re.compile(r"^---\n([\s\S]*?)\n---\n")


def git(raiz: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(raiz)] + list(args),
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def listar_arquivos(raiz: Path) -> list[Path]:
    # Only tracked files: no -o, so the map is the same in any checkout.
    saida = git(raiz, "ls-files", "-z")
    if saida:
        return [raiz / p for p in saida.split("\0") if p]
    try:  # not a git repo: fall back to the filesystem
        return [p for p in raiz.rglob("*") if p.is_file()]
    except OSError:
        return []


def ignorado(rel: Path) -> bool:
    if any(parte in PASTAS_IGNORADAS for parte in rel.parts[:-1]):
        return True
    nome = rel.name
    if nome in LOCKFILES or nome.endswith(".min.js"):
        return True
    return rel.suffix.lower() in EXTENSOES_IGNORADAS


def binario(caminho: Path) -> bool:
    try:
        with caminho.open("rb") as f:
            return b"\0" in f.read(2048)
    except OSError:
        return True


def mapear(raiz: Path, max_tokens: int) -> dict:
    arquivos, pulados = [], []
    por_pasta: dict[str, dict[str, int]] = defaultdict(lambda: {"arquivos": 0, "tokens": 0})
    for caminho in listar_arquivos(raiz):
        if not caminho.is_file() or caminho.is_symlink():
            continue
        try:
            rel = caminho.relative_to(raiz)
        except ValueError:
            continue
        if ignorado(rel) or binario(caminho):
            continue
        try:
            tokens = caminho.stat().st_size // 4
        except OSError:
            continue
        item = {"arquivo": rel.as_posix(), "tokens": tokens}
        if tokens > max_tokens:
            pulados.append(item)
            continue
        arquivos.append(item)
        pasta = rel.parts[0] if len(rel.parts) > 1 else "."
        por_pasta[pasta]["arquivos"] += 1
        por_pasta[pasta]["tokens"] += tokens
    arquivos.sort(key=lambda a: a["arquivo"])
    return {
        "raiz": str(raiz),
        "total_arquivos": len(arquivos),
        "total_tokens": sum(a["tokens"] for a in arquivos),
        "max_tokens": max_tokens,
        "por_pasta": dict(sorted(por_pasta.items(), key=lambda kv: -kv[1]["tokens"])),
        "arquivos": arquivos,
        "pulados": pulados,
    }


def imprimir_texto(r: dict) -> None:
    print(f"Raiz: {r['raiz']}")
    print(f"Total: {r['total_arquivos']} arquivos, ~{r['total_tokens']:,} tokens (bytes/4)")
    print("\nPor pasta de topo:")
    for pasta, v in r["por_pasta"].items():
        print(f"  {v['tokens']:>10,}  {v['arquivos']:>6} arq  {pasta}")
    if r["pulados"]:
        print(f"\nPulados (> {r['max_tokens']:,} tokens):")
        for a in r["pulados"]:
            print(f"  {a['tokens']:>10,}  {a['arquivo']}")
    print("\nArquivos:")
    for a in r["arquivos"]:
        print(f"  {a['tokens']:>8,}  {a['arquivo']}")


def frontmatter(pagina: Path) -> dict | None:
    """Top-level frontmatter keys; `modules` becomes a list[str]."""
    try:
        texto = pagina.read_text(encoding="utf-8")
    except OSError:
        return None
    m = FM_RE.match(texto)
    if not m:
        return None
    out: dict = {}
    lista = None
    for linha in m.group(1).split("\n"):
        if re.match(r"^\s", linha):
            if lista is not None:
                item = re.match(r"^\s+-\s+(.*?)\s*$", linha)
                if item:
                    out[lista].append(item.group(1).strip("'\""))
            continue
        i = linha.find(":")
        if i <= 0:
            lista = None
            continue
        chave, valor = linha[:i].strip(), linha[i + 1:].strip()
        if valor == "":
            out[chave] = []
            lista = chave
        else:
            out[chave] = valor.strip("'\"")
            lista = None
    return out


def check(pagina: Path, repo: Path) -> int:
    fm = frontmatter(pagina)
    if fm is None:
        print(f"{pagina.name}: mapa-velho: sem frontmatter ou sem `last_mapped`")
        return 2
    last_mapped = fm.get("last_mapped") or ""
    modulos = fm.get("modules") or []
    if isinstance(modulos, str):
        modulos = [modulos]
    if not isinstance(last_mapped, str) or not last_mapped.strip() or not modulos:
        print(f"{pagina.name}: mapa-velho: frontmatter sem `last_mapped` ou sem `modules`")
        return 2
    velhos = []
    for mod in modulos:
        alvo = "." if mod in (".", "./") else mod.rstrip("/") + "/"
        sha = git(repo, "log", "-1", "--format=%h", f"--since={last_mapped.strip()}", "--", alvo).strip()
        if sha:
            velhos.append((mod, sha))
    for mod, sha in velhos:
        print(f"{pagina.name}: mapa-velho: {mod} mudou em {sha}")
    return 2 if velhos else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Estima arquivos e tokens do repositório, localmente.")
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--format", choices=["texto", "json"], default="texto")
    ap.add_argument("--max-tokens", type=int, default=50000)
    ap.add_argument("--check", metavar="PÁGINA",
                    help="lê o frontmatter da página e acusa os módulos com commit depois do last_mapped")
    ap.add_argument("--repo", metavar="RAIZ",
                    help="repo que o --check vigia (default: a pasta da página)")
    args = ap.parse_args(argv)
    if args.check:
        pagina = Path(args.check).resolve()
        if not pagina.is_file():
            print(f"Não é arquivo: {pagina}", file=sys.stderr)
            return 1
        repo = Path(args.repo).resolve() if args.repo else pagina.parent
        return check(pagina, repo)
    raiz = Path(args.raiz).resolve()
    if not raiz.is_dir():
        print(f"Não é pasta: {raiz}", file=sys.stderr)
        return 1
    r = mapear(raiz, args.max_tokens)
    if args.format == "json":
        json.dump(r, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        imprimir_texto(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
