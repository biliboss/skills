"""The domain module: the domain-model skill's dm_* tables (dev-console SQLite) drawn as Mermaid, live.

/model                 the modeled domains
/model/<slug>          the map: at most MAX entities (aggregates and the most connected first), edges = dm_relation
/model/<slug>.mmd      the Mermaid text plus a version; the page polls it and redraws only when the rows change
Read only, stdlib sqlite3 (the schema lives in skills/domain-model/scripts/models.py). DM_DB overrides the path.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
from html import escape
from pathlib import Path

MAX = 9


def db_path() -> Path:
    return Path(os.environ.get("DM_DB") or Path.home() / ".local/share/dev-console/dev-console.sqlite")


def _rows(sql: str, *args) -> list[dict]:
    try:
        con = sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    except sqlite3.Error:  # no dm_* tables yet
        return []
    finally:
        con.close()


def domains() -> list[dict]:
    return _rows("select slug, name, purpose, status from dm_domain order by slug")


def _id(name: str) -> str:
    return "n_" + re.sub(r"\W", "_", name)


def _label(s: str) -> str:
    return (s or "").replace('"', "'")


TITLES = {"domain": "Domínio", "architecture": "Arquitetura"}
SHAPES = {"value": ('(["', '"])'), "aggregate": ('[["', '"]]'), "store": ('[("', '")]'), "actor": ('(("', '"))'),
          "service": ('[/"', '"/]'), "ui": ('("', '")')}


def diagrams(slug: str) -> list[str]:
    """The diagram types phase 01 holds for this domain, domain first; ['domain'] when the phase is empty."""
    ds = [r["diagram"] for r in _rows('select distinct diagram from "01_overview_diagram" where domain=?', slug)]
    return sorted(ds, key=lambda d: (d != "domain", d)) or ["domain"]


def mermaid(slug: str, diagram: str = "domain") -> str:
    """One picture of phase 01 (≤ MAX nodes): the domain's entities, or the architecture's parts, and how they connect."""
    phase = _rows('select * from "01_overview_diagram" where domain=? and diagram=? order by pos', slug, diagram)
    if phase:  # phase 01 is the curated picture: draw it as written
        ents = [{"name": r["item"], "kind": r["kind"] or "entity", "definition": r["note"], "status": r["status"]}
                for r in phase if r["row"] == "node"]
        rels = [{"src": r["item"], "verb": r["verb"], "dst": r["target"], "cardinality": r["cardinality"]}
                for r in phase if r["row"] == "edge"]
    elif diagram != "domain":
        return 'flowchart LR\n  empty["diagrama vazio"]'
    else:  # no phase 01 yet: derive it from dm_entity + dm_relation
        ents = _rows("select name, kind, definition, status from dm_entity where domain=?", slug)
        rels = _rows("select src, verb, dst, cardinality from dm_relation where domain=?", slug)
    if not ents:
        return 'flowchart LR\n  empty["sem entidades ainda"]'
    degree = {e["name"]: 0 for e in ents}
    for r in rels:
        for k in (r["src"], r["dst"]):
            if k in degree:
                degree[k] += 1
    rank = {"aggregate": 0, "entity": 1, "value": 2}
    keep = ents[:MAX] if phase else sorted(ents, key=lambda e: (rank.get(e["kind"], 3), -degree[e["name"]], e["name"]))[:MAX]
    names = {e["name"] for e in keep}
    out = ["flowchart LR"]
    for e in keep:
        kind = e["kind"]
        shape = SHAPES.get(kind, ('["', '"]'))
        out.append(f'  {_id(e["name"])}{shape[0]}<b>{_label(e["name"])}</b><br/><small>{kind}</small>{shape[1]}')
        out.append(f'  class {_id(e["name"])} {kind}')
        if e["status"] == "draft":
            out.append(f'  class {_id(e["name"])} draft')
    for r in rels:
        if r["src"] in names and r["dst"] in names:
            lab = _label(r["verb"]) + (f' {r["cardinality"]}' if r["cardinality"] else "")
            out.append(f'  {_id(r["src"])} -- "{lab}" --> {_id(r["dst"])}')
    hidden = len(ents) - len(keep)
    if hidden > 0:
        out.append(f'  more["+{hidden} entidades fora do mapa"]:::value')
    out += [
        "  classDef aggregate fill:#fde68a,stroke:#b45309,stroke-width:2px,color:#111",
        "  classDef entity fill:#dbeafe,stroke:#1d4ed8,color:#111",
        "  classDef value fill:#f3f4f6,stroke:#6b7280,color:#111",
        "  classDef actor fill:#fce7f3,stroke:#be185d,color:#111",
        "  classDef ui fill:#dcfce7,stroke:#15803d,color:#111",
        "  classDef service fill:#e0e7ff,stroke:#4338ca,color:#111",
        "  classDef code fill:#dbeafe,stroke:#1d4ed8,color:#111",
        "  classDef store fill:#fde68a,stroke:#b45309,stroke-width:2px,color:#111",
        "  classDef draft stroke-dasharray:5 4",
    ]
    return "\n".join(out)


def version(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><link rel="icon" href="data:,"><style>
:root{{--bg:#fafaf9;--fg:#1c1917;--mute:#78716c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0c0a09;--fg:#f5f5f4;--mute:#a8a29e}}}}
body{{margin:0;padding:16px 24px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
h1{{font-size:20px;margin:0}} p{{color:var(--mute);margin:4px 0 16px}} h2{{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:24px 0 4px}} .d svg{{max-width:100%;height:auto}} .d .node .nodeLabel,.d .node .nodeLabel *{{color:#111!important;fill:#111!important}}
#v{{font:12px ui-monospace,monospace;color:var(--mute)}} a{{color:inherit}}
</style></head><body>
<h1>{name} <span id="v"></span></h1><p>{purpose}</p><div id="all"></div>
<p>tracejado = draft, contínuo = real · máx. {max} itens por diagrama</p>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs';
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({{startOnLoad:false, securityLevel:'loose', theme: dark ? 'dark' : 'default', flowchart:{{htmlLabels:true}}, themeVariables: dark ? {{edgeLabelBackground:'#0c0a09', lineColor:'#a8a29e'}} : {{}}}});
let cur = '', n = 0;
async function tick(){{
  try {{
    const r = await fetch('{src}', {{cache:'no-store'}}); const j = await r.json();
    if (j.version !== cur) {{
      cur = j.version; let html = '';
      for (const d of j.diagrams) {{ const {{svg}} = await mermaid.render('g' + (n++), d.mermaid);
        html += `<h2>${{d.title}}</h2><div class="d">${{svg}}</div>`; }}
      document.getElementById('all').innerHTML = html; document.getElementById('v').textContent = j.version;
    }}
  }} catch (e) {{ console.log('[model]', e); }}
}}
tick(); setInterval(tick, 1500);
</script></body></html>"""


