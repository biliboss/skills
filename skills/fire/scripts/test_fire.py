#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
from bot_fixture import BotCase  # noqa: E402
import bots  # noqa: E402


class Fire(BotCase):
    def fire(self, ident='helper', **env):
        return self.run_verb('fire', ident, '--confirm', **env)

    def test_principal_never_fired(self):
        before = self.registry.read_text()
        result = self.fire('lead')
        self.assertEqual(result.returncode, 1)
        self.assertIn('principal', result.stderr)
        self.assertEqual(self.registry.read_text(), before)

    def test_no_principal_fails_closed(self):
        self.add_helper()
        items = self.data()
        del items[0]['principal']
        self.write(items)
        for ident in ('lead', 'helper'):
            self.assertEqual(self.fire(ident).returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_two_principals_fail_closed(self):
        self.add_helper()
        items = self.data()
        items[1]['principal'] = True
        self.write(items)
        self.assertEqual(self.fire().returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_needs_confirm(self):
        self.add_helper()
        self.assertEqual(self.run_verb('fire', 'helper').returncode, 1)
        self.assertEqual(len(self.data()), 2)

    def test_keeps_folder(self):
        folder = self.add_helper()
        result = self.fire()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([b['id'] for b in self.data()], ['lead'])
        self.assertEqual((folder / 'AGENTS.md').read_text(), '# Helper\n')

    def test_live_bot_not_fired(self):
        self.add_helper()
        self.terminals.write_text(json.dumps({'terminals': [
            {'state': 'live', 'address': 'a', 'name': bots.identity(self.bot('helper'))}]}))
        result = self.fire()
        self.assertEqual(result.returncode, 1)
        self.assertIn('live', result.stderr)
        self.assertEqual(len(self.data()), 2)

    def test_uninspectable_terminals_block(self):
        self.add_helper()
        self.assertEqual(self.fire(HC_FAIL='1').returncode, 1)
        self.assertEqual(len(self.data()), 2)


if __name__ == '__main__':
    unittest.main()
