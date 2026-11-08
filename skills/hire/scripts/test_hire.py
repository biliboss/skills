#!/usr/bin/env python3
"""hire.py against a temporary registry and a fake hc; no real Herdr terminal is touched."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest

SCRIPT = Path(__file__).resolve().with_name('hire.py')
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
import bots  # noqa: E402

LEAD = '11111111-1111-4111-8111-111111111111'


class Hire(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name).resolve() / 'agents'
        self.home.mkdir()
        self.registry = self.home / 'bots.json'
        self.lead_folder = self.home / 'lead'
        self.lead_folder.mkdir()
        (self.lead_folder / 'AGENTS.md').write_text('lead identity\n')
        self.write([{'id': 'lead', 'name': 'Lead', 'folder': str(self.lead_folder), 'session_id': LEAD,
                     'command': ['/bin/echo'], 'principal': True}])
        self.brief = self.home.parent / 'brief.md'
        self.brief.write_text('# Helper\n')
        self.terminals = self.home.parent / 'terminals.json'
        self.terminals.write_text('{"terminals": []}')
        fake = self.home.parent / 'bin'
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

    def run_hire(self, *args, **env):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              env={**self.env, **env})

    def hire(self, ident='helper', name='Helper'):
        return self.run_hire('new', ident, name, '--brief', str(self.brief), '--no-open')

    def bot(self, ident):
        return next(item for item in self.data() if item['id'] == ident)

    def test_new_creates_identity_and_registers(self):
        result = self.hire()
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.home / 'helper'
        self.assertEqual((folder / 'AGENTS.md').read_text(), '# Helper\n')
        self.assertEqual((folder / 'CLAUDE.md').read_text(), '@AGENTS.md\n')
        self.assertEqual(json.loads((folder / '.claude/settings.json').read_text()), {})
        bot = self.bot('helper')
        self.assertEqual(bot['command'], ['/bin/echo'])
        self.assertNotIn('principal', bot)
        self.assertNotEqual(bot['session_id'], LEAD)

    def test_duplicates_refused(self):
        self.assertEqual(self.hire().returncode, 0)
        before = self.registry.read_text()
        self.assertEqual(self.hire().returncode, 1)
        self.assertEqual(self.hire('other', 'helper').returncode, 1)
        self.assertEqual(self.registry.read_text(), before)

    def test_existing_folder_untouched(self):
        folder = self.home / 'helper'
        folder.mkdir()
        (folder / 'keep.txt').write_text('mine')
        self.assertEqual(self.hire().returncode, 1)
        self.assertEqual([p.name for p in folder.iterdir()], ['keep.txt'])
        self.assertEqual(len(self.data()), 1)

    def test_invalid_id_leaves_nothing(self):
        self.assertEqual(self.hire('Bad/Id').returncode, 1)
        self.assertEqual(sorted(p.name for p in self.home.iterdir() if not p.name.startswith('.')), ['bots.json', 'lead'])

    def test_principal_cannot_be_retired(self):
        before = self.registry.read_text()
        result = self.run_hire('retire', 'lead', '--confirm')
        self.assertEqual(result.returncode, 1)
        self.assertIn('principal', result.stderr)
        self.assertEqual(self.registry.read_text(), before)

    def test_no_marked_principal_fails_closed(self):
        self.assertEqual(self.hire().returncode, 0)
        items = self.data()
        del items[0]['principal']
        self.write(items)
        for ident in ('lead', 'helper'):
            self.assertEqual(self.run_hire('retire', ident, '--confirm').returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_two_principals_fail_closed(self):
        self.assertEqual(self.hire().returncode, 0)
        items = self.data()
        items[1]['principal'] = True
        self.write(items)
        self.assertEqual(self.run_hire('retire', 'helper', '--confirm').returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_principal_identity_not_replaced(self):
        self.assertEqual(self.run_hire('update', 'lead', '--brief', str(self.brief)).returncode, 1)
        self.assertEqual((self.lead_folder / 'AGENTS.md').read_text(), 'lead identity\n')

    def test_update_keeps_session_and_previous_identity(self):
        self.assertEqual(self.hire().returncode, 0)
        session = self.bot('helper')['session_id']
        changed = self.home.parent / 'changed.md'
        changed.write_text('# Changed\n')
        result = self.run_hire('update', 'helper', '--name', 'Renamed', '--brief', str(changed))
        self.assertEqual(result.returncode, 0, result.stderr)
        bot = self.bot('helper')
        self.assertEqual((bot['name'], bot['session_id']), ('Renamed', session))
        folder = self.home / 'helper'
        self.assertEqual((folder / 'AGENTS.md').read_text(), '# Changed\n')
        self.assertEqual([p.read_text() for p in (folder / '.hire/previous').iterdir()], ['# Helper\n'])

    def test_retire_needs_confirm(self):
        self.assertEqual(self.hire().returncode, 0)
        self.assertEqual(self.run_hire('retire', 'helper').returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_retire_keeps_folder(self):
        self.assertEqual(self.hire().returncode, 0)
        result = self.run_hire('retire', 'helper', '--confirm')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([b['id'] for b in self.data()], ['lead'])
        self.assertEqual((self.home / 'helper/AGENTS.md').read_text(), '# Helper\n')

    def test_live_bot_not_retired(self):
        self.assertEqual(self.hire().returncode, 0)
        self.terminals.write_text(json.dumps({'terminals': [
            {'state': 'live', 'address': 'a', 'name': bots.identity(self.bot('helper'))}]}))
        result = self.run_hire('retire', 'helper', '--confirm')
        self.assertEqual(result.returncode, 1)
        self.assertIn('live', result.stderr)
        self.assertEqual(len(self.data()), 2)

    def test_uninspectable_terminals_block_retire(self):
        self.assertEqual(self.hire().returncode, 0)
        self.assertEqual(self.run_hire('retire', 'helper', '--confirm', HC_FAIL='1').returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_list_reports_principal(self):
        result = self.run_hire('list')
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)['bots'][0]
        self.assertEqual((row['id'], row['principal'], row['live']), ('lead', True, False))

    def test_concurrent_hires_all_land(self):
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda n: self.hire(f'bot{n}', f'Bot {n}'), range(8)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        self.assertEqual(len(self.data()), 9)


if __name__ == '__main__':
    unittest.main()
