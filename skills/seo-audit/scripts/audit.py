# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""On-page and sitemap SEO audit from the raw HTML (no JavaScript), read-only.

    audit.sh <url> [<url> ...]              one JSON document per run: {"pages": [...]}
    sitemap.sh <site|sitemap url> [--check] [--max 200]

Every page gets the facts (status, redirects, title, description, canonical, robots, h1, lang, viewport, Open Graph,
JSON-LD types, images without alt, visible words) and a list of findings, each with a level (erro, aviso, info), a
code and a sentence. Output is one JSON document on stdout; errors go to stderr with exit 1.
"""
import argparse
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; biliboss-seo-audit/0.1; +https://github.com/biliboss/skills)"
TIMEOUT = 20
TITLE_MAX = 60  # practitioner heuristic: Google cuts the title link by pixel width (~600px), not by characters
DESC_MAX = 160  # same: the snippet is cut by width; Google may also write its own
THIN_WORDS = 150
MAX_BODY = 10 * 1024 * 1024  # a page or sitemap larger than this is cut
TRUSTED_HOSTS: set[str] = set()  # hosts the caller passed by hand; only these may be private or loopback


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(NoRedirect)


def refuse(url: str):
    """Why this URL must not be opened, or None. URLs come from the pages themselves (Location, canonical, <loc>), so
    only http(s) is opened, and a private or loopback address only when the caller passed that host by hand."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return f"esquema {parts.scheme or '(nenhum)'} recusado: só http e https"
    host = parts.hostname or ""
    if host in TRUSTED_HOSTS:
        return None
    try:
        addrs = {str(a[4][0]) for a in socket.getaddrinfo(host, None)}
    except (socket.gaierror, UnicodeError):
        return None  # let the fetch report that it did not resolve
    for addr in addrs:
        ip = ipaddress.ip_address(addr.split("%")[0])
        if not ip.is_global:  # private, loopback, link-local, CGNAT, reserved
            return f"{host} resolve para um endereço interno ({ip}); recusado (só um host passado à mão pode ser interno)"
    return None


def trust(url: str) -> str:
    """Mark the host of a URL the caller passed by hand."""
    host = urllib.parse.urlsplit(url).hostname
    if host:
        TRUSTED_HOSTS.add(host)
    return url


def fetch(url: str, max_hops: int = 10):
    """GET following redirects by hand, so the chain is recorded. Returns (status, final_url, headers, body, chain)."""
    chain = []
    for _ in range(max_hops):
        why = refuse(url)
        if why:
            return None, url, {}, b"", chain + [{"url": url, "error": why}]
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
        try:
            resp = _opener.open(req, timeout=TIMEOUT)
            status, headers, body = resp.status, resp.headers, resp.read(MAX_BODY)
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, e.headers, e.read(MAX_BODY)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return None, url, {}, b"", chain + [{"url": url, "error": str(getattr(e, "reason", e))}]
        if status in (301, 302, 303, 307, 308) and headers.get("Location"):
            nxt = urllib.parse.urljoin(url, headers["Location"])
            chain.append({"url": url, "status": status, "to": nxt})
            url = nxt
            continue
        return status, url, headers, body, chain
    return None, url, {}, b"", chain + [{"url": url, "error": "too many redirects"}]


