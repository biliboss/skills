# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Keyword ideas from free sources, read-only.

    suggest.sh <seed> [<seed> ...] [--expand] [--hl pt-BR] [--gl br]
    opportunities.sh [--days 28] [--min-impressions 20] [--max-ctr 0.02] [--limit 1000]

suggest: Google's autocomplete (what people type after the seed), optionally expanded with the alphabet and the
Portuguese question words. opportunities: reads our own Search Console through the search-console skill's gsc.sh
(SEARCH_CONSOLE_SH, else the sibling skill) and lists the striking-distance queries (average position 4 to 20 with
impressions) and the queries and pages with many impressions and few clicks. Output is one JSON document on stdout.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SUGGEST = os.environ.get("KW_SUGGEST_URL", "https://suggestqueries.google.com/complete/search")  # override: tests
UA = "Mozilla/5.0 (compatible; biliboss-keyword-ideas/0.1; +https://github.com/biliboss/skills)"
QUESTIONS = ["como", "quanto", "qual", "onde", "quando", "por que", "o que", "melhor", "vale a pena"]
LETTERS = "abcdefghijlmnopqrstuvz"  # the Portuguese alphabet without k, w, y, which start few words


def suggest_one(q: str, hl: str, gl: str) -> list[str]:
    url = SUGGEST + "?" + urllib.parse.urlencode({"client": "firefox", "hl": hl, "gl": gl, "q": q})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"kw: autocomplete falhou para {q!r}: {e}", file=sys.stderr)
        return []
    return [s for s in (data[1] if len(data) > 1 else []) if isinstance(s, str)]


def words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).split()


def cmd_suggest(a):
    seen: dict[str, str] = {}
    dropped = 0
    for seed in a.seeds:
        seed = " ".join(seed.split())
        need = set(words(seed))
        probes = [seed]
        if a.expand:
            probes += [f"{seed} {c}" for c in LETTERS] + [f"{w} {seed}" for w in QUESTIONS]
        for p in probes:
            for s in suggest_one(p, a.hl, a.gl):
                # keep only suggestions holding every seed word as a whole word ("como creci" also returns the
                # Spanish "como crecio china")
                if not need <= set(words(s)):
                    dropped += 1
                    continue
                seen.setdefault(s, p)
            if a.expand:
                time.sleep(0.15)  # be gentle with the free endpoint
    qs = [" ".join(words(w)) + " " for w in QUESTIONS]
    rows = [{"text": t, "from": p, "question": any((" ".join(words(t)) + " ").startswith(q) for q in qs)}
            for t, p in sorted(seen.items())]
    return {"seeds": a.seeds, "hl": a.hl, "gl": a.gl, "expanded": a.expand, "total": len(rows),
            "dropped_without_seed": dropped, "suggestions": rows}


def gsc_path() -> str:
    env = os.environ.get("SEARCH_CONSOLE_SH")
    if env:
        return env
    sibling = Path(__file__).resolve().parents[2] / "search-console" / "scripts" / "gsc.sh"
    if sibling.is_file():
        return str(sibling)
    sys.exit("kw: não achei o gsc.sh da skill search-console (instale a skill ou defina SEARCH_CONSOLE_SH)")


def gsc(by: str, days: int, limit: int) -> dict:
    cmd = [gsc_path(), "query", "--days", str(days), "--by", by, "--limit", str(limit)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"kw: o gsc.sh falhou ({' '.join(cmd[1:])}): {r.stderr.strip()[-400:]}")
    return json.loads(r.stdout)


def cmd_opportunities(a):
    q, p = gsc("query", a.days, a.limit), gsc("page", a.days, a.limit)
    near = [r for r in q["rows"] if 4 < r["position"] <= 20 and r["impressions"] >= a.min_impressions]
    near.sort(key=lambda r: -r["impressions"])

    def low(rows):
        out = [r for r in rows
               if r["position"] <= 10 and r["impressions"] >= a.min_impressions and r["ctr"] < a.max_ctr]
        return sorted(out, key=lambda r: -r["impressions"])

    return {
        "site": q.get("site"), "from": q.get("from"), "to": q.get("to"),
        "criteria": {"min_impressions": a.min_impressions, "max_ctr": a.max_ctr,
                     "striking_distance": "posição média acima de 4 e até 20"},
        "rows_read": {"query": len(q["rows"]), "page": len(p["rows"])},
        "striking_distance": near,
        "low_ctr_queries": low(q["rows"]),
        "low_ctr_pages": low(p["rows"]),
    }


def main():
    ap = argparse.ArgumentParser(prog="keyword-ideas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("suggest")
    s.add_argument("seeds", nargs="+")
    s.add_argument("--expand", action="store_true", help="also the seed + each letter and each question word + seed")
    s.add_argument("--hl", default="pt-BR")
    s.add_argument("--gl", default="br")
    o = sub.add_parser("opportunities")
    o.add_argument("--days", type=int, default=28)
    o.add_argument("--min-impressions", type=int, default=20)
    o.add_argument("--max-ctr", type=float, default=0.02)
    o.add_argument("--limit", type=int, default=1000)
    a = ap.parse_args()
    res = cmd_suggest(a) if a.cmd == "suggest" else cmd_opportunities(a)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
