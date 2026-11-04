#!/bin/sh
# projeto.sh <project-id | url do projeto>: o retrato de um projeto antes de mexer nele.
#   Status, líder e membros, os marcos com o progresso e os cartões de cada um, os cartões sem marco
#   e o último update (autor, saúde, começo do texto). Cabe no limite de complexidade da API.
set -eu
aqui=$(cd "$(dirname "$0")" && pwd)
[ $# -eq 1 ] || { echo "uso: projeto.sh <project-id | url>" >&2; exit 2; }
id=$1
case "$id" in
  http*) slug=$(printf '%s' "$id" | sed -E 's#.*/project/([^/?#]+).*#\1#'); id=${slug##*-} ;;
esac
q="query{project(id:\"$id\"){name url state status{name} description lead{name} members(first:10){nodes{name}}
  projectMilestones(first:5){nodes{id name progress issues(first:20){nodes{identifier title state{name} delegate{name}}}}}
  issues(first:30,filter:{projectMilestone:{null:true}}){nodes{identifier title state{name}}}
  projectUpdates(first:1){nodes{id url createdAt health user{name} body}}}}"
"$aqui/lin.sh" "$q" | jq -r '
  if .errors then .errors[0].message else .data.project |
  "\(.name) — \(.status.name) (\(.state))\n\(.url)\n\(.description // "")\nlíder: \(.lead.name // "-") · membros: \([.members.nodes[].name]|join(", "))\n",
  (.projectMilestones.nodes[] | "== marco: \(.name) · \((.progress|floor))%\n" + ([.issues.nodes[] | "   \(.identifier) [\(.state.name)] \(.title)\(if .delegate then " · delegado: "+.delegate.name else "" end)"]|join("\n"))),
  "== sem marco",
  (.issues.nodes[] | "   \(.identifier) [\(.state.name)] \(.title)"),
  (.projectUpdates.nodes[] | "== último update: \(.createdAt[0:16]) · \(.user.name) · \(.health)\n\(.url)\n\(.body[0:400])")
  end'
