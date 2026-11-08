#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
from bot_fixture import BotCase  # noqa: E402


class Roster(BotCase):
    def rows(self, **env):
        result = self.run_verb('roster', **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['bots']

    def test_reports_principal_and_live(self):
        row = self.rows()[0]
        self.assertEqual((row['id'], row['principal'], row['live']), ('lead', True, False))

    def test_unknown_live_when_herdr_is_unreachable(self):
        self.assertIsNone(self.rows(HC_FAIL='1')[0]['live'])

    def test_does_not_change_registry(self):
        before = self.registry.read_text()
        self.rows()
        self.assertEqual(self.registry.read_text(), before)


if __name__ == '__main__':
    unittest.main()
