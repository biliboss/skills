#!/bin/bash
# bw.sh: the owner's Bitwarden vault behind the Contas module, through the official CLI (bw).
#   bw.sh status   -> {"status":"locked|unlocked|unauthenticated","email":..,"last_sync":..}   (no secret)
#   bw.sh unlock   -> the OWNER runs this in his terminal: bw asks the master password; the session key goes to the
#                     macOS keychain (service bw-session), never to a file, a log or the chat
#   bw.sh lock     -> locks the vault and forgets the session key
#   bw.sh sync     -> pulls the vault and writes ~/.local/state/auth/bitwarden.json: logins' METADATA only
#                     (name, host, username, has 2FA, password reused yes/no, revision). Passwords never leave bw.
#   bw.sh login <host> -> the matching logins' names and usernames (for `devc login`); no password
set -u
OUT=${BW_OUT:-$HOME/.local/state/auth/bitwarden.json}
KC=bw-session
mkdir -p "$(dirname "$OUT")"
session() { security find-generic-password -s "$KC" -w 2>/dev/null; }
status_json() {
  local s; s=$(BW_SESSION=$(session) bw status 2>/dev/null)
  printf '%s' "${s:-{\}}" | jq -c '{status: (.status // "unknown"), email: .userEmail, last_sync: .lastSync}'
}
case "${1:-status}" in
  status) status_json ;;
  unlock)
    key=$(bw unlock --raw) || { echo "bw.sh: desbloqueio cancelado" >&2; exit 1; }
    security add-generic-password -U -s "$KC" -a "$USER" -w "$key"
    unset key; echo "desbloqueado; sessão guardada no keychain ($KC)"; "$0" sync >/dev/null && echo "sincronizado" ;;
  lock) bw lock >/dev/null 2>&1; security delete-generic-password -s "$KC" >/dev/null 2>&1; echo "bloqueado" ;;
  sync)
    S=$(session); [ -n "$S" ] || { jq -cn --argjson st "$(status_json)" '{status:$st, items:[]}' > "$OUT"; cat "$OUT"; exit 0; }
    BW_SESSION=$S bw sync >/dev/null 2>&1 || true
    # jq gets the vault on a pipe and keeps only metadata; a password becomes a hash only to count reuse, then drops
    BW_SESSION=$S bw list items 2>/dev/null | jq -c --argjson st "$(status_json)" '
      [ .[] | select(.type == 1) | {id, name, user: (.login.username // ""),
          host: ((.login.uris // [])[0].uri // "" | sub("^[a-z]+://"; "") | sub("/.*$"; "") | sub("^www\\."; "")),
          totp: ((.login.totp // "") != ""), pw: (.login.password // "" | @base64), rev: .revisionDate} ] as $all
      | ($all | group_by(.pw) | map(select(.[0].pw != "" and length > 1) | .[].id)) as $reused
      | {status: $st, at: (now | todate),
         items: [ $all[] | {id, name, user, host, totp, rev, reused: (.id as $i | $reused | index($i) != null)} ]}' > "$OUT.tmp" \
      && mv "$OUT.tmp" "$OUT"
    jq -c '{status, at, count: (.items | length)}' "$OUT" ;;
  login)
    jq -c --arg h "${2:?host}" '[.items[] | select(.host | endswith($h)) | {name, user}]' "$OUT" ;;
  *) sed -n 2,10p "$0"; exit 2 ;;
esac
