"""Shared test fixture for the bot verbs: a temporary registry and a fake hc."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILLS = Path(__file__).resolve().parents[2]
LEAD = '11111111-1111-4111-8111-111111111111'
HELPER = '22222222-2222-4222-8222-222222222222'


class BotCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'agents'
        self.home.mkdir()
        self.registry = self.home / 'bots.json'
        self.lead_folder = self.home / 'lead'
        self.lead_folder.mkdir()
        (self.lead_folder / 'AGENTS.md').write_text('lead identity\n')
        self.write([{'id': 'lead', 'name': 'Lead', 'folder': str(self.lead_folder), 'session_id': LEAD,
                     'command': ['/bin/echo'], 'principal': True}])
        self.brief = self.root / 'brief.md'
        self.brief.write_text('# Helper\n')
        self.terminals = self.root / 'terminals.json'
        self.terminals.write_text('{"terminals": []}')
        fake = self.root / 'bin'
        fake.mkdir()
        (fake / 'hc').write_text('#!/bin/sh\nif [ -n "$HC_FAIL" ]; then exit 1; fi\ncat "$HC_TERMINALS"\n')
        (fake / 'hc').chmod(0o755)
        self.env = {**os.environ, 'AG_HOME': str(self.home), 'AG_BOTS_FILE': str(self.registry),
                    'PATH': f"{fake}:{os.environ['PATH']}", 'HC_TERMINALS': str(self.terminals),
                    'PYTHONDONTWRITEBYTECODE': '1'}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, items):
        self.registry.write_text(json.dumps({'bots': items}))

    def data(self):
        return json.loads(self.registry.read_text())['bots']

    def bot(self, ident):
        return next(item for item in self.data() if item['id'] == ident)

    def run_verb(self, name, *args, **env):
        return subprocess.run([sys.executable, str(SKILLS / name / 'scripts' / name), *args],
                              capture_output=True, text=True, env={**self.env, **env})

    def add_helper(self):
        """Register a companion directly, so each verb's tests do not depend on another verb."""
        folder = self.home / 'helper'
        folder.mkdir()
        (folder / 'AGENTS.md').write_text('# Helper\n')
        self.write([*self.data(), {'id': 'helper', 'name': 'Helper', 'folder': str(folder), 'session_id': HELPER,
                                   'command': ['/bin/echo']}])
        return folder
