#!/bin/sh
# upload.sh <arquivo> [content-type]: sobe um arquivo para o Linear e imprime a URL (uploads.linear.app).
#   Use a URL num Markdown do Linear: ![descrição](URL). Imagem de repo privado do GitHub não abre lá.
set -eu
aqui=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 1 ] && [ -f "$1" ] || { echo "uso: upload.sh <arquivo> [content-type]" >&2; exit 2; }
f=$1; ct=${2:-}
if [ -z "$ct" ]; then
  case "$f" in *.png) ct=image/png ;; *.jpg|*.jpeg) ct=image/jpeg ;; *.gif) ct=image/gif ;; *.webp) ct=image/webp ;; *.pdf) ct=application/pdf ;; *) ct=application/octet-stream ;; esac
fi
sz=$(wc -c < "$f" | tr -d ' ')
tmp=$(mktemp); out=$(mktemp)
printf '{"ct":"%s","fn":"%s","sz":%s}' "$ct" "$(basename "$f")" "$sz" > "$tmp"
"$aqui/lin.sh" 'mutation($ct:String!,$fn:String!,$sz:Int!){fileUpload(contentType:$ct,filename:$fn,size:$sz){success uploadFile{uploadUrl assetUrl headers{key value}}}}' "$tmp" > "$out"
rm -f "$tmp"
[ "$(jq -r '.data.fileUpload.success' "$out")" = true ] || { jq -c '.errors // .' "$out" >&2; rm -f "$out"; exit 1; }
url=$(jq -r '.data.fileUpload.uploadFile.uploadUrl' "$out"); asset=$(jq -r '.data.fileUpload.uploadFile.assetUrl' "$out")
set --
while IFS= read -r h; do [ -n "$h" ] && set -- "$@" -H "$h"; done <<EOF
$(jq -r '.data.fileUpload.uploadFile.headers[]|.key+": "+.value' "$out")
EOF
rm -f "$out"
code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$@" -H "Content-Type: $ct" -H 'Cache-Control: public, max-age=31536000' --data-binary "@$f" "$url")
[ "$code" = 200 ] || { echo "upload.sh: PUT respondeu $code" >&2; exit 1; }
echo "$asset"
