"""Opt-in Herdr integration: creates and removes only temporary test terminals."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

if os.environ.get("HERDR_DISPOSABLE") != "1":
    raise SystemExit("Refusing: this test moves focus. Run it only on a disposable Herdr (HERDR_DISPOSABLE=1), never the owner's.")

OPENER = str(Path(__file__).with_name('ag-open').resolve())


def hc(*argv):
    return json.loads(subprocess.check_output(['hc', *argv], text=True))


def wait_for(check):
    for _ in range(60):
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError('test condition did not become true')


with tempfile.TemporaryDirectory(prefix='herdr-bots-test-') as temp:
    root = Path(temp)
    script = root / 'command.py'
    script.write_text('import json,sys,time\nfrom pathlib import Path\np=Path(__file__).parent\nwith (p/"argv.jsonl").open("a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\nif (p/"fail").exists(): sys.exit(23)\ntime.sleep(120)\n')
    session = str(uuid.uuid4())
    ident = 'test-' + uuid.uuid4().hex[:10]
    registry = root / 'bots.json'
    registry.write_text(json.dumps({'bots': [{'id': ident, 'name': 'Bots verification', 'folder': temp,
                                           'session_id': session, 'command': ['python3', str(script)]}]}))
    env = {**os.environ, 'AG_HOME': temp, 'AG_BOTS_FILE': str(registry)}
    addresses = set()

    def open_bot():
        return subprocess.run([OPENER, '--focus', ident], env=env, text=True, capture_output=True)

    def terminals():
        return [t for t in hc('ls')['terminals'] if t.get('name', '').startswith('bot-') and
                hc('get', t['address']).get('labels', {}).get('bili.bot') == ident]

    def log():
        path = root / 'argv.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    try:
        result = open_bot()
        assert result.returncode == 0, result.stderr
        address = json.loads(result.stdout)['terminal']
        addresses.add(address)
        wait_for(lambda: len(log()) == 1)
        assert log() == [['--session-id', session]], log()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: open_bot(), range(6)))
        assert all(r.returncode == 0 for r in results), results
        assert len(terminals()) == 1 and len(log()) == 1
        subprocess.run(['herdr-app', 'do', 'terminal.park', '--terminal', address], check=True, capture_output=True)
        wait_for(lambda: not hc('get', address)['labels'].get('herdr.space'))
        result = open_bot()
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['terminal'] == address
        hc('kill', address)
        wait_for(lambda: hc('get', address)['state'] != 'live')
        result = open_bot()
        assert result.returncode == 0, result.stderr
        address = json.loads(result.stdout)['terminal']
        addresses.add(address)
        wait_for(lambda: len(log()) == 2)
        assert log()[-1] == ['--resume', session], log()
        hc('kill', address)
        wait_for(lambda: hc('get', address)['state'] != 'live')
        (root / 'fail').touch()
        result = open_bot()
        wait_for(lambda: len(log()) == 3)
        assert log()[-1] == ['--resume', session] and len(log()) == 3
        wait_for(lambda: not terminals())
        listed = subprocess.check_output([OPENER, '--list'], env=env, text=True)
        assert 'exit 23' in json.loads(listed)['bots'][0]['last_error']
        print('PASS: creation, concurrent clicks, focus, parking, resume UUID and failed resume without fallback')
    finally:
        for terminal in hc('ls', '--all')['terminals']:
            detail = hc('get', terminal['address'])
            if detail.get('labels', {}).get('bili.bot') == ident:
                addresses.add(terminal['address'])
        for address in addresses:
            if hc('get', address)['state'] == 'live':
                hc('kill', address)
            hc('rm', address)
