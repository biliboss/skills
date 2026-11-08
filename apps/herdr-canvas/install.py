#!/usr/bin/env python3
"""Install the Canvas mod: copy files, add the panel child to two layouts, add one key, run `herdr-app check`.

It only touches files. It never talks to the running Herdr (it sends no command that switches, opens, shows or
clones a layout or mod), so installing cannot move the owner's focus. The mod loads when the panel is first opened
or on restart.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
MOD_FILES = ('main.js', 'blocks.js', 'store.js', 'notify.js', 'mod.json', 'canvas.svg')
LAYOUTS = ('main', 'bili-bots')
KEY = ('layout:bili-bots', 'cmd-alt-c', 'mod.open:herdr-canvas')
STAMP = datetime.now().strftime('%Y%m%d-%H%M%S')


def app_home():
    env = os.environ.get('HERDR_APP_HOME')
    if env:
        return Path(env).expanduser(), 'HERDR_APP_HOME'
    return Path.home() / '.config/herdr-app', 'default (HERDR_APP_HOME unset)'


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-check', action='store_true', help='skip herdr-app check (tests)')
    args = parser.parse_args()
    app, origin = app_home()
    print(f'Destination: {app} ({origin})')
    if not app.is_dir():
        raise ValueError(f'{app} does not exist')
    mod = app / 'mods/herdr-canvas'
    mod.mkdir(parents=True, exist_ok=True)
    for name in MOD_FILES:
        shutil.copy2(HERE / 'mod' / name, mod / name)
    print(f'Copied mod to {mod}')
    if not args.no_check:
        subprocess.run(['herdr-app', 'check', str(mod)], check=True)
    for name in LAYOUTS:
        path = app / 'layouts' / f'{name}.json'
        if not path.exists():
            print(f'Layout {name}: absent, skipped')
            continue
        layout = patch_layout(path)
        if layout is None:
            print(f'Layout {name}: already has canvas')
            continue
        print(f'Layout {name}: backup {backup(path).name}')
        write_json(path, layout)
    keys_path = app / 'keys.json'
    if keys_path.exists():
        keys = json.loads(keys_path.read_text())
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
