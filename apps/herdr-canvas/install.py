#!/usr/bin/env python3
"""Install the Canvas mod into the Herdr config folder named by HERDR_APP_HOME (required).

Copies the mod, adds the `canvas` child to the `panel-body` stack of layouts `main` and `bili-bots`, patches
mods/tabs/main.js so the right panel gets a Canvas button next to Browser, adds one key, runs `herdr-app check`.
Everything is validated before anything is written; each edited file gets a `*.bak-canvas-<stamp>` backup.

It only touches files. It never talks to the running Herdr (it sends no command that switches, opens, shows or
clones a layout or mod), so installing cannot move the owner's focus. The mod loads when the panel is first opened
or on restart.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
MOD_FILES = ('main.js', 'blocks.js', 'store.js', 'notify.js', 'pagemode.js', 'mod.json', 'canvas.svg')
LAYOUTS = ('main', 'bili-bots')
KEY = ('layout:bili-bots', 'cmd-alt-c', 'mod.open:herdr-canvas')
STAMP = datetime.now().strftime('%Y%m%d-%H%M%S')

PANELS_ORIGINAL = 'shared("workspace.panels") ?? ["files", "changes"];'
CANVAS_BUTTON = '.child(panelButton("canvas", "Canvas", "mods/herdr-canvas/canvas.svg"))'
BROWSER_BUTTON = '.child(panelButton("browser", "Browser", "mods/tabs/globe.svg"))'
CHANGES_BUTTON = 'panelButton("changes", "Changes", "mods/changes/changes.svg")))'


def app_home():
    env = os.environ.get('HERDR_APP_HOME')
    if not env:
        raise ValueError('HERDR_APP_HOME is not set. Name the Herdr config folder explicitly, e.g. '
                         'HERDR_APP_HOME=~/.config/herdr-bili ./install.sh (there is no default; it used to be the official home)')
    return Path(env).expanduser()


def write_json(path, data):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    os.replace(temp, path)


def backup(path):
    target = path.with_name(f'{path.name}.bak-canvas-{STAMP}')
    shutil.copy2(path, target)
    return target


def find(node, ident):
    if node.get('id') == ident:
        return node
    for child in node.get('children', []):
        found = find(child, ident)
        if found:
            return found


def patch_layout(path):
    layout = json.loads(path.read_text())
    body = find(layout, 'panel-body')
    if not body or body.get('type') != 'stack':
        raise ValueError(f'{path.name}: no stack panel-body; layout left untouched')
    if find(body, 'canvas'):
        return None
    body.setdefault('children', []).append({'id': 'canvas', 'type': 'block', 'content': {'mod': 'herdr-canvas'}})
    return layout


def patch_tabs(text):
    """Returns the patched mods/tabs/main.js text, or None when it already has the Canvas button.

    Same shape as the Browser patch: "canvas" joins the enabled panels, and a panelButton goes after the
    Browser button (or after Changes when there is no Browser button). Raises when an anchor is missing.
    """
    has_enabled, has_button = 'enabled = ' in text and '"canvas"]' in text, CANVAS_BUTTON in text
    if has_enabled and has_button:
        return None
    if has_enabled != has_button:
        raise ValueError('mods/tabs/main.js: Canvas is half applied (enabled list and button disagree); fix it by hand')
    with_browser = re.compile(r"(const enabled = \[\.\.\.\(.*\), \"browser\")\];")
    if with_browser.search(text):
        text = with_browser.sub(r'\1, "canvas"];', text, count=1)
    elif f'const enabled = {PANELS_ORIGINAL}' in text:
        text = text.replace(f'const enabled = {PANELS_ORIGINAL}', f'const enabled = [...({PANELS_ORIGINAL[:-1]}), "canvas"];', 1)
    else:
        raise ValueError('mods/tabs/main.js: anchor `const enabled = shared("workspace.panels") ...` not found; file left untouched')
    lines = text.split('\n')
    for anchor in (BROWSER_BUTTON, CHANGES_BUTTON):
        for i, line in enumerate(lines):
            if anchor in line:
                indent = line[:len(line) - len(line.lstrip())]
                lines.insert(i + 1, indent + CANVAS_BUTTON)
                return '\n'.join(lines)
    raise ValueError('mods/tabs/main.js: no panelButton("browser"...) or panelButton("changes"...) line to put the Canvas button after; file left untouched')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-check', action='store_true', help='skip herdr-app check (tests)')
    parser.add_argument('--skip-tabs', action='store_true', help='do not patch mods/tabs/main.js (a home without that tab bar)')
    args = parser.parse_args()
    app = app_home()
    print(f'Destination: {app} (HERDR_APP_HOME)')
    if not app.is_dir():
        raise ValueError(f'{app} does not exist')

    # Plan: read and validate everything first; nothing is written until all of it is sound.
    layouts = []
    for name in LAYOUTS:
        path = app / 'layouts' / f'{name}.json'
        if not path.exists():
            print(f'Layout {name}: absent, skipped')
            continue
        layouts.append((name, path, patch_layout(path)))
    tabs_path, tabs_text = app / 'mods/tabs/main.js', None
    if not args.skip_tabs:
        if not tabs_path.exists():
            raise ValueError(f'{tabs_path} not found; use --skip-tabs for a home without the tab bar (Canvas then opens only by key or `canvas open`)')
        tabs_text = patch_tabs(tabs_path.read_text())
    keys_path, keys = app / 'keys.json', None
    if keys_path.exists():
        keys = json.loads(keys_path.read_text())

    mod = app / 'mods/herdr-canvas'
    mod.mkdir(parents=True, exist_ok=True)
    for name in MOD_FILES:
        shutil.copy2(HERE / 'mod' / name, mod / name)
    print(f'Copied mod to {mod}')
    if not args.no_check:
        subprocess.run(['herdr-app', 'check', str(mod)], check=True)
    for name, path, layout in layouts:
        if layout is None:
            print(f'Layout {name}: already has canvas')
            continue
        print(f'Layout {name}: backup {backup(path).name}')
        write_json(path, layout)
    if args.skip_tabs:
        print('mods/tabs/main.js: skipped (--skip-tabs)')
    elif tabs_text is None:
        print('mods/tabs/main.js: already has the Canvas button')
    else:
        print(f'mods/tabs/main.js: backup {backup(tabs_path).name}')
        temp = tabs_path.with_name(tabs_path.name + '.tmp')
        temp.write_text(tabs_text)
        os.replace(temp, tabs_path)
    if keys is not None:
        section, chord, command = KEY
        if keys.get(section, {}).get(chord) != command:
            print(f'keys.json: backup {backup(keys_path).name}')
            keys.setdefault(section, {})[chord] = command
            write_json(keys_path, keys)
        else:
            print('keys.json: binding already present')
    print('Installed Canvas. It loads when the panel is first opened or Herdr restarts; nothing was opened or focused.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Canvas installation: {error}', file=sys.stderr)
        sys.exit(1)
