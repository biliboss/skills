#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
from bot_fixture import BotCase, LEAD  # noqa: E402


class Hire(BotCase):
    def hire(self, ident='helper', name='Helper'):
        return self.run_verb('hire', ident, name, '--brief', str(self.brief), '--no-open')

    def test_creates_identity_and_registers(self):
        result = self.hire()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['hired'], 'helper')
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
        self.assertEqual(sorted(p.name for p in self.home.iterdir() if not p.name.startswith('.')),
                         ['bots.json', 'lead'])

    def test_needs_marked_principal(self):
        items = self.data()
        del items[0]['principal']
        self.write(items)
        self.assertEqual(self.hire().returncode, 1)
        self.assertFalse((self.home / 'helper').exists())

    def test_concurrent_hires_all_land(self):
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda n: self.hire(f'bot{n}', f'Bot {n}'), range(8)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        self.assertEqual(len(self.data()), 9)


if __name__ == '__main__':
    unittest.main()
