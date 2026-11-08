"""Shared helpers for the canvas tests: a temp home with one bot, a fake `hc` and a fake `herdr-app` on PATH."""
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

CANVAS = Path(__file__).resolve().parent / 'canvas'

FAKE_HC = '''#!/usr/bin/env python3
import json, os, sys
log = os.environ["FAKE_HC_LOG"]
args = sys.argv[1:]
if args[:2] == ["ls", "--json"]:
    print(json.dumps({"terminals": [{"address": "t9", "agent": "claude-code", "cwd": os.environ["FAKE_HC_CWD"], "state": "live", "status": "idle"}]}))
    sys.exit(0)
if args[:1] == ["get"] and "--json" in args:
    print(json.dumps({"address": args[1], "state": "live", "status": {"app": "claude-code", "state": os.environ.get("FAKE_HC_STATE", "idle")}}))
    sys.exit(0)
with open(log, "a") as f:
    f.write(json.dumps(args) + "\\n")
count = os.environ.get("FAKE_HC_FAIL_FIRST")
if count and args[:1] == ["send"]:
    marker = log + ".failed"
    if not os.path.exists(marker):
        open(marker, "w").close()
        print("busy", file=sys.stderr)
        sys.exit(1)
sys.exit(0)
'''

FAKE_HERDR_APP = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_HERDR_LOG"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "home": os.environ.get("HERDR_APP_HOME")}) + "\\n")
sys.exit(int(os.environ.get("FAKE_HERDR_EXIT", "0")))
'''


def script(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class Sandbox:
    """root/home (HOME), root/bot (the bot folder), root/bin (fake hc, herdr-app), root/bots.json."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.home, self.folder, self.bin = self.root / 'home', self.root / 'bot', self.root / 'bin'
        for p in (self.home, self.folder, self.bin):
            p.mkdir()
        (self.root / 'bots.json').write_text(json.dumps({'bots': [{'id': 'b1', 'name': 'B1', 'folder': str(self.folder)}]}))
        script(self.bin / 'hc', FAKE_HC)
        script(self.bin / 'herdr-app', FAKE_HERDR_APP)
        self.hc_log, self.herdr_log = self.root / 'hc.log', self.root / 'herdr.log'
        self.env = {**os.environ, 'CANVAS_BOTS': str(self.root / 'bots.json'), 'HOME': str(self.home),
                    'PATH': f'{self.bin}{os.pathsep}{os.environ["PATH"]}', 'FAKE_HC_LOG': str(self.hc_log),
                    'FAKE_HC_CWD': str(self.folder), 'FAKE_HERDR_LOG': str(self.herdr_log), 'CANVAS_RETRY_DELAY': '0.1'}
        self.env.pop('HERDR_APP_HOME', None)
        self.env.pop('CANVAS_HERDR_HOME', None)
        self.canvas = self.folder / 'canvas'

    def md(self, text, name='page.md'):
        path = self.root / name
        path.write_text(text)
        return path

    def hc_calls(self):
        return [json.loads(l) for l in self.hc_log.read_text().splitlines()] if self.hc_log.exists() else []

    def herdr_calls(self):
        return [json.loads(l) for l in self.herdr_log.read_text().splitlines()] if self.herdr_log.exists() else []

    def cleanup(self):
        self.tmp.cleanup()


def python():
    return sys.executable
