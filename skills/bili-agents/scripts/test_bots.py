import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bots', Path(__file__).with_name('bots.py'))
bots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bots)


class BotsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bot = {'id': 'test', 'name': 'Test', 'folder': str(self.root), 'command': ['python3'],
                    'session_id': '00000000-0000-4000-8000-000000000001'}
        self.home = patch.object(bots, 'HOME', self.root)
        self.home.start()
        self.addCleanup(self.home.stop)
        self.registry = self.root / 'bots.json'
        self.registry.write_text(json.dumps({'bots': [self.bot]}))
        self.patch = patch.object(bots, 'REGISTRY', self.registry)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_registry_rejects_duplicates_and_session_overrides(self):
        for entries in ([self.bot, self.bot], [{**self.bot, 'command': ['claude', '--continue']}]):
            self.registry.write_text(json.dumps({'bots': entries}))
            with self.assertRaises(ValueError):
                bots.registry()

    def test_unavailable_command(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            bots.ready({**self.bot, 'command': ['no-such-bot-command-123']})

    def test_first_then_resume_and_no_fallback_on_failure(self):
        with patch.object(bots.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
            run.return_value.returncode = 0
            self.assertEqual(bots.session(self.bot), 0)
            self.assertEqual(run.call_args.args[0][-2:], ['--session-id', self.bot['session_id']])
            run.return_value.returncode = 42
            self.assertEqual(bots.session(self.bot), 42)
            self.assertEqual(run.call_args.args[0][-2:], ['--resume', self.bot['session_id']])
            self.assertEqual(run.call_count, 2)

    def test_lock_prevents_duplicates(self):
        guard = bots.lock(self.bot, '.open.lock')
        try:
            with self.assertRaises(BlockingIOError):
                bots.open_bot(self.bot)
        finally:
            guard.close()

    def exercise_open(self, shown, live=True):
        calls = []
        def call(argv):
            calls.append(argv)
            if argv[:2] == ['hc', 'ls']:
                return {'terminals': [{'address': 't99', 'state': 'live', 'name': bots.identity(self.bot)}] if live else []}
            if argv[:2] == ['hc', 'run']:
                return {'address': 't99'}
            if argv == ['herdr-app', 'status']:
                return {'focused_pane': 'p1'}
            if argv == ['herdr-app', 'ls']:
                return {'spaces': [{'tabs': [{'terminals': shown if not any(c[:2] == ['hc', 'label'] for c in calls) else [{'terminal': 't99', 'pane': 'p99'}]}]}]}
            return {}
        with patch.object(bots, 'call', side_effect=call), contextlib.redirect_stdout(io.StringIO()):
            bots.open_bot(self.bot)
        return calls

    def test_focus_existing_without_creation(self):
        calls = self.exercise_open([{'terminal': 't99', 'pane': 'p1'}])
        self.assertFalse(any(c[:2] == ['hc', 'run'] for c in calls))
        self.assertFalse(any('terminal.keep' in c for c in calls))
        self.assertTrue(any('agent.focus' in c for c in calls))

    def test_hidden_terminal_is_adopted_in_own_workspace(self):
        calls = self.exercise_open([{'terminal': 'other', 'pane': 'p1'}])
        self.assertFalse(any(c[:2] == ['hc', 'run'] for c in calls))
        label = next(c for c in calls if c[:2] == ['hc', 'label'])
        self.assertIn('herdr.space=' + bots.space_id(self.bot), label)
        self.assertFalse(any('terminal.keep' in c for c in calls))

    def test_new_terminal_has_dedicated_workspace(self):
        calls = self.exercise_open([], live=False)
        run = next(c for c in calls if c[:2] == ['hc', 'run'])
        self.assertIn('bili.session=' + self.bot['session_id'], run)
        self.assertIn('herdr.space=' + bots.space_id(self.bot), run)

    def test_space_identity_is_stable_and_bot_specific(self):
        self.assertEqual(bots.space_id(self.bot), bots.space_id(dict(self.bot)))
        self.assertNotEqual(bots.space_id(self.bot), bots.space_id({**self.bot, 'id': 'other'}))


if __name__ == '__main__':
    unittest.main()
