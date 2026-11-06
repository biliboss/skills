# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Watch the macOS clipboard; when it holds a key of the expected shape,
pipe it into envless (stdin, never argv), then clear the clipboard.

The value is never printed, logged or returned. Output is only status lines.
Exit: 0 saved, 1 envless refused, 2 no vault, 3 timeout.

Usage:
  uv run vigia-copiar.py --cofre ~/cofre-x --nome API_TOKEN \
      [--env dev] [--formato hex32|livre] [--minutos 10]
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

FORMATOS = {
    "hex32": re.compile(r"[0-9a-fA-F]{32}"),
    # any single token, no spaces, 20-200 chars (when the format is unknown)
    "livre": re.compile(r"[A-Za-z0-9_\-\.:]{20,200}"),
}


def ler_clipboard() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def limpar_clipboard() -> None:
    subprocess.run(["pbcopy"], input="", text=True, check=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cofre", required=True)
    p.add_argument("--nome", required=True)
    p.add_argument("--env", default="dev")
    p.add_argument("--formato", choices=sorted(FORMATOS), default="hex32")
    p.add_argument("--minutos", type=float, default=10)
    p.add_argument("--intervalo", type=float, default=0.5)
    a = p.parse_args()

    cofre = os.path.expanduser(a.cofre)
    if not os.path.isfile(os.path.join(cofre, ".envless", "recipients")):
        print(f"❌ cofre não encontrado em {cofre}")
        return 2

    padrao = FORMATOS[a.formato]
    fim = time.monotonic() + a.minutos * 60
    vistos: set[str] = set()
    print(f"👀 vigiando o copiar ({a.formato}), até {a.minutos:g} min…", flush=True)

    while time.monotonic() < fim:
        valor = ler_clipboard().strip()
        if valor and padrao.fullmatch(valor):
            r = subprocess.run(
                ["envless", "set", a.nome, f"--env={a.env}"],
                input=valor, text=True, cwd=cofre,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            limpar_clipboard()
            tamanho = len(valor)
            valor = ""
            if r.returncode != 0:
                print("❌ o cofre recusou a gravação; o copiar já foi limpo")
                return 1
            print(f"✅ chave guardada no cofre ({tamanho} caracteres); copiar limpo")
            return 0
        if valor:
            h = hashlib.sha256(valor.encode()).hexdigest()
            if h not in vistos:
                vistos.add(h)
                print("… copiou algo, mas não tem cara de chave; sigo vigiando", flush=True)
        time.sleep(a.intervalo)

    print("⏰ tempo acabou, nenhuma chave vista")
    return 3


if __name__ == "__main__":
    sys.exit(main())
