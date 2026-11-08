#!/usr/bin/env bash
# category: Voice
# what: behaviour test: a fresh agent with the shared voice answers a neutral probe in at most 3 sentences and 60 words (slow: opens a real agent)
# fix: run scripts/ag-voice-probe (opens a scratch agent, asks two neutral probes, counts sentences and words); if the voice does not hold, switch the mechanism (output style <-> session-start hook) and probe again
R="$AG_SKILL"
P="$R/scripts/ag-voice-probe"
[ -x "$P" ] || { echo "scripts/ag-voice-probe is missing (nothing to measure the voice with)"; exit 1; }
out="$("$P" 2>&1)"; rc=$?
[ "$rc" -eq 0 ] || { echo "voice probe unavailable or failed: $(printf '%s' "$out" | tail -2 | tr '\n' ' ' | cut -c1-160)"; exit "$rc"; }
echo "$out" | tail -1
