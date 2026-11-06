# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client==2.187.0", "google-auth==2.43.0"]
# ///
"""Google Search Console, read-only, through a service account: sites, search analytics, sitemaps, URL inspection.

    gsc.sh sites
    gsc.sh query  [--site S] [--days 28] [--by query|page|date|country|device] [--limit 25] [--filter page~/blog]
    gsc.sh sitemaps [--site S]
    gsc.sh inspect <url> [--site S]

The key is a service-account JSON (`GSC_KEY`, default ~/.config/biliboss/via-ads-gsc.json) with the
`webmasters.readonly` scope; the account must be a user of the property in Search Console. The site is `--site` or
`GSC_SITE` (a domain property is `sc-domain:example.com`). Output is one JSON document on stdout; errors go to stderr
with exit 1. Search Console data lags about two days, so the window ends two days ago.
"""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DEFAULT_KEY = Path.home() / ".config/biliboss/via-ads-gsc.json"


def service():
    key = Path(os.environ.get("GSC_KEY") or DEFAULT_KEY).expanduser()
    if not key.is_file():
        sys.exit(f"gsc: no key at {key} (set GSC_KEY)")
    creds = service_account.Credentials.from_service_account_file(str(key), scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def site_of(a) -> str:
    site = a.site or os.environ.get("GSC_SITE")
    if not site:
        sys.exit("gsc: no site (pass --site or set GSC_SITE; a domain property is sc-domain:<domain>)")
    return site


def cmd_sites(svc, a):
    return svc.sites().list().execute().get("siteEntry", [])


def cmd_query(svc, a):
    end = dt.date.today() - dt.timedelta(days=2)
    start = end - dt.timedelta(days=a.days - 1)
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": [a.by], "rowLimit": a.limit}
    if a.filter:  # "page~/blog" (contains) or "query=imóvel" (equals); the first ~ or = splits
        if "~" not in a.filter and "=" not in a.filter:
            sys.exit("gsc: --filter is <dimension>~<text> (contains) or <dimension>=<text> (equals)")
        op = min((c for c in "~=" if c in a.filter), key=a.filter.index)
        dim, expr = a.filter.split(op, 1)
        body["dimensionFilterGroups"] = [{"filters": [
            {"dimension": dim, "operator": "contains" if op == "~" else "equals", "expression": expr}]}]
    rows = svc.searchanalytics().query(siteUrl=site_of(a), body=body).execute().get("rows", [])
    return {"site": site_of(a), "from": body["startDate"], "to": body["endDate"], "by": a.by, "rows": [
        {a.by: r["keys"][0], "clicks": r["clicks"], "impressions": r["impressions"],
         "ctr": round(r["ctr"], 4), "position": round(r["position"], 1)} for r in rows]}


def cmd_sitemaps(svc, a):
    return svc.sitemaps().list(siteUrl=site_of(a)).execute().get("sitemap", [])


def cmd_inspect(svc, a):
    body = {"inspectionUrl": a.url, "siteUrl": site_of(a)}
    return svc.urlInspection().index().inspect(body=body).execute().get("inspectionResult", {})


def main() -> int:
    ap = argparse.ArgumentParser(description="Google Search Console, read-only")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sites")
    q = sub.add_parser("query")
    q.add_argument("--days", type=int, default=28)
    q.add_argument("--by", default="query", choices=["query", "page", "date", "country", "device"])
    q.add_argument("--limit", type=int, default=25)
    q.add_argument("--filter")
    sm = sub.add_parser("sitemaps")
    ins = sub.add_parser("inspect")
    ins.add_argument("url")
    for p in (q, sm, ins):
        p.add_argument("--site")
    a = ap.parse_args()
    try:
        out = {"sites": cmd_sites, "query": cmd_query, "sitemaps": cmd_sitemaps, "inspect": cmd_inspect}[a.cmd](service(), a)
    except HttpError as e:
        print(f"gsc: {e.status_code} {e.reason}", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