def register(rt, json_response):
    from starlette.responses import HTMLResponse

    @rt("/model")
    def model_index():
        ds = domains()
        if len(ds) == 1:  # one domain: straight to its diagram
            from starlette.responses import RedirectResponse
            return RedirectResponse(f"/model/{ds[0]['slug']}")
        items = "".join(f'<li><a href="/model/{escape(d["slug"])}">{escape(d["name"])}</a> · {escape(d["status"])}</li>'
                        for d in ds) or "<li>nenhum domínio modelado (skill domain-model)</li>"
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>Modelos</title><style>body{{font:15px system-ui;padding:16px 24px;background:#0c0a09;color:#f5f5f4}}a{{color:inherit}}</style><h1>Modelos</h1><ul>{items}</ul>")

    @rt("/model/{slug}.mmd")
    def model_mmd(slug: str):
        ds = [{"diagram": d, "title": TITLES.get(d, d), "mermaid": mermaid(slug, d)} for d in diagrams(slug)]
        return json_response({"slug": slug, "version": version("".join(x["mermaid"] for x in ds)), "diagrams": ds,
                              "mermaid": ds[0]["mermaid"]})

    @rt("/model/{slug}")
    def model_page(slug: str):
        d = next((x for x in domains() if x["slug"] == slug), None)
        if not d:
            return HTMLResponse(f"domínio {escape(slug)} não está em dm_domain", status_code=404)
        return HTMLResponse(PAGE.format(title=escape(d["name"]), name=escape(d["name"]), purpose=escape(d["purpose"] or ""),
                                        src=f"/model/{escape(slug)}.mmd", max=MAX))

    return model_index, model_mmd, model_page


if __name__ == "__main__":  # console_model.py <slug>: print the Mermaid
    print(mermaid(sys.argv[1] if len(sys.argv) > 1 else "domain-model", sys.argv[2] if len(sys.argv) > 2 else "domain"))
