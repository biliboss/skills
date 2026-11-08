#!/usr/bin/env python3
"""Local bot registry and Herdr session operations (no injected agent settings)."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

HOME = Path(os.environ.get('AG_HOME', Path.home() / 'agents')).expanduser()
REGISTRY = Path(os.environ.get('AG_BOTS_FILE', HOME / 'bots.json'))


def call(argv):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(f'{argv[0]}: {result.stderr.strip() or result.stdout.strip()}')
    return json.loads(result.stdout)


def registry():
    data = json.loads(REGISTRY.read_text())
    bots = data['bots']
    if not isinstance(bots, list):
        raise ValueError('bots must be an array')
    ids, sessions = set(), set()
    for bot in bots:
        ident = bot['id']
        if not re.fullmatch(r'[a-z0-9_-]{1,32}', ident) or ident in ids:
            raise ValueError('bot ids must be unique: a-z, 0-9, _ or -')
        session = str(uuid.UUID(bot['session_id']))
        if session != bot['session_id'] or session in sessions:
            raise ValueError('session_id must be a unique canonical UUID')
        if not isinstance(bot['name'], str) or not bot['name'].strip():
            raise ValueError('name must not be empty')
        command = bot['command']
        if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
            raise ValueError('command must be a nonempty argv array')
        if any(x.split('=')[0] in ('--continue', '-c', '--resume', '-r', '--session-id', '--fork-session') for x in command):
            raise ValueError('session flags are managed by ag-bot-session')
        if not Path(bot['folder']).expanduser().is_absolute():
            raise ValueError('folder must be absolute (or start with ~)')
        ids.add(ident)
        sessions.add(session)
    return bots


def identity(bot):
    return 'bot-' + hashlib.sha256((bot['id'] + ':' + bot['session_id']).encode()).hexdigest()[:28]


def space_id(bot):
    return 'bot-' + str(uuid.uuid5(uuid.NAMESPACE_URL, bot['id'] + ':' + bot['session_id']))


def lock(bot, suffix):
    folder = HOME / '.bot-state'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle = (folder / (identity(bot) + suffix)).open('a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        handle.close()
        raise
    return handle


def ready(bot):
    if not Path(bot['folder']).expanduser().is_dir():
        raise ValueError(f"bot folder does not exist: {bot['folder']}")
    if not shutil.which(bot['command'][0]):
        raise ValueError(f"bot command is unavailable: {bot['command'][0]}")


def open_bot(bot):
    with lock(bot, '.open.lock'):
        entries = call(['hc', 'ls'])['terminals']
        layout = call(['herdr-app', 'ls'])
        shown = [t for s in layout['spaces'] for tab in s['tabs'] for t in tab['terminals']]
        found = []
        live_details = {}
        for entry in entries:
            if entry.get('state') != 'live':
                continue
            # The unique name exists from creation, before the wrapper adds labels.
            if entry.get('name') == identity(bot):
                found.append(entry['address'])
                continue
            detail = call(['hc', 'get', entry['address']])
            live_details[entry['address']] = detail
            labels = detail.get('labels', {})
            if labels.get('bili.bot') == bot['id'] and labels.get('bili.session') == bot['session_id']:
                found.append(entry['address'])
        if len(found) > 1:
            raise RuntimeError('multiple terminals match this bot and UUID; refusing to choose')
        if not found:
            # Stale session_id: adopt the live terminal already shown in the bot folder instead of opening another tab.
            folder = Path(bot['folder']).expanduser().resolve()
            shown_ids = {t.get('terminal') for t in shown}
            same_folder = []
            for address, detail in live_details.items():
                cwd = detail.get('cwd')
                if address in shown_ids and cwd and Path(cwd).expanduser().resolve() == folder:
                    same_folder.append(address)
            if len(same_folder) > 1:
                raise RuntimeError('multiple terminals in the bot folder; refusing to choose')
            if same_folder:
                found = same_folder
                call(['hc', 'label', found[0], 'bili.bot=' + bot['id'], 'bili.session=' + bot['session_id']])
        if found:
            address = found[0]
        else:
            ready(bot)
            result = call(['hc', 'run', '--bg', '--no-parent', '--no-notify', '--name', identity(bot),
                           '--label', 'herdr.space=' + space_id(bot),
                           '--label', 'herdr.tab=' + space_id(bot) + '-tab',
                           '--label', 'bili.bot=' + bot['id'], '--label', 'bili.session=' + bot['session_id'],
                           '--cwd', str(Path(bot['folder']).expanduser()), '--',
                           'env', 'AG_HOME=' + str(HOME), 'AG_BOTS_FILE=' + str(REGISTRY),
                           str(Path(__file__).resolve().with_name('ag-bot-session')), bot['id']])
            address = result.get('address') or result.get('terminal')
            if not address:
                raise RuntimeError(f'core returned no terminal address: {result}')
        if not any(t.get('terminal') == address for t in shown):
            # Adoption through the bot's explicit space labels may arrive asynchronously.
            call(['hc', 'label', address, 'herdr.space=' + space_id(bot), 'herdr.tab=' + space_id(bot) + '-tab'])
            for attempt in range(40):
                current = call(['herdr-app', 'ls'])
                if any(t.get('terminal') == address for sp in current['spaces'] for tab in sp['tabs'] for t in tab['terminals']):
                    break
                time.sleep(0.1)
            else:
                # A parked terminal already belongs to the bot workspace; select it before keeping.
                call(['herdr-app', 'do', 'space.select', json.dumps({'id': space_id(bot)})])
                call(['herdr-app', 'do', 'terminal.keep', json.dumps({'terminal': address, 'place': 'tab'})])
        call(['herdr-app', 'do', 'agent.focus', json.dumps({'terminal': address})])
        print(json.dumps({'terminal': address, 'bot': bot['id'], 'session_id': bot['session_id']}))

def session(bot):
    with lock(bot, '.session.lock'):
        ready(bot)
        marker = HOME / '.bot-state' / (identity(bot) + '.started')
        config = Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude')).expanduser()
        exists = any((config / 'projects').glob('*/' + bot['session_id'] + '.jsonl'))
        flag = '--resume' if marker.exists() or exists else '--session-id'
        # Persist before launch: an ambiguous failure must never silently create another conversation.
        marker.touch(mode=0o600, exist_ok=True)
        error_path = marker.with_suffix('.error')
        error_path.unlink(missing_ok=True)
        result = subprocess.run([*bot['command'], flag, bot['session_id']], cwd=Path(bot['folder']).expanduser(),
                                env={**os.environ, 'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1'})
        if result.returncode:
            message = f"Bot {bot['name']}: {flag} {bot['session_id']} failed (exit {result.returncode}); no fallback conversation created."
            error_path.write_text(message)
            print(message, file=sys.stderr)
        return result.returncode

def last_active(bot):
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude')).expanduser()
    return max((p.stat().st_mtime for p in (config / 'projects').glob('*/' + bot['session_id'] + '.jsonl')), default=0)


def main():
    try:
        bots = registry()
        if len(sys.argv) == 2 and sys.argv[1] == 'list':
            items = []
            for bot in bots:
                error_path = HOME / '.bot-state' / (identity(bot) + '.error')
                items.append({**bot, 'space_id': space_id(bot),
                              'last_error': error_path.read_text() if error_path.exists() else '',
                              'last_active': last_active(bot)})
            # The principal bot stays on top; the rest follow the latest session activity.
            items.sort(key=lambda item: (not item.get('principal'), -item['last_active']))
            print(json.dumps({'bots': items}))
            return 0
        if len(sys.argv) != 3 or sys.argv[1] not in ('open', 'session'):
            raise ValueError('usage: bots.py list | open <id> | session <id>')
        bot = next((b for b in bots if b['id'] == sys.argv[2]), None)
        if bot is None:
            raise ValueError('unknown bot: ' + sys.argv[2])
        if sys.argv[1] == 'session':
            return session(bot)
        open_bot(bot)
        return 0
    except BlockingIOError:
        print('Bot operation already in progress; no duplicate created.', file=sys.stderr)
        return 0 if sys.argv[1] == 'open' else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Bots: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
