#!/usr/bin/env python3
"""ratchet.py: catraca de gates com legado. Só stdlib; copie este arquivo para o projeto (ex.: .gates/ratchet.py).

Uso:
  ratchet.py --name X --baseline .gates-baseline.json [--update] [--ignore REGEX]... -- <comando> [args]

Roda o comando, junta stdout e stderr e normaliza cada linha de saída tirando números de linha e coluna
(`a.py:12:5:`, `a.ts(3,9)`, `[1:1 - 15:3]`, `line=3,col=5`) e o diretório atual. Conta por linha normalizada e compara com a
linha de base do nome X: reprova só o que aumentou e mostra o que piorou. Comando com saída 0 passa sem comparar.
--ignore descarta linhas (regex) antes de contar: resumos como "Found 3 errors.". --update grava a contagem atual como
linha de base de X (cria o arquivo e a entrada se não existirem), sem reprovar.
Sem entrada de X na linha de base, vale a linha de base vazia: qualquer diagnóstico reprova.
Saída: 0 passou (ou --update), 1 piorou, 2 uso ou comando não executável.
"""
import collections
import json
import os
import re
import subprocess
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")
STRIPS = [
    re.compile(r"\[\d+:\d+ - \d+:\d+\]"),
    re.compile(r"\b(?:line|endLine|col|endColumn)=\d+,?"),
    re.compile(r"\(\d+,\d+\)"),
    re.compile(r":\d+(?::\d+)?(?=[:\s]|$)"),
]


def normalize(line, cwd):
    line = line.replace(cwd + os.sep, "").rstrip()
    for rx in STRIPS:
        line = rx.sub("", line)
    return line


def parse(argv):
    opts = {"name": None, "baseline": None, "update": False, "ignore": []}
    i = 0
    while i < len(argv) and argv[i] != "--":
        a = argv[i]
        if a == "--update":
            opts["update"] = True
        elif a in ("--name", "--baseline", "--ignore") and i + 1 < len(argv):
            i += 1
            if a == "--ignore":
                opts["ignore"].append(re.compile(argv[i]))
            else:
                opts[a[2:]] = argv[i]
        else:
            return None, None
        i += 1
    cmd = argv[i + 1:]
    if not opts["name"] or not opts["baseline"] or not cmd:
        return None, None
    return opts, cmd


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    opts, cmd = parse(argv)
    if opts is None:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except OSError as exc:
        print(f"ratchet: não executou {cmd[0]}: {exc}", file=sys.stderr)
        return 2
    cwd = os.getcwd()
    counts = collections.Counter()
    for raw in ANSI.sub("", proc.stdout).splitlines():
        if not raw.strip() or any(rx.search(raw) for rx in opts["ignore"]):
            continue
        counts[normalize(raw, cwd)] += 1

    base_path = opts["baseline"]
    data = {}
    if os.path.exists(base_path):
        with open(base_path, encoding="utf-8") as fh:
            data = json.load(fh)

    if opts["update"]:
        data[opts["name"]] = dict(sorted(counts.items()))
        with open(base_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"ratchet {opts['name']}: linha de base com {sum(counts.values())} ocorrência(s) em {len(counts)} linha(s)")
        return 0

    if proc.returncode == 0:
        return 0
    if not counts:
        print(f"ratchet {opts['name']}: o comando saiu com {proc.returncode} sem nenhuma saída", file=sys.stderr)
        return 1
    base = data.get(opts["name"], {})
    worse = [(line, base.get(line, 0), n) for line, n in sorted(counts.items()) if n > base.get(line, 0)]
    if not worse:
        return 0
    print(f"ratchet {opts['name']}: piorou contra a linha de base ({base_path})")
    for line, before, now in worse:
        print(f"  {before} -> {now}  {line}")
    if opts["name"] not in data:
        print(f"  (sem linha de base para '{opts['name']}': para registrar o legado, rode com --update)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
