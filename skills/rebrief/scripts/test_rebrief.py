#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
from bot_fixture import BotCase, HELPER  # noqa: E402


class Rebrief(BotCase):
    def test_keeps_session_and_previous_identity(self):
        folder = self.add_helper()
        changed = self.root / 'changed.md'
        changed.write_text('# Changed\n')
        result = self.run_verb('rebrief', 'helper', '--name', 'Renamed', '--brief', str(changed))
        self.assertEqual(result.returncode, 0, result.stderr)
        bot = self.bot('helper')
        self.assertEqual((bot['name'], bot['session_id']), ('Renamed', HELPER))
        self.assertEqual((folder / 'AGENTS.md').read_text(), '# Changed\n')
        self.assertEqual([p.read_text() for p in (folder / '.hire/previous').iterdir()], ['# Helper\n'])

    def test_principal_identity_not_replaced(self):
        self.assertEqual(self.run_verb('rebrief', 'lead', '--brief', str(self.brief)).returncode, 1)
        self.assertEqual((self.lead_folder / 'AGENTS.md').read_text(), 'lead identity\n')

    def test_principal_can_be_renamed(self):
        self.assertEqual(self.run_verb('rebrief', 'lead', '--name', 'Chief').returncode, 0)
        bot = self.bot('lead')
        self.assertEqual((bot['name'], bot['principal']), ('Chief', True))

    def test_name_collision_refused(self):
        self.add_helper()
        self.assertEqual(self.run_verb('rebrief', 'helper', '--name', 'lead').returncode, 1)
        self.assertEqual(self.bot('helper')['name'], 'Helper')

    def test_nothing_to_change(self):
        self.add_helper()
        self.assertEqual(self.run_verb('rebrief', 'helper').returncode, 1)


if __name__ == '__main__':
    unittest.main()
