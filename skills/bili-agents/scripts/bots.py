#!/usr/bin/env python3
"""Local bot registry and Herdr session operations (no injected agent settings)."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

HOME = Path(os.environ.get('AG_HOME', Path.home() / 'agents')).expanduser()
REGISTRY = Path(os.environ.get('AG_BOTS_FILE', HOME / 'bots.json'))


def call(argv):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(f'{argv[0]}: {result.stderr.strip() or result.stdout.strip()}')
    return json.loads(result.stdout)


def registry(path=None):
    data = json.loads((path or REGISTRY).read_text())
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
        found = []
        for entry in entries:
            if entry.get('state') != 'live':
                continue
            # The unique name exists from creation, before the wrapper adds labels.
            if entry.get('name') == identity(bot):
                found.append(entry['address'])
                continue
            detail = call(['hc', 'get', entry['address']])
            labels = detail.get('labels', {})
            if labels.get('bili.bot') == bot['id'] and labels.get('bili.session') == bot['session_id']:
                found.append(entry['address'])
        if len(found) > 1:
            raise RuntimeError('multiple terminals match this bot and UUID; refusing to choose')
        layout = call(['herdr-app', 'ls'])
        shown = [t for s in layout['spaces'] for tab in s['tabs'] for t in tab['terminals']]
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


class Refused(ValueError):
    """The request breaks a rule; nothing was changed."""


@contextlib.contextmanager
def registry_lock():
    folder = HOME / '.bot-state'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (folder / 'registry.lock').open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def load():
    return json.loads(REGISTRY.read_text())


def principal(items):
    found = [bot for bot in items if bot.get('principal') is True]
    if len(found) != 1:
        raise Refused(f'registry must mark exactly one principal bot, found {len(found)}; nothing changed')
    return found[0]


def find(data, ident):
    for bot in data['bots']:
        if bot['id'] == ident:
            return bot
    raise Refused(f'unknown bot: {ident}')


def validated_temp(data):
    """Write data beside the registry and validate it with the code that reads the registry."""
    handle, name = tempfile.mkstemp(prefix='.bots-', suffix='.json', dir=REGISTRY.parent)
    temp = Path(name)
    try:
        with os.fdopen(handle, 'w') as output:
            output.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        shutil.copymode(REGISTRY, temp)
        registry(temp)
        return temp
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def save(previous, data):
    """Replace the registry atomically; the principal bot must survive every write."""
    before = principal(previous['bots'])
    after = principal(data['bots'])
    if (before['id'], before['session_id']) != (after['id'], after['session_id']):
        raise Refused('the principal bot cannot change or be removed; nothing changed')
    os.replace(validated_temp(data), REGISTRY)


def is_live(bot):
    """Raises when terminals cannot be inspected, so callers can fail closed."""
    for entry in call(['hc', 'ls'])['terminals']:
        if entry.get('state') != 'live':
            continue
        if entry.get('name') == identity(bot):
            return True
        labels = call(['hc', 'get', entry['address']]).get('labels', {})
        if labels.get('bili.bot') == bot['id'] and labels.get('bili.session') == bot['session_id']:
            return True
    return False


def read_brief(path):
    text = Path(path).expanduser().read_text()
    if not text.strip():
        raise Refused(f'brief is empty: {path}')
    return text


def check_name(data, name, ignore=None):
    if not name.strip():
        raise Refused('name must not be empty')
    for bot in data['bots']:
        if bot['id'] != ignore and bot['name'].casefold() == name.strip().casefold():
            raise Refused(f"name already used by bot {bot['id']}")


# Listening: the listener registers, in the target's project settings, hooks that run ag-notify.
HOOK_EVENTS = {'stop': 'Stop', 'notification': 'Notification'}
NOTIFIER = Path(__file__).resolve().with_name('ag-notify')


def settings_path(bot):
    return Path(bot['folder']).expanduser() / '.claude' / 'settings.json'


def read_settings(path):
    """The target's project settings as a dict; a missing file is empty, a broken one is refused."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        raise Refused(f'{path} is not valid JSON ({error}); nothing changed') from error
    if not isinstance(data, dict):
        raise Refused(f'{path} must hold a JSON object; nothing changed')
    return data


def write_settings(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix='.settings-', suffix='.json', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(handle, 'w') as output:
            output.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        if path.exists():
            shutil.copymode(path, temp)
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def notifier_command(listener_id, event):
    return f'{NOTIFIER} {listener_id} {event}'


def notifier_target(hook):
    """(listener_id, event) when this hook entry runs ag-notify, else None."""
    if not isinstance(hook, dict) or hook.get('type') != 'command' or not isinstance(hook.get('command'), str):
        return None
    try:
        argv = shlex.split(hook['command'])
    except ValueError:
        return None
    if len(argv) >= 3 and Path(argv[0]).name == NOTIFIER.name and argv[2] in HOOK_EVENTS:
        return argv[1], argv[2]
    return None


def hook_groups(settings, event):
    hooks = settings.get('hooks')
    if hooks is None:
        hooks = settings['hooks'] = {}
    if not isinstance(hooks, dict):
        raise Refused('settings.hooks must be an object; nothing changed')
    groups = hooks.get(HOOK_EVENTS[event])
    if groups is None:
        groups = hooks[HOOK_EVENTS[event]] = []
    if not isinstance(groups, list):
        raise Refused(f'settings.hooks.{HOOK_EVENTS[event]} must be an array; nothing changed')
    return groups


def remove_listener(settings, listener_id, events=HOOK_EVENTS):
    """Drop only this listener's ag-notify entries; foreign hooks and groups stay as they are."""
    for event in events:
        groups = hook_groups(settings, event)
        kept = []
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get('hooks'), list):
                group['hooks'] = [h for h in group['hooks'] if notifier_target(h) != (listener_id, event)]
                if not group['hooks']:
                    continue
            kept.append(group)
        groups[:] = kept
        if not groups:
            del settings['hooks'][HOOK_EVENTS[event]]
    if not settings['hooks']:
        del settings['hooks']


def add_listener(settings, listener_id, events=HOOK_EVENTS):
    """One entry per listener and event, whatever was there before (the notifier path may have moved)."""
    remove_listener(settings, listener_id, events)
    for event in events:
        hook_groups(settings, event).append({'hooks': [
            {'type': 'command', 'command': notifier_command(listener_id, event), 'timeout': 30}]})


def listeners(bot):
    """Ids of the bots listening to this one, read from its project settings; unreadable settings count as none."""
    try:
        settings = read_settings(settings_path(bot))
    except (OSError, Refused):
        return []
    found = set()
    hooks = settings.get('hooks') if isinstance(settings.get('hooks'), dict) else {}
    for event in HOOK_EVENTS.values():
        for group in hooks.get(event) or []:
            if isinstance(group, dict):
                for hook in group.get('hooks') or []:
                    target = notifier_target(hook)
                    if target:
                        found.add(target[0])
    return sorted(found)


def verb(action):
    """Run one lifecycle command: stdout is the result, stderr the refusal, exit 0 or 1."""
    program = Path(sys.argv[0]).name
    try:
        print(json.dumps(action(), indent=2, ensure_ascii=False))
        return 0
    except BlockingIOError:
        print(f'{program}: this bot is being opened right now; nothing changed', file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'{program}: {error}', file=sys.stderr)
    return 1


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
