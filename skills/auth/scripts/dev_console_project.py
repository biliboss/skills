"""Auth in the dev-console: the agent's secure identity, accounts per provider (design stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from auth import TRANSITIONS, AuthJournal  # noqa: E402,F401
from fasthtml.common import Div, P, Span  # noqa: E402

NAME = "Biliboss Skills - Auth"
SLUG = "auth"
SOURCE = Path(__file__).parent / "auth.py"  # the file with EVENTS
ENTITY = "Account"
ENTITY_PLURAL = "contas"
ENTITIES = {"provider": "Provider", "account": "Account"}
ENTITY_KEY = "account"
PROJECTOR = "_project"
COST_CENTER = "biliboss-skills"

journal = AuthJournal()

# The owner (or the agent for him) sets up a provider: its OAuth client goes into envless.
INITIAL = ["provider.updated"]

BORDO = "#7a1f2b"  # the only colour: what needs the owner
MARKS = {"ok": ("●", "ok", False), "needs_login": ("◆", "precisa de login", True), "broken": ("✗", "quebrada", True)}


def title_of(history: list[dict], state: dict) -> str:
    return state.get("alias") or state.get("id", "")


def contas(ctx):
    """Every account, one line each: provider · alias · email · state; burgundy only for what needs the owner."""
    rows = sorted(ctx.entities, key=lambda s: (s.get("provider", ""), s.get("alias", "")))
    if not rows:
        return Div(P("Contas", cls="font-sans text-lg font-semibold"), P("Nenhuma conta ainda.", cls="text-neutral-400"))
    lines = []
    for s in rows:
        glyph, text, owner = MARKS.get(s.get("status", "needs_login"), MARKS["broken"])
        lines.append(Div(
            Span(s.get("provider", ""), cls="w-16 shrink-0 text-neutral-400"),
            Span(s.get("alias", ""), cls="w-24 shrink-0 font-semibold text-neutral-900 dark:text-neutral-100"),
            Span(s.get("email", ""), cls="min-w-0 flex-1 truncate text-neutral-500"),
            Span(f"{glyph} {text}", cls="shrink-0", style=f"color:{BORDO}" if owner else "color:#9a9a9a"),
            cls="flex gap-3 py-1 font-mono text-sm"))
    return Div(P("Contas", cls="font-sans text-lg font-semibold text-neutral-900 dark:text-neutral-100"),
               Div(*lines, cls="mt-2"), data_contas="1")


BW_FILE = Path("~/.local/state/auth/bitwarden.json").expanduser()  # bw.sh sync: logins' metadata, never a password


def cofre(ctx):
    """The owner's Bitwarden vault (bw.sh): locked -> one burgundy line with the command; unlocked -> the logins, one
    line each (host · name · user · 2FA), burgundy only for what needs him (no 2FA, a reused password)."""
    import json
    try:
        data = json.loads(BW_FILE.read_text())
    except (OSError, ValueError):
        data = {"status": {"status": "unknown"}, "items": []}
    st = data.get("status") or {}
    head = P("Cofre", Span(f" Bitwarden · {st.get('email') or ''}", cls="text-sm font-normal text-neutral-400"),
             cls="font-sans text-lg font-semibold text-neutral-900 dark:text-neutral-100")
    if st.get("status") != "unlocked" or not data.get("items"):
        return Div(head, Div(Span("◆ bloqueado", style=f"color:{BORDO}", cls="shrink-0"),
                             Span("desbloqueie no terminal: ~/src/skills/skills/auth/scripts/bw.sh unlock",
                                  cls="text-neutral-500"), cls="mt-2 flex gap-3 font-mono text-sm"),
                   cls="mt-8", data_cofre="locked")
    items = sorted(data["items"], key=lambda i: (i.get("host") or "~", i.get("name", "")))
    no2fa = sum(1 for i in items if not i.get("totp"))
    reused = sum(1 for i in items if i.get("reused"))
    lines = []
    for i in items:
        warn = [w for w, on in (("sem 2FA", not i.get("totp")), ("senha repetida", i.get("reused"))) if on]
        lines.append(Div(
            Span(i.get("host") or "—", cls="w-48 shrink-0 truncate text-neutral-400"),
            Span(i.get("name", ""), cls="w-48 shrink-0 truncate font-semibold text-neutral-900 dark:text-neutral-100"),
            Span(i.get("user", ""), cls="min-w-0 flex-1 truncate text-neutral-500"),
            Span(" · ".join(warn) or "● 2FA", cls="shrink-0", style=f"color:{BORDO}" if warn else "color:#9a9a9a"),
            cls="flex gap-3 py-0.5 font-mono text-sm"))
    summary = P(f"{len(items)} logins · {no2fa} sem 2FA · {reused} com senha repetida", cls="mt-1 text-sm text-neutral-500")
    return Div(head, summary, Div(*lines, cls="mt-2"), cls="mt-8", data_cofre="unlocked")


def contas_e_cofre(ctx):
    return Div(contas(ctx), cofre(ctx))


WIDGETS = {"account.updated": [contas_e_cofre], "account.checked": [contas_e_cofre], "account.connected": [contas_e_cofre]}
HOME = ("account.updated", "Contas")
