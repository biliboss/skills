#!/usr/bin/env bash
# category: Doctor
# what: the report is for humans (category blocks, summary) and for agents (FOR AGENTS block, stable --json with id, category, status, evidence, fix, order)
# fix: make ag-doctor read "# category:", "# what:" and "# fix:" from each check (categories.tsv for the old ones), group the output by category, print a FOR AGENTS block with NEXT steps, and add --json
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/checks" "$tmp/pendentes"
printf '#!/usr/bin/env bash\n# category: Alpha\n# what: passes\necho "all good"\nexit 0\n' > "$tmp/checks/a-pass.sh"
printf '#!/usr/bin/env bash\n# category: Beta\n# what: pending\n# fix: build the thing\necho "not built"\nexit 1\n' > "$tmp/pendentes/b-pend.sh"
human="$(AG_DOCTOR="$tmp" "$BIN/ag-doctor" 2>&1)"
for need in 'ALPHA' 'BETA' 'FOR AGENTS' 'NEXT 1)' 'build the thing'; do
  printf '%s\n' "$human" | grep -q "$need" || { echo "human report lacks '$need'"; exit 1; }
done
json="$(AG_DOCTOR="$tmp" "$BIN/ag-doctor" --json 2>&1)"
printf '%s' "$json" | jq -e 'type=="array" and length==2 and all(.[]; has("id") and has("category") and has("status") and has("evidence") and has("fix") and has("order"))' >/dev/null 2>&1 \
  || { echo "--json is not an array of {id, category, status, evidence, fix, order}"; exit 1; }
printf '%s' "$json" | jq -e 'map(select(.status=="PEND"))[0].fix=="build the thing"' >/dev/null 2>&1 || { echo "--json does not carry the fix of a pending check"; exit 1; }
echo "report by category with a FOR AGENTS block; --json has id, category, status, evidence, fix and order"