def decode(body: bytes, headers) -> str:
    ctype = headers.get("Content-Type", "") if headers else ""
    m = re.search(r"charset=([\w-]+)", ctype)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "latin-1"]:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", "replace")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.in_title = None, False
        self.meta, self.links = [], []
        self.h1, self.in_h1, self.h1_buf = [], False, []
        self.lang = None
        self.jsonld, self.in_jsonld, self.jsonld_buf = [], False, []
        self.skip = 0  # inside script/style/noscript
        self.words = 0
        self.imgs, self.imgs_no_alt = 0, 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        elif tag == "title" and self.title is None:
            self.in_title, self.title = True, ""
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "h1":
            self.in_h1, self.h1_buf = True, []
        elif tag == "img":
            self.imgs += 1
            if not a.get("alt", "").strip():
                self.imgs_no_alt += 1
        elif tag == "script":
            if a.get("type", "").lower() == "application/ld+json":
                self.in_jsonld, self.jsonld_buf = True, []
            self.skip += 1
        elif tag in ("style", "noscript", "template"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "h1" and self.in_h1:
            self.in_h1 = False
            self.h1.append(" ".join("".join(self.h1_buf).split()))
        elif tag == "script":
            if self.in_jsonld:
                self.in_jsonld = False
                self.jsonld.append("".join(self.jsonld_buf))
            self.skip = max(0, self.skip - 1)
        elif tag in ("style", "noscript", "template"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title = (self.title or "") + data
        if self.in_jsonld:
            self.jsonld_buf.append(data)
        if self.in_h1:
            self.h1_buf.append(data)
        if not self.skip and not self.in_title:
            self.words += len(re.findall(r"\w+", data))


def meta_value(p: Page, key: str):
    for m in p.meta:
        if m.get("name", "").lower() == key or m.get("property", "").lower() == key:
            return m.get("content")
    return None


def jsonld_types(blocks):
    types, bad = [], 0

    def walk(x):
        if isinstance(x, dict):
            t = x.get("@type")
            if t:
                types.extend(t if isinstance(t, list) else [t])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for b in blocks:
        try:
            walk(json.loads(b))
        except json.JSONDecodeError:
            bad += 1
    return sorted(set(map(str, types))), bad


def norm(u: str) -> str:
    p = urllib.parse.urlsplit(u)
    path = p.path or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path.rstrip("/") or "/", p.query, ""))


def said(status, chain) -> str:
    """'respondeu 404', or why it did not open (refused, did not resolve), for the finding texts."""
    if status is not None:
        return f"respondeu {status}"
    return f"não abriu ({chain[-1].get('error')})" if chain and chain[-1].get("error") else "não abriu"


