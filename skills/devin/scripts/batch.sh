#!/bin/sh
# batch.sh <manifesto.json> --repo <caminho> [--base <ref>] [--mode <permissão>]
# Dispara um lote de cartões pelo run.sh e imprime cada id em stdout, uma linha, assim que dispara.
# Manifesto: array de {"name": slug, "prompt_file": caminho, "allowed": ["arquivo", "dir/*", "dir/**"], "model": "opcional"}.
# prompt_file relativo vale a partir da pasta do manifesto. Tudo é validado antes de disparar (nada dispara se algo falha):
# name único e slug-válido (a-z, 0-9, hífen, até 40), prompt_file existe, allowed não vazio e relativo ao repositório.
# A base é resolvida para um sha uma vez e é a mesma em todos os cartões. Grava allowed (um por linha) em $dir/allowed.
# Teto: DEVIN_MAX_PARALLEL (padrão 8, no máximo 8) conta as rodadas running de todo o DEVIN_RUNS_DIR, não só as do lote;
# sem vaga, espera (sleep 2) dentro do script. Por isso o lote demora: rode em background no harness
# (run_in_background), nunca em primeiro plano, e leia os ids pela saída. Dois cartões com o mesmo arquivo em allowed
# geram aviso no stderr e o lote segue (o conflito aparece no merge.sh).
# Saída: 0 todos disparados, 1 manifesto inválido ou falha ao disparar, 2 uso.
set -eu
. "$(dirname -- "$0")/lib.sh"

manifest="" repo="" base="HEAD" mode=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="${2:?}"; shift 2 ;;
    --base) base="${2:?}"; shift 2 ;;
    --mode) mode="${2:?}"; shift 2 ;;
    -*) die "opção desconhecida: $1" 2 ;;
    *) if [ -n "$manifest" ]; then die "um manifesto só" 2; fi; manifest="$1"; shift ;;
  esac
done
[ -n "$manifest" ] || die "uso: batch.sh <manifesto.json> --repo <caminho> [--base <ref>] [--mode <permissão>]" 2
[ -n "$repo" ] || die "falta --repo" 2
[ -f "$manifest" ] || die "manifesto não encontrado: $manifest" 2
command -v jq >/dev/null 2>&1 || die "jq não instalado" 2
jq -e . "$manifest" >/dev/null 2>&1 || die "manifesto não é JSON válido: $manifest"
max=$(max_parallel)
top=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) || die "não é um repositório git: $repo"
base_sha=$(git -C "$top" rev-parse --verify "$base^{commit}" 2>/dev/null) || die "base não encontrada: $base"
mdir=$(CDPATH= cd -- "$(dirname -- "$manifest")" && pwd)

errors=$(jq -r '
  if (type != "array") or (length == 0) then "o manifesto deve ser um array não vazio"
  else
    ( to_entries[] | .key as $i | .value as $c |
      if ($c | type) != "object" then "cartão \($i): não é um objeto"
      else
        ( if ($c.name | type) != "string" or (($c.name | test("^[a-zA-Z0-9-]{1,40}$")) | not)
            then "cartão \($i): name ausente ou inválido (a-z, 0-9, hífen, até 40)" else empty end ),
        ( if ($c.prompt_file | type) != "string" or $c.prompt_file == ""
            then "cartão \($i): falta prompt_file" else empty end ),
        ( if ($c.allowed | type) != "array" or ($c.allowed | length) == 0
              or ([$c.allowed[] | select((type != "string") or . == "")] | length) > 0
            then "cartão \($i): allowed deve ser uma lista não vazia de textos"
          elif ([$c.allowed[] | select(test("^/|(^|/)\\.\\.(/|$)"))] | length) > 0
            then "cartão \($i): allowed só aceita caminhos relativos ao repositório, sem .."
          else empty end ),
        ( if ($c | has("model")) and ((($c.model | type) != "string") or $c.model == "")
            then "cartão \($i): model inválido" else empty end )
      end ),
    ( [.[] | select(type == "object") | .name] | group_by(.)[] | select(length > 1) | "name repetido: \(.[0])" )
  end' "$manifest")
if [ -n "$errors" ]; then
  printf '%s\n' "$errors" | sed 's/^/devin: manifesto inválido: /' >&2
  exit 1
fi

list=$(mktemp)
trap 'rm -f "$list"' EXIT
jq -r '.[] | [.name, .prompt_file, (.model // "")] | @tsv' "$manifest" > "$list"
tab=$(printf '\t')

bad=0
while IFS="$tab" read -r name pf model; do
  if [ "${pf#/}" = "$pf" ]; then pf="$mdir/$pf"; fi
  if [ ! -s "$pf" ]; then
    echo "devin: manifesto inválido: prompt_file do cartão $name ausente ou vazio: $pf" >&2
    bad=1
  fi
done < "$list"
[ "$bad" = 0 ] || exit 1

jq -r '[.[] | .name as $n | .allowed[] | {f: ., n: $n}] | group_by(.f)[] | select(length > 1)
  | "aviso: \(.[0].f) está em allowed de mais de um cartão (\([.[].n] | join(", "))): conflito provável no merge"' "$manifest" >&2

mkdir -p "$DEVIN_RUNS_DIR"
while IFS="$tab" read -r name pf model; do
  if [ "${pf#/}" = "$pf" ]; then pf="$mdir/$pf"; fi
  while [ "$(running_count)" -ge "$max" ]; do sleep 2; done
  set -- --repo "$top" --prompt-file "$pf" --name "$name" --base "$base_sha"
  if [ -n "$model" ]; then set -- "$@" --model "$model"; fi
  if [ -n "$mode" ]; then set -- "$@" --mode "$mode"; fi
  id=$(sh "$(dirname -- "$0")/run.sh" "$@") || die "falha ao disparar o cartão $name"
  jq -r --arg n "$name" '.[] | select(.name == $n) | .allowed[]' "$manifest" > "$(run_dir "$id")/allowed"
  printf '%s\n' "$id"
done < "$list"
