"""The console's atoms (Atomic Design): the smallest pieces every widget is built from, so a title or an empty state is
written once. dev-console.py loads this as a sibling; a project imports it (`from console_atoms import title, empty`)
after appending skills/dev-console/scripts to sys.path. See references/atomic-design.md."""
from __future__ import annotations

import fasthtml.common as ft  # tags read at call time: a test may stub fasthtml with only some of them

TITLE_CLS = "mb-3 font-sans text-base font-semibold text-neutral-900 dark:text-neutral-100"
MUTED_CLS = "text-neutral-400"


def title(text: str):
    """Every widget starts with its title (in a module or a sidebar part the console hides it: the line names it)."""
    return ft.H2(text, cls=TITLE_CLS)


def empty(text: str, cls: str = ""):
    """The empty state: one muted line saying what is missing."""
    return ft.P(text, cls=f"{cls} {MUTED_CLS}".strip())