def audit_page(url: str) -> dict:
    status, final, headers, body, chain = fetch(url)
    out = {"url": url, "final_url": final, "status": status, "redirects": chain, "source": "html-sem-js"}
    f = []
    if status is None:
        out["findings"] = [{"level": "erro", "code": "fetch", "text": f"não abriu: {chain[-1].get('error')}"}]
        return out
    if chain:
        f.append({"level": "info", "code": "redirect", "text": f"{len(chain)} redirecionamento(s) até {final}"})
    if status != 200:
        f.append({"level": "erro", "code": "status", "text": f"respondeu {status}, não 200"})
    xrobots = headers.get("X-Robots-Tag")
    ctype = headers.get("Content-Type", "")
    out["x_robots_tag"] = xrobots
    if "html" not in ctype:
        out["content_type"] = ctype
        f.append({"level": "aviso", "code": "not-html", "text": f"não é HTML ({ctype})"})
        out["findings"] = f
        return out

    p = Page()
    p.feed(decode(body, headers))
    title = " ".join((p.title or "").split()) or None
    desc = meta_value(p, "description")
    robots = meta_value(p, "robots")
    canonical = next((l.get("href") for l in p.links if "canonical" in l.get("rel", "").lower().split()), None)
    if canonical:
        canonical = urllib.parse.urljoin(final, canonical)
    hreflang = [{"lang": l.get("hreflang"), "href": l.get("href")} for l in p.links
                if "alternate" in l.get("rel", "").lower().split() and l.get("hreflang")]
    types, bad_jsonld = jsonld_types(p.jsonld)
    og = {k: meta_value(p, f"og:{k}") for k in ("title", "description", "image", "url", "type")}
    out.update({
        "title": title, "title_len": len(title) if title else 0,
        "description": desc, "description_len": len(desc) if desc else 0,
        "canonical": canonical, "robots": robots, "lang": p.lang,
        "viewport": meta_value(p, "viewport"), "h1": p.h1, "hreflang": hreflang,
        "open_graph": og, "twitter_card": meta_value(p, "twitter:card"),
        "jsonld_types": types, "images": p.imgs, "images_without_alt": p.imgs_no_alt, "words": p.words,
    })

    noindex = any("noindex" in (v or "").lower() for v in (robots, xrobots))
    if noindex:
        f.append({"level": "erro", "code": "noindex", "text": "noindex: o Google não põe esta página no índice"})
    if not title:
        f.append({"level": "erro", "code": "title-missing", "text": "sem <title>"})
    elif len(title) > TITLE_MAX:
        f.append({"level": "aviso", "code": "title-long",
                  "text": f"título com {len(title)} caracteres; acima de ~{TITLE_MAX} costuma ser cortado (heurística)"})
    if not desc:
        f.append({"level": "aviso", "code": "description-missing",
                  "text": "sem meta description; o Google monta o trecho do texto da página"})
    elif len(desc) > DESC_MAX:
        f.append({"level": "aviso", "code": "description-long",
                  "text": f"descrição com {len(desc)} caracteres; acima de ~{DESC_MAX} costuma ser cortada (heurística)"})
    if not canonical:
        f.append({"level": "aviso", "code": "canonical-missing", "text": "sem link canonical"})
    elif norm(canonical) != norm(final):
        c_status, c_final, _, _, c_chain = fetch(canonical)  # one extra GET, only when the canonical is elsewhere
        out["canonical_final"] = c_final
        if c_chain and norm(c_final) == norm(final):
            f.append({"level": "erro", "code": "canonical-loop",
                      "text": f"o canonical aponta para {canonical}, que redireciona de volta para esta página: "
                              "o Google recebe dois sinais contrários sobre qual é a URL oficial"})
        elif c_status != 200:
            f.append({"level": "erro", "code": "canonical-broken",
                      "text": f"o canonical aponta para {canonical}, que {said(c_status, c_chain)}"})
        else:
            f.append({"level": "aviso", "code": "canonical-other",
                      "text": f"o canonical aponta para outra URL ({canonical}); esta não é a versão indexada"})
    if not p.h1:
        f.append({"level": "aviso", "code": "h1-missing", "text": "sem <h1> no HTML"})
    elif len(p.h1) > 1:
        f.append({"level": "info", "code": "h1-many", "text": f"{len(p.h1)} <h1>"})
    if not p.lang:
        f.append({"level": "aviso", "code": "lang-missing", "text": "sem lang no <html> (pt-BR)"})
    if not out["viewport"]:
        f.append({"level": "aviso", "code": "viewport-missing", "text": "sem meta viewport (celular)"})
    missing_og = [k for k in ("title", "description", "image") if not og[k]]
    if missing_og:
        f.append({"level": "aviso", "code": "og-missing",
                  "text": "sem og:" + ", og:".join(missing_og) + "; o link compartilhado no WhatsApp sai sem cartão"})
    if not types:
        f.append({"level": "info", "code": "jsonld-none",
                  "text": "sem JSON-LD no HTML (se ele é injetado por JavaScript, este script não vê; confira no Rich Results Test)"})
    if bad_jsonld:
        f.append({"level": "aviso", "code": "jsonld-invalid", "text": f"{bad_jsonld} bloco(s) JSON-LD que não são JSON válido"})
    if p.imgs_no_alt:
        f.append({"level": "info", "code": "img-alt", "text": f"{p.imgs_no_alt} de {p.imgs} imagens sem alt"})
    if p.words < THIN_WORDS:
        f.append({"level": "info", "code": "thin-html",
                  "text": f"{p.words} palavras no HTML; se o conteúdo monta em JavaScript, o Google precisa renderizar para ver"})
    out["findings"] = f
    return out


# ---- sitemap ----

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def robots_sitemaps(base: str):
    status, final, headers, body, _ = fetch(urllib.parse.urljoin(base, "/robots.txt"))
    if status != 200:
        return status, []
    lines = decode(body, headers).splitlines()
    return status, [l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("sitemap:")]


def read_sitemap(url: str, out: dict, depth: int = 0):
    if url in out["_seen"]:  # an index that lists itself, or two indexes listing the same sitemap
        return
    out["_seen"].add(url)
    status, final, headers, body, chain = fetch(url)
    entry = {"url": url, "final_url": final, "status": status}
    if status is None:
        entry["said"] = said(status, chain)
    out["sitemaps"].append(entry)
    if status != 200:
        return
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        entry["error"] = f"XML inválido: {e}"
        return
    tag = root.tag.split("}")[-1]
    entry["kind"] = tag
    if tag == "sitemapindex":
        for sm in root.findall("s:sitemap", NS):
            loc = (sm.findtext("s:loc", default="", namespaces=NS) or "").strip()
            if loc and depth < 3:
                read_sitemap(loc, out, depth + 1)
    elif tag == "urlset":
        n = 0
        for u in root.findall("s:url", NS):
            loc = (u.findtext("s:loc", default="", namespaces=NS) or "").strip()
            if loc:
                n += 1
                out["urls"].append({"loc": loc, "lastmod": u.findtext("s:lastmod", default=None, namespaces=NS),
                                    "sitemap": final})
        entry["urls"] = n


