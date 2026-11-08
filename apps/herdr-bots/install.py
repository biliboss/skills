#!/usr/bin/env python3
"""Install a private layout and optionally prepare one empty, registered bot."""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1] / 'skills/bili-agents'
spec = importlib.util.spec_from_file_location('bots', SKILL / 'scripts/bots.py')
bots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bots)


def write(path, data):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    os.replace(temp, path)


def find(node, ident):
    if node.get('id') == ident:
        return node
    for child in node.get('children', []):
        result = find(child, ident)
        if result:
            return result


def prepare(bot):
    folder = Path(bot['folder']).expanduser()
    expected = {'AGENTS.md': '', 'CLAUDE.md': '@AGENTS.md\n', '.claude/settings.json': '{}\n'}
    # A marker belongs to the installation, never to the old agent folder.
    marker = bots.HOME / '.bot-state' / (bots.identity(bot) + '.prepared')
    if marker.exists():
        if not folder.is_dir():
            raise RuntimeError('prepared bot folder is missing; refusing to recreate it')
        return
    # Check all local cwd records, including processes outside Herdr. Failure to inspect blocks preparation.
    result = subprocess.run(['lsof', '-d', 'cwd', '-Fn'], text=True, capture_output=True)
    if result.returncode not in (0, 1) or not result.stdout:
        raise RuntimeError('cannot inspect local working directories; bot preparation stopped')
    target = str(folder.resolve())
    for line in result.stdout.splitlines():
        if line.startswith('n') and (line[1:] == target or line[1:].startswith(target + '/')):
            raise RuntimeError(f'active process uses {folder}; bot preparation stopped, session untouched')
    for entry in bots.call(['hc', 'ls'])['terminals']:
        cwd = entry.get('cwd', '')
        if entry.get('state') == 'live' and (cwd == target or cwd.startswith(target + '/')):
            raise RuntimeError(f"live terminal {entry['address']} uses {folder}; preparation stopped")
    if folder.is_symlink():
        raise RuntimeError('bot folder is a symlink; refusing to move it')
    if folder.exists():
        backup = folder.with_name(folder.name + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        folder.rename(backup)
        print(f'Preserved old folder intact: {backup}')
    folder.mkdir(parents=True)
    for name, text in expected.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(folder) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bot', nargs=4, metavar=('ID', 'NAME', 'FOLDER', 'UUID'))
    parser.add_argument('--command', default='["claude"]', help='JSON argv; session flags supplied by launcher')
    args = parser.parse_args()
    bots.HOME.mkdir(parents=True, exist_ok=True)
    if args.bot:
        ident, name, folder, session = args.bot
        bot = dict(id=ident, name=name, folder=folder, session_id=session, command=json.loads(args.command))
        existing = bots.registry() if bots.REGISTRY.exists() else []
        if any(b['id'] == ident and b != bot for b in existing):
            raise ValueError('bot already registered with different settings; edit registry explicitly')
        proposed = existing if any(b['id'] == ident for b in existing) else [*existing, bot]
        # Validate without changing an existing registry or instance.
        old = bots.REGISTRY
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / 'bots.json'
            write(candidate, {'bots': proposed})
            bots.REGISTRY = candidate
            bots.registry()
            bots.REGISTRY = old
        bots.ready({**bot, 'folder': str(bots.HOME)})
        prepare(bot)
        write(bots.REGISTRY, {'bots': proposed})
    registered = bots.registry()
    app = Path(os.environ.get('HERDR_APP_HOME', Path.home() / '.config/herdr-app'))
    source = bots.call(['herdr-app', 'status'])['layout']
    # Reuse our private layout on reinstall; never edit a shipped layout.
    destination = 'bili-bots'
    path = app / 'layouts' / (destination + '.json')
    if not path.exists():
        bots.call(['herdr-app', 'do', 'layout.clone', json.dumps({'name': source, 'as': destination})])
    layout = json.loads(path.read_text())
    sidebar = find(layout, 'sidebar')
    if not sidebar or not any(c.get('id') == 'brand' for c in sidebar.get('children', [])):
        raise ValueError('active layout needs a sidebar with a brand block; cloned layout left for inspection')
    node = find(layout, 'bili-bots')
    if node is None:
        node = {'id': 'bili-bots', 'type': 'block', 'size': {'px': 104}, 'content': {}}
        index = next(i for i, child in enumerate(sidebar['children']) if child.get('id') == 'brand')
        sidebar['children'].insert(index + 1, node)
    spaces_node = find(layout, 'spaces')
    if not spaces_node:
        raise ValueError('layout needs a Spaces block')
    spaces_mod = app / 'mods/bili-bot-spaces'
    if not spaces_mod.exists():
        original = spaces_node['content']['mod']
        bots.call(['herdr-app', 'do', 'mod.clone', json.dumps({'name': original, 'as': 'bili-bot-spaces'})])
        source = spaces_mod / 'main.js'
        text = source.read_text()
        if 'import { spaces,' not in text:
            raise ValueError('unsupported Spaces mod; cannot hide bot workspaces safely')
        text = text.replace('import { spaces,', 'import { spaces as allSpaces,', 1)
        text += '\nfunction spaces() { return allSpaces().filter(space => !(shared("bili.botSpaces") ?? []).includes(space.id)); }\n'
        source.write_text(text)
    # Number Bots first, then visible Spaces; one navigation handler owns the order.
    spaces_source = spaces_mod / 'main.js'
    text = spaces_source.read_text()
    if '// bili-bots navigation hints' not in text:
        text += '\n// bili-bots navigation hints\nfunction botShortcut(id) { const n = (shared("bili.botSpaces") ?? []).length + spaces().findIndex(s => s.id === id) + 1; return shared("bili.optionHints") && n > 0 && n <= 9 ? `⌥${n}` : ""; }\n'
        text = text.replace('.child(g ? this.gitTail(g, tree, w.name, t) : div().flex_1()),', '.child(g ? this.gitTail(g, tree, w.name, t) : div().flex_1())\n          .child(div().flex_none().text_size(11).text_color(t.dim).child(botShortcut(w.id))),', 1)
        text = text.replace('.child(String(i + 1))', '.child(botShortcut(w.id) || String(i + 1))', 1)
        spaces_source.write_text(text)
    text = spaces_source.read_text().replace('return n > 0 && n <= 9 ? `⌥${n}` : "";', 'return shared("bili.optionHints") && n > 0 && n <= 9 ? `⌥${n}` : "";')
    spaces_source.write_text(text)
    keys_path = app / 'keys.json'
    keys = json.loads(keys_path.read_text())
    bindings = keys.setdefault('layout:bili-bots', {})
    for number in range(1, 10):
        bindings[f'alt-{number}'] = f'herdr-bots.select-{number}'
    write(keys_path, keys)
    subprocess.run(['herdr-app', 'check', str(spaces_mod)], check=True)
    spaces_node['content']['mod'] = 'bili-bot-spaces'
    node['size'] = {'px': min(240, 40 + 35 * len(registered))}
    node['content'] = {'mod': 'herdr-bots', 'props': {'opener': str(SKILL / 'scripts/ag-open'), 'registry': str(bots.REGISTRY), 'dataHome': str(bots.HOME)}}
    mod = app / 'mods/herdr-bots'
    mod.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'darwin':
        helper = mod / 'option-state'
        temporary = mod / 'option-state.new'
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        subprocess.run(['xcrun', 'clang', '-isysroot', sdk, '-O2', str(HERE / 'option-state.c'), '-framework', 'ApplicationServices', '-o', str(temporary)], check=True)
        os.replace(temporary, helper)
        node['content']['props']['optionState'] = str(helper)
    for name in ('main.js', 'mod.json'):
        shutil.copy2(HERE / name, mod / name)
    subprocess.run(['herdr-app', 'check', str(mod)], check=True)
    write(path, layout)
    bots.call(['herdr-app', 'do', 'layout.switch', json.dumps({'name': destination})])
    print('Installed Bots in layout bili-bots')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Bots installation: {error}', file=sys.stderr)
        sys.exit(1)
