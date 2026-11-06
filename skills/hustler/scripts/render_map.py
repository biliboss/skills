#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Render a hustler positioning map (one standalone HTML + inline SVG) from a JSON file.

The JSON is the project's data; re-running the skill edits it and re-renders, so the map never drifts.
Shape (all text is for a human, free language):
  title, job, customer, x_label, y_label, upper_label,
  items:    [{name, x, y, kind: alt|nothing|us|target, note, price?, src?, dx?, dy?}]   x, y in 0..10
  findings: [str], models: [{name, who_pays, what}], recheck: [str], sources: [{label, url}]
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

W, H, L, R, T, B = 760, 560, 70, 30, 30, 70  # canvas and margins
ACCENT = "#7a1f2b"  # bordô: only "us"


def px(v: float) -> float:
    return L + (v + 0.7) / 11.4 * (W - L - R)


def py(v: float) -> float:
    return H - B - (v + 0.7) / 11.4 * (H - T - B)


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def svg(d: dict) -> str:
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(d["title"])}">']
    # upper-right quadrant: the target area, a light gray tile
    out.append(f'<rect x="{px(5):.0f}" y="{T}" width="{W - R - px(5):.0f}" height="{py(5) - T:.0f}" class="tile"/>')
    out.append(f'<text x="{px(10) + 38:.0f}" y="{py(5) - 8:.0f}" class="qlabel" text-anchor="end">{esc(d.get("upper_label", "upper right"))}</text>')
    out.append(f'<line x1="{px(5):.0f}" y1="{T}" x2="{px(5):.0f}" y2="{H - B}" class="axis"/>')
    out.append(f'<line x1="{L}" y1="{py(5):.0f}" x2="{W - R}" y2="{py(5):.0f}" class="axis"/>')
    out.append(f'<rect x="{L}" y="{T}" width="{W - L - R}" height="{H - T - B}" class="frame"/>')
    out.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 26}" class="alabel" text-anchor="middle">{esc(d["x_label"])} →</text>')
    out.append(f'<text transform="translate(22 {(T + H - B) / 2:.0f}) rotate(-90)" class="alabel" text-anchor="middle">{esc(d["y_label"])} →</text>')
    for it in d["items"]:
        x, y = px(it["x"]), py(it["y"])
        kind = it.get("kind", "alt")
        dx, dy = it.get("dx", 12), it.get("dy", 4)
        anchor = "end" if dx < 0 else "start"
        cls = {"us": "us", "target": "target", "nothing": "nothing"}.get(kind, "alt")
        out.append(f'<g class="pt {cls}"><title>{esc(it["name"])}: {esc(it.get("note", ""))}</title>')
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{9 if kind in ("us", "target") else 6}"/>')
        out.append(f'<text x="{x + dx:.0f}" y="{y + dy:.0f}" text-anchor="{anchor}">{esc(it["name"])}</text></g>')
    out.append("</svg>")
    return "\n".join(out)


def rows(d: dict) -> str:
    r = []
    for it in d["items"]:
        src = f'<a href="{esc(it["src"])}">fonte</a>' if it.get("src") else ""
        r.append(
            f'<tr class="{esc(it.get("kind", "alt"))}"><td class="n">{esc(it["name"])}</td>'
            f'<td class="num">{it["x"]:g}</td><td class="num">{it["y"]:g}</td>'
            f'<td>{esc(it.get("price", ""))}</td><td>{esc(it.get("note", ""))} {src}</td></tr>'
        )
    return "\n".join(r)


def page(d: dict) -> str:
    li = lambda xs: "\n".join(f"<li>{esc(x)}</li>" for x in xs)  # noqa: E731
    models = "\n".join(
        f'<tr><td class="n">{esc(m["name"])}</td><td>{esc(m["who_pays"])}</td><td>{esc(m["what"])}</td></tr>'
        for m in d.get("models", [])
    )
    srcs = "\n".join(
        f'<li><a href="{esc(s["url"])}">{esc(s["label"])}</a></li>' if s.get("url") else f"<li>{esc(s['label'])}</li>"
        for s in d.get("sources", [])
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(d["title"])}</title>
<style>
:root{{--bg:#fafaf9;--fg:#1c1c1b;--dim:#6f6e69;--line:#e2e1dc;--tile:#efeeea;--accent:{ACCENT}}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--fg:#ecebe7;--dim:#9d9b94;--line:#2c2b29;--tile:#1f1e1c;--accent:#d27a88}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:40px 16px 72px}}
h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:36px 0 8px;font-weight:600}}
.dim{{color:var(--dim)}} a{{color:inherit}}
svg{{width:100%;height:auto;display:block}}
.tile{{fill:var(--tile)}} .frame{{fill:none;stroke:var(--line)}} .axis{{stroke:var(--line);stroke-dasharray:4 4}}
.qlabel{{fill:var(--dim);font-size:12px}} .alabel{{fill:var(--dim);font-size:12px}}
.pt text{{fill:var(--fg);font-size:12px}} .pt.alt circle{{fill:var(--dim)}} .pt.nothing circle{{fill:none;stroke:var(--dim);stroke-dasharray:2 2}}
.pt.us circle{{fill:var(--accent)}} .pt.us text,.pt.target text{{fill:var(--accent);font-weight:700}}
.pt.target circle{{fill:none;stroke:var(--accent);stroke-width:2;stroke-dasharray:3 3}}
table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--dim);font-weight:600}} td.n{{font-weight:600;white-space:nowrap}} td.num{{font-variant-numeric:tabular-nums;text-align:right}}
tr.us td.n,tr.target td.n{{color:var(--accent)}}
.tw{{overflow-x:auto}} ul,ol{{padding-left:20px}} li{{margin:4px 0}}
footer{{margin-top:40px;color:var(--dim);font-size:12px}}
</style></head><body><main>
<h1>{esc(d["title"])}</h1>
<p class="dim">{esc(d["job"])}</p>
<p class="dim">Cliente: {esc(d["customer"])}</p>
{svg(d)}
<h2>Onde está cada um</h2>
<div class="tw"><table><thead><tr><th>Alternativa</th><th>{esc(d["x_label"])}</th><th>{esc(d["y_label"])}</th><th>Preço</th><th>Nota e fonte</th></tr></thead><tbody>
{rows(d)}
</tbody></table></div>
<h2>O que o mapa diz</h2><ol>{li(d.get("findings", []))}</ol>
<h2>Modelos de negócio</h2>
<div class="tw"><table><thead><tr><th>Modelo</th><th>Quem paga</th><th>O quê</th></tr></thead><tbody>{models}</tbody></table></div>
<h2>Rever na próxima rodada</h2><ul>{li(d.get("recheck", []))}</ul>
<h2>Fontes</h2><ul>{srcs}</ul>
<footer>hustler · {esc(d.get("date", ""))} · notas 0–10 marcadas “estimativa” são nossas, não dado do fornecedor.</footer>
</main></body></html>
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: render_map.py <map.json> <out.html>", file=sys.stderr)
        return 2
    d = json.loads(Path(sys.argv[1]).read_text())
    for k in ("title", "job", "customer", "x_label", "y_label", "items"):
        if k not in d:
            print(f"render_map.py: missing '{k}' in {sys.argv[1]}", file=sys.stderr)
            return 1
    for it in d["items"]:
        if not (0 <= it["x"] <= 10 and 0 <= it["y"] <= 10):
            print(f"render_map.py: {it['name']} outside 0..10", file=sys.stderr)
            return 1
    Path(sys.argv[2]).write_text(page(d))
    print(sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