def audit_sitemap(target: str, check: bool, max_urls: int) -> dict:
    if not re.match(r"https?://", target):
        target = "https://" + target
    parts = urllib.parse.urlsplit(target)
    base = f"{parts.scheme}://{parts.netloc}/"
    trust(base)
    out = {"site": base, "robots_status": None, "robots_sitemaps": [], "sitemaps": [], "urls": [], "findings": [],
           "_seen": set()}
    f = out["findings"]
    out["robots_status"], out["robots_sitemaps"] = robots_sitemaps(base)
    if parts.path.endswith(".xml"):
        starts = [target]
    elif out["robots_sitemaps"]:
        starts = out["robots_sitemaps"]
    else:
        starts = [urllib.parse.urljoin(base, "/sitemap.xml")]
        f.append({"level": "aviso", "code": "robots-no-sitemap",
                  "text": "o robots.txt não declara Sitemap:; tentei /sitemap.xml"})
    for s in starts:
        read_sitemap(s, out)
    other_hosts = set()
    for sm in out["sitemaps"]:
        if sm["status"] != 200:
            f.append({"level": "erro", "code": "sitemap-status", "text": f"{sm['url']} {sm.get('said') or 'respondeu ' + str(sm['status'])}"})
        elif sm.get("error"):
            f.append({"level": "erro", "code": "sitemap-xml", "text": f"{sm['url']}: {sm['error']}"})
        host = urllib.parse.urlsplit(sm["final_url"]).netloc
        if host and host != parts.netloc and host not in other_hosts:
            other_hosts.add(host)
            f.append({"level": "aviso", "code": "sitemap-other-host",
                      "text": f"{sm['url']} termina em outro host ({host}); o Google só aceita sitemap de outro host "
                              "declarado no robots.txt ou com os dois sites verificados no Search Console"})
    hosts = {urllib.parse.urlsplit(u["loc"]).netloc for u in out["urls"]}
    out["url_hosts"] = sorted(hosts)
    if not out["urls"]:
        f.append({"level": "erro", "code": "sitemap-empty", "text": "nenhuma URL nos sitemaps lidos"})
    if check:
        checked, redirected = [], []
        for u in out["urls"][:max_urls]:
            status, final, headers, _, chain = fetch(u["loc"])
            u.update({"status": status, "final_url": final, "x_robots_tag": headers.get("X-Robots-Tag") if headers else None})
            checked.append(u)
            if status != 200:
                f.append({"level": "erro", "code": "url-status", "text": f"{u['loc']} {said(status, chain)}"})
            elif chain:
                redirected.append(u)
            if u["x_robots_tag"] and "noindex" in u["x_robots_tag"].lower():
                f.append({"level": "erro", "code": "url-noindex", "text": f"{u['loc']} tem X-Robots-Tag noindex"})
            time.sleep(0.1)
        if redirected:  # one finding, not one per URL: a whole sitemap often redirects for the same reason
            ex = "; ".join(f"{u['loc']} → {u['final_url']}" for u in redirected[:3])
            f.append({"level": "aviso", "code": "url-redirect", "count": len(redirected),
                      "text": f"{len(redirected)} de {len(checked)} URLs do sitemap redirecionam; o sitemap deve listar "
                              f"a URL final (canonical). Ex.: {ex}"})
        out["checked"] = len(checked)
        if len(out["urls"]) > max_urls:
            f.append({"level": "info", "code": "check-limit", "text": f"conferi {max_urls} de {len(out['urls'])} URLs (--max)"})
    out["total_urls"] = len(out["urls"])
    del out["_seen"]
    return out


def main():
    ap = argparse.ArgumentParser(prog="seo-audit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pg = sub.add_parser("page")
    pg.add_argument("urls", nargs="+")
    sm = sub.add_parser("sitemap")
    sm.add_argument("target")
    sm.add_argument("--check", action="store_true", help="GET every URL and report status, redirects, noindex")
    sm.add_argument("--max", type=int, default=200)
    a = ap.parse_args()
    if a.cmd == "page":
        urls = [trust(u if re.match(r"[a-z][a-z0-9+.-]*://", u) else "https://" + u) for u in a.urls]
        res = {"pages": [audit_page(u) for u in urls]}
    else:
        res = audit_sitemap(a.target, a.check, a.max)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
