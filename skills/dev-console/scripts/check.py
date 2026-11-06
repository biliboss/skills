# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.54.0"]
# ///
"""Headless check of one console page, for a harness without a browser tool of its own (Claude Code, pi).

It drives the Chrome already installed on the Mac (playwright's `channel="chrome"`), so nothing is downloaded but the
playwright wheel, and it never borrows another project's node_modules. One JSON object on stdout: the page title, the
HTTP status, every console error and page error, the value of `--eval`, and the screenshot path.

    check.sh <url> [--shot out.png] [--width 1000] [--height 800] [--light] [--wait 1500] [--eval '<js expression>']

It prints the page's own text only through `--eval`: keep private text (the Agents module's prompts) out of it.
"""
import argparse
import json
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--shot", help="screenshot path (png)")
    ap.add_argument("--width", type=int, default=1000)  # the owner's console width
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--light", action="store_true", help="light mode (default dark, as he uses it)")
    ap.add_argument("--wait", type=int, default=1500, help="ms after load, for scripts and SSE to settle")
    ap.add_argument("--eval", dest="js", help="a JS expression whose value is returned (JSON-serialisable)")
    a = ap.parse_args()
    out: dict = {"url": a.url, "errors": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": a.width, "height": a.height},
                                color_scheme="light" if a.light else "dark")
        page.on("pageerror", lambda e: out["errors"].append(f"pageerror: {e}"))
        page.on("console", lambda m: m.type == "error" and out["errors"].append(f"console: {m.text}"))
        try:  # a refused connection or a bad --eval is still one JSON line, never a traceback
            resp = page.goto(a.url, wait_until="domcontentloaded")
            page.wait_for_timeout(a.wait)
            out["status"] = resp.status if resp else None
            out["title"] = page.title()
            if a.js:
                out["eval"] = page.evaluate(a.js)
            if a.shot:
                page.screenshot(path=a.shot)
                out["shot"] = a.shot
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"check: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
        finally:
            browser.close()
    print(json.dumps(out, ensure_ascii=False))
    return 1 if out["errors"] or (out["status"] or 0) >= 400 else 0


if __name__ == "__main__":
    sys.exit(main())
