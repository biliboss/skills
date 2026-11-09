import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
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

    def exercise_open(self, shown, live=True, focus=False, never_shown=False):
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
                return {'spaces': [{'tabs': [{'terminals': shown if never_shown or not any(c[:2] == ['hc', 'label'] for c in calls) else [{'terminal': 't99', 'pane': 'p99'}]}]}]}
            return {}
        with patch.object(bots, 'call', side_effect=call), patch.object(bots.time, 'sleep'), \
                contextlib.redirect_stdout(io.StringIO()):
            bots.open_bot(self.bot, focus=focus)
        return calls

    FOCUS = ('agent.focus', 'space.select', 'terminal.keep', 'tab.select', 'pane.focus', 'tab.new', 'space.new')

    def moves_focus(self, calls):
        return [c for c in calls if any(f in part for part in c for f in self.FOCUS)]

    def test_default_never_moves_focus_in_any_path(self):
        paths = {'existing': dict(shown=[{'terminal': 't99', 'pane': 'p1'}]),
                 'adopt_async': dict(shown=[{'terminal': 'other', 'pane': 'p1'}]),
                 'new': dict(shown=[], live=False),
                 'keep_never_shown': dict(shown=[{'terminal': 'other', 'pane': 'p1'}], never_shown=True)}
        for name, kw in paths.items():
            with self.subTest(name):
                self.assertEqual(self.moves_focus(self.exercise_open(**kw)), [])

    def spaces_with(self, terminals, details):
        calls = []
        def call(argv):
            calls.append(argv)
            if argv[:2] == ['hc', 'ls']:
                return {'terminals': terminals}
            return details[argv[2]]
        with patch.object(bots, 'call', side_effect=call):
            return bots.live_spaces([self.bot]), calls

    def test_live_space_comes_from_the_terminal_label(self):
        labels = {'bili.bot': 'test', 'bili.session': self.bot['session_id'], 'herdr.space': 'bot-real'}
        terminal = {'address': 't1', 'state': 'live', 'cwd': str(self.root)}
        self.assertEqual(self.spaces_with([terminal], {'t1': {'labels': labels}})[0], {'test': 'bot-real'})

    def test_named_terminal_counts_and_other_terminals_are_not_fetched(self):
        named = {'address': 't1', 'state': 'live', 'name': bots.identity(self.bot), 'cwd': '/elsewhere'}
        others = [{'address': 't2', 'state': 'live', 'name': 'other'}, {'address': 't3', 'state': 'live', 'cwd': '/elsewhere'},
                  {'address': 't4', 'state': 'done', 'cwd': str(self.root)}]
        spaces, calls = self.spaces_with([named, *others], {'t1': {'labels': {'herdr.space': 'bot-real'}}})
        self.assertEqual(spaces, {'test': 'bot-real'})
        self.assertEqual([c for c in calls if c[:2] == ['hc', 'get']], [['hc', 'get', 't1']])

    def test_list_keeps_the_computed_space_without_a_live_terminal(self):
        def fail(argv):
            raise RuntimeError('hc: down')
        for side_effect in (fail, lambda argv: {'terminals': []}):
            with patch.object(bots, 'call', side_effect=side_effect), patch.object(sys, 'argv', ['bots.py', 'list']), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(bots.main(), 0)
            self.assertEqual(json.loads(out.getvalue())['bots'][0]['space_id'], bots.space_id(self.bot))

    def test_ambiguous_live_spaces_fall_back(self):
        labels = {'bili.bot': 'test', 'bili.session': self.bot['session_id']}
        terminals = [{'address': a, 'state': 'live', 'cwd': str(self.root)} for a in ('t1', 't2')]
        details = {'t1': {'labels': {**labels, 'herdr.space': 'a'}}, 't2': {'labels': {**labels, 'herdr.space': 'b'}}}
        self.assertEqual(self.spaces_with(terminals, details)[0], {})

    def test_open_relabels_and_renames_in_the_real_workspace(self):
        calls = []
        def call(argv):
            calls.append(argv)
            if argv[:2] == ['hc', 'ls']:
                return {'terminals': [{'address': 't99', 'state': 'live', 'name': bots.identity(self.bot)}]}
            if argv[:2] == ['hc', 'get']:
                return {'labels': {'herdr.space': 'bot-real'}}
            if argv == ['herdr-app', 'ls']:
                return {'spaces': [{'id': 'bot-real', 'name': 'x', 'tabs': [{'terminals': [{'terminal': 'other'}]}]}]}
            return {}
        with patch.object(bots, 'call', side_effect=call), patch.object(bots.time, 'sleep'), \
                contextlib.redirect_stdout(io.StringIO()):
            bots.open_bot(self.bot)
        self.assertIn('herdr.space=bot-real', next(c for c in calls if c[:2] == ['hc', 'label']))
        self.assertFalse(any('terminal.keep' in c or 'space.select' in c or 'agent.focus' in c for c in calls))

    def test_never_shown_leaves_terminal_labeled_without_keep(self):
        calls = self.exercise_open([{'terminal': 'other', 'pane': 'p1'}], never_shown=True)
        self.assertTrue(any(c[:2] == ['hc', 'label'] for c in calls))
        self.assertFalse(any('terminal.keep' in c or 'space.select' in c for c in calls))

    def test_explicit_focus_selects_keeps_and_focuses(self):
        calls = self.exercise_open([{'terminal': 'other', 'pane': 'p1'}], never_shown=True, focus=True)
        flat = [' '.join(c) for c in calls]
        self.assertTrue(any('space.select' in c for c in flat))
        self.assertTrue(any('terminal.keep' in c for c in flat))
        self.assertTrue(any('agent.focus' in c for c in flat))

    def test_cli_focus_flag(self):
        with patch.object(bots, 'open_bot') as opener:
            for argv, expected in ((['open', 'test'], False), (['open', '--focus', 'test'], True)):
                with patch.object(sys, 'argv', ['bots.py', *argv]):
                    self.assertEqual(bots.main(), 0)
                self.assertEqual(opener.call_args.kwargs['focus'], expected)
            with patch.object(sys, 'argv', ['bots.py', 'session', '--focus', 'test']), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(bots.main(), 1)

    def test_ag_open_forwards_flags_and_panel_click_requests_focus(self):
        self.assertIn("'open', *sys.argv[1:]", Path(__file__).with_name('ag-open').read_text())
        main_js = Path(__file__).resolve().parents[3] / 'apps/herdr-bots/main.js'
        self.assertIn("props().opener, '--focus', bot.id", main_js.read_text())

    def test_focus_existing_without_creation(self):
        calls = self.exercise_open([{'terminal': 't99', 'pane': 'p1'}], focus=True)
        self.assertFalse(any(c[:2] == ['hc', 'run'] for c in calls))
        self.assertFalse(any('terminal.keep' in c for c in calls))
        self.assertTrue(any('agent.focus' in c for c in calls))

    def test_hidden_terminal_is_adopted_in_own_workspace(self):
        calls = self.exercise_open([{'terminal': 'other', 'pane': 'p1'}])
        self.assertFalse(any(c[:2] == ['hc', 'run'] for c in calls))
        label = next(c for c in calls if c[:2] == ['hc', 'label'])
        self.assertIn('herdr.space=' + bots.space_id(self.bot), label)
        self.assertFalse(any('terminal.keep' in c for c in calls))

    def test_stale_session_adopts_live_shown_terminal_in_folder(self):
        calls = []
        def call(argv):
            calls.append(argv)
            if argv[:2] == ['hc', 'ls']:
                return {'terminals': [{'address': 't7', 'state': 'live', 'name': 'unrelated'}]}
            if argv == ['hc', 'get', 't7']:
                return {'labels': {'bili.bot': 'test', 'bili.session': 'stale'}, 'cwd': str(self.root)}
            if argv == ['herdr-app', 'ls']:
                return {'spaces': [{'tabs': [{'terminals': [{'terminal': 't7', 'pane': 'p1'}]}]}]}
            return {}
        with patch.object(bots, 'call', side_effect=call), contextlib.redirect_stdout(io.StringIO()) as out:
            bots.open_bot(self.bot)
        self.assertFalse(any(c[:2] == ['hc', 'run'] for c in calls))
        label = next(c for c in calls if c[:2] == ['hc', 'label'])
        self.assertEqual(label[2], 't7')
        self.assertIn('bili.session=' + self.bot['session_id'], label)
        self.assertEqual(json.loads(out.getvalue())['terminal'], 't7')

    def test_new_terminal_has_dedicated_workspace(self):
        calls = self.exercise_open([], live=False)
        run = next(c for c in calls if c[:2] == ['hc', 'run'])
        self.assertIn('bili.session=' + self.bot['session_id'], run)
        self.assertIn('herdr.space=' + bots.space_id(self.bot), run)

    def layout(self, space_name, tab_names):
        tabs = [{'id': 'tab%d' % i, 'name': n, 'terminals': [{'terminal': 't%d' % i,
                 'name': bots.identity(self.bot) if i == 1 else None}]} for i, n in enumerate(tab_names)]
        return {'spaces': [{'id': bots.space_id(self.bot), 'name': space_name, 'tabs': tabs}]}

    def run_sync(self, layout, **kw):
        calls = []
        with patch.object(bots, 'call', side_effect=lambda argv: calls.append(argv) or {}):
            bots.sync_names(self.bot, layout, **kw)
        return calls

    def test_sync_names_renames_when_different(self):
        calls = self.run_sync(self.layout('test', ['0', '1']))
        self.assertEqual(calls, [
            ['herdr-app', 'do', 'space.rename', json.dumps({'id': bots.space_id(self.bot), 'name': 'Test'})],
            ['herdr-app', 'do', 'tab.rename', json.dumps({'id': 'tab1', 'name': 'Test'})]])

    def test_sync_names_noop_when_equal(self):
        self.assertEqual(self.run_sync(self.layout('Test', ['x', 'Test'])), [])

    def test_sync_names_picks_the_tab_with_the_terminal(self):
        calls = self.run_sync(self.layout('Test', ['a', 'b', 'c']), address='t2')
        self.assertEqual(calls, [['herdr-app', 'do', 'tab.rename', json.dumps({'id': 'tab2', 'name': 'Test'})]])

    def test_open_bot_syncs_names_after_terminal_shows(self):
        calls = self.exercise_open([{'terminal': 't99', 'pane': 'p1'}])
        self.assertEqual(sum(c[:2] == ['herdr-app', 'ls'] for c in calls) >= 2, True)

    def test_space_identity_is_stable_and_bot_specific(self):
        self.assertEqual(bots.space_id(self.bot), bots.space_id(dict(self.bot)))
        self.assertNotEqual(bots.space_id(self.bot), bots.space_id({**self.bot, 'id': 'other'}))

    def test_list_keeps_principal_first_then_most_recent(self):
        def session(n):
            return f'00000000-0000-4000-8000-00000000000{n}'
        entries = [{**self.bot, 'id': 'never', 'session_id': session(1)},
                   {**self.bot, 'id': 'old', 'session_id': session(2)},
                   {**self.bot, 'id': 'main', 'session_id': session(3), 'principal': True},
                   {**self.bot, 'id': 'new', 'session_id': session(4)}]
        self.registry.write_text(json.dumps({'bots': entries}))
        projects = self.root / 'config/projects/demo'
        projects.mkdir(parents=True)
        for n, stamp in ((2, 100), (3, 50), (4, 200)):
            path = projects / (session(n) + '.jsonl')
            path.touch()
            os.utime(path, (stamp, stamp))
        output = io.StringIO()
        env = {'CLAUDE_CONFIG_DIR': str(self.root / 'config')}
        with patch.dict(os.environ, env), patch.object(sys, 'argv', ['bots.py', 'list']), contextlib.redirect_stdout(output):
            self.assertEqual(bots.main(), 0)
        self.assertEqual([b['id'] for b in json.loads(output.getvalue())['bots']], ['main', 'new', 'old', 'never'])


if __name__ == '__main__':
    unittest.main()
