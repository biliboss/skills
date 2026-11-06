"""Hot reload of what a project imports: the project file is not the only code a domain runs.

A project puts its own folder on sys.path (`from kanban import ...`) and may load a sibling skill's module by path
(kanban -> cost-track's costs.py). Two rules keep the console from serving stale code:
  - `purge(folders)` drops every cached module whose file is inside those folders, so the next import reads the file;
  - `watch_dirs(...)` lists the folders the watcher must follow: the projects', the ones they added to sys.path, the
    folders of the modules they loaded, and what a project names in `WATCH` (paths relative to its own folder).
"""
from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

_SKIP = tuple(str(Path(p).resolve()) for p in {sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["purelib"],
                                              sysconfig.get_paths()["platlib"], sys.prefix, sys.base_prefix})


def _foreign(path: Path) -> bool:
    """True for the stdlib, site-packages and the interpreter's own folders: not ours to watch or purge."""
    s = str(path.resolve())
    return "site-packages" in s or any(s == k or s.startswith(k + "/") for k in _SKIP)


def _inside(path: Path, folders) -> bool:
    return any(path == f or f in path.parents for f in folders)


def purge(folders, keep=()) -> list[str]:
    """Remove from sys.modules the modules defined in `folders` (except names in `keep`); returns the names dropped."""
    folders = [Path(f).resolve() for f in folders]
    dropped = []
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if name in keep or not file:
            continue
        p = Path(file).resolve()
        if not _foreign(p) and _inside(p, folders):
            del sys.modules[name]
            dropped.append(name)
    return dropped


def watch_dirs(projects, modules=None, extra_paths=()) -> set[Path]:
    """The folders to watch: each project's, `extra_paths` (what loading them added to sys.path), the folders of the
    loaded non-library modules under the projects' common ancestor, and each project's `WATCH` list."""
    out = {Path(p).resolve().parent for p in projects}
    out |= {Path(p).resolve() for p in extra_paths if Path(p).is_dir() and not _foreign(Path(p))}
    for mod in (modules if modules is not None else sys.modules).values():
        file = getattr(mod, "__file__", None)
        if file and Path(file).exists() and not _foreign(Path(file)) and ".hermes" not in Path(file).parts[-6:-1]:
            out.add(Path(file).resolve().parent)
    return {d for d in out if d.is_dir() and d != Path.home() and d != Path("/")}
