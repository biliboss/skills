#!/usr/bin/env python3
"""Hire, list, update and retire companion bots in the local Herdr bot registry."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
sys.dont_write_bytecode = True
import bots  # noqa: E402


class Refused(Exception):
    """The request breaks a rule; nothing was changed."""


@contextlib.contextmanager
def registry_lock():
    folder = bots.HOME / '.bot-state'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (folder / 'registry.lock').open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def load():
    return json.loads(bots.REGISTRY.read_text())


def principal(items):
    found = [bot for bot in items if bot.get('principal') is True]
    if len(found) != 1:
        raise Refused(f'registry must mark exactly one principal bot, found {len(found)}; nothing changed')
    return found[0]


def validated_temp(data):
    """Write data beside the registry and validate it with the same code that reads the registry."""
    handle, name = tempfile.mkstemp(prefix='.bots-', suffix='.json', dir=bots.REGISTRY.parent)
    temp = Path(name)
    original = bots.REGISTRY
    try:
        with os.fdopen(handle, 'w') as output:
            output.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        shutil.copymode(original, temp)
        bots.REGISTRY = temp
        bots.registry()
        return temp
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    finally:
        bots.REGISTRY = original


def save(previous, data):
    before = principal(previous['bots'])
    after = principal(data['bots'])
    if (before['id'], before['session_id']) != (after['id'], after['session_id']):
        raise Refused('the principal bot cannot change or be removed; nothing changed')
    os.replace(validated_temp(data), bots.REGISTRY)


def find(data, ident):
    for bot in data['bots']:
        if bot['id'] == ident:
            return bot
    raise Refused(f'unknown bot: {ident}')


def is_live(bot):
    """Raises when terminals cannot be inspected, so callers can fail closed."""
    for entry in bots.call(['hc', 'ls'])['terminals']:
        if entry.get('state') != 'live':
            continue
        if entry.get('name') == bots.identity(bot):
            return True
        labels = bots.call(['hc', 'get', entry['address']]).get('labels', {})
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


def new(args):
    brief = read_brief(args.brief)
    with registry_lock():
        data = load()
        lead = principal(data['bots'])
        if any(bot['id'] == args.id for bot in data['bots']):
            raise Refused(f'bot already registered: {args.id}')
        check_name(data, args.name)
        folder = Path(args.folder).expanduser() if args.folder else bots.HOME / args.id
        if os.path.lexists(folder):
            raise Refused(f'folder already exists and was not touched: {folder}')
        bot = {'id': args.id, 'name': args.name.strip(), 'folder': str(folder),
               'session_id': str(uuid.uuid4()), 'command': lead['command']}
        candidate = {**data, 'bots': [*data['bots'], bot]}
        principal(candidate['bots'])
        validated_temp(candidate).unlink()
        folder.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f'.hire-{args.id}-', dir=folder.parent))
        try:
            (staging / '.claude').mkdir()
            (staging / 'AGENTS.md').write_text(brief)
            (staging / 'CLAUDE.md').write_text('@AGENTS.md\n')
            (staging / '.claude' / 'settings.json').write_text('{}\n')
            staging.chmod(0o755)
            os.rename(staging, folder)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        try:
            save(data, candidate)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
    print(json.dumps({'hired': bot['id'], 'folder': bot['folder'], 'session_id': bot['session_id']}))
    if not args.no_open:
        try:
            bots.open_bot(bot)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise Refused(f"bot {bot['id']} was hired but did not open: {error}") from error
    return 0


def listing(_args):
    rows = []
    for bot in bots.registry():
        try:
            live = is_live(bot)
        except (OSError, KeyError, RuntimeError, subprocess.SubprocessError, ValueError):
            live = None
        rows.append({'id': bot['id'], 'name': bot['name'], 'folder': bot['folder'],
                     'principal': bot.get('principal') is True, 'live': live})
    print(json.dumps({'bots': rows}, indent=2, ensure_ascii=False))
    return 0


def replace_identity(bot, brief):
    folder = Path(bot['folder']).expanduser()
    target = folder / 'AGENTS.md'
    if target.exists():
        keep = folder / '.hire' / 'previous'
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, keep / f'AGENTS.{time.strftime("%Y%m%d-%H%M%S")}.md')
    handle, name = tempfile.mkstemp(prefix='.AGENTS-', dir=folder)
    with os.fdopen(handle, 'w') as output:
        output.write(brief)
    os.chmod(name, 0o644)
    os.replace(name, target)


def update(args):
    if args.name is None and args.brief is None:
        raise Refused('nothing to update: pass --name or --brief')
    brief = read_brief(args.brief) if args.brief else None
    with registry_lock():
        data = load()
        principal(data['bots'])
        bot = find(data, args.id)
        if brief is not None and bot.get('principal') is True:
            raise Refused("the principal bot's identity is maintained by the owner, not by hire; nothing changed")
        if args.name is not None:
            check_name(data, args.name, ignore=args.id)
            changed = {**bot, 'name': args.name.strip()}
            save(data, {**data, 'bots': [changed if item is bot else item for item in data['bots']]})
        if brief is not None:
            replace_identity(bot, brief)
    print(json.dumps({'updated': args.id, 'identity_changed': brief is not None,
                      'note': 'a running session reads a new identity only when it starts again'}))
    return 0


def retire(args):
    with registry_lock():
        data = load()
        lead = principal(data['bots'])
        bot = find(data, args.id)
        if bot['id'] == lead['id']:
            raise Refused(f"{bot['name']} is the principal bot and can never be retired")
        if not args.confirm:
            raise Refused(f"retire needs --confirm; {bot['name']} stays registered")
        with bots.lock(bot, '.open.lock'):
            if is_live(bot):
                raise Refused(f"{bot['name']} has a live terminal; close it first, nothing was killed")
            save(data, {**data, 'bots': [item for item in data['bots'] if item is not bot]})
    print(json.dumps({'retired': bot['id'], 'folder_kept': bot['folder'], 'session_kept': bot['session_id']}))
    return 0


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest='action', required=True)
    item = commands.add_parser('new')
    item.add_argument('id')
    item.add_argument('name')
    item.add_argument('--brief', required=True)
    item.add_argument('--folder')
    item.add_argument('--no-open', action='store_true')
    item.set_defaults(run=new)
    commands.add_parser('list').set_defaults(run=listing)
    item = commands.add_parser('update')
    item.add_argument('id')
    item.add_argument('--name')
    item.add_argument('--brief')
    item.set_defaults(run=update)
    item = commands.add_parser('retire')
    item.add_argument('id')
    item.add_argument('--confirm', action='store_true')
    item.set_defaults(run=retire)
    return root


def main():
    args = parser().parse_args()
    try:
        return args.run(args)
    except BlockingIOError:
        print('hire: this bot is being opened right now; nothing changed', file=sys.stderr)
    except (Refused, OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'hire: {error}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
