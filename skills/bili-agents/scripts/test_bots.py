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

    def test_only_terminal_gets_the_labels_enviar_needs_and_split_does_not(self):
        for terminals, expected in (([{'terminal': 't1'}], True), ([{'terminal': 't1'}, {'terminal': 't2'}], False)):
            calls = []
            def call(argv):
                calls.append(argv)
                if argv == ['herdr-app', 'ls']:
                    return {'spaces': [{'id': 'bot-real', 'name': 'Test', 'folder': str(self.root),
                                        'tabs': [{'id': 'tab', 'name': 'Test', 'terminals': terminals}]}]}
                return {}
            with patch.object(bots, 'call', side_effect=call), contextlib.redirect_stdout(io.StringIO()):
                bots.open_bot(self.bot)
            self.assertEqual(any(c[:2] == ['hc', 'label'] for c in calls), expected)
            self.assertFalse(any('agent.focus' in c or 'space.select' in c for c in calls))

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

    def ws(self, terminals, sid=None, folder=None):
        return {'id': sid or 'bot-real', 'name': 'x', 'folder': folder or str(self.root),
                'tabs': [{'id': 'tab0', 'terminals': terminals}]}

    def run_list(self, side_effect):
        with patch.object(bots, 'call', side_effect=side_effect), patch.object(sys, 'argv', ['bots.py', 'list']), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bots.main(), 0)
        return json.loads(out.getvalue())['bots'][0]['space_id']

    def test_list_uses_folder_match_without_hc(self):
        calls = []
        def call(argv):
            calls.append(argv)
            return {'spaces': [self.ws([]), self.ws([], sid='other', folder='/elsewhere')]}
        self.assertEqual(self.run_list(call), 'bot-real')
        self.assertEqual(calls, [['herdr-app', 'ls']])

    def test_list_keeps_computed_id_without_workspace_or_on_error(self):
        def fail(argv):
            raise RuntimeError('herdr-app: down')
        for side_effect in (fail, lambda argv: {'spaces': [self.ws([], folder='/elsewhere')]}):
            self.assertEqual(self.run_list(side_effect), bots.space_id(self.bot))

    def test_two_spaces_same_folder_pick_deterministically(self):
        two = {'spaces': [self.ws([], sid='b'), self.ws([], sid='a')]}
        self.assertEqual(bots.workspace_of(self.bot, two)['id'], 'a')
        computed = {'spaces': [*two['spaces'], self.ws([], sid=bots.space_id(self.bot))]}
        self.assertEqual(bots.workspace_of(self.bot, computed)['id'], bots.space_id(self.bot))

    def open_in_workspace(self, terminals, labels=None, focus=False, ls=None):
        calls = []
        layout = {'spaces': [self.ws(terminals)]}
        def call(argv):
            calls.append(argv)
            if argv == ['herdr-app', 'ls']:
                return layout
            if argv[:2] == ['hc', 'get']:
                result = (labels or {}).get(argv[2], {})
                if isinstance(result, Exception):
                    raise result
                return {'labels': result}
            if argv[:2] == ['hc', 'ls']:
                return {'terminals': ls or []}
            if argv[:2] == ['hc', 'run']:
                return {'address': 'tnew'}
            return {}
        with patch.object(bots, 'call', side_effect=call), patch.object(bots.time, 'sleep'), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            bots.open_bot(self.bot, focus=focus)
        return calls, json.loads(out.getvalue())

    def test_two_unlabeled_terminals_pick_first_without_writes(self):
        calls, out = self.open_in_workspace([{'terminal': 't63'}, {'terminal': 't64'}])
        self.assertEqual(out['terminal'], 't63')
        self.assertFalse(any(c[:2] in (['hc', 'label'], ['hc', 'run']) for c in calls))
        self.assertEqual(self.moves_focus(calls), [])

    def test_name_beats_label_beats_first(self):
        terminals = [{'terminal': 't1'}, {'terminal': 't2'}, {'terminal': 't3', 'name': bots.identity(self.bot)}]
        labels = {'t2': {'bili.bot': 'test'}}
        self.assertEqual(self.open_in_workspace(terminals, labels)[1]['terminal'], 't3')
        self.assertEqual(self.open_in_workspace(terminals[:2], labels)[1]['terminal'], 't2')
        self.assertEqual(self.open_in_workspace(terminals[:2])[1]['terminal'], 't1')

    def test_label_lookup_skips_errors_and_ignores_session(self):
        terminals = [{'terminal': 't1'}, {'terminal': 't2'}]
        labels = {'t1': RuntimeError('gone'), 't2': {'bili.bot': 'test', 'bili.session': 'stale'}}
        self.assertEqual(self.open_in_workspace(terminals, labels)[1]['terminal'], 't2')

    def test_focus_true_focuses_the_chosen_terminal(self):
        calls, _ = self.open_in_workspace([{'terminal': 't63'}, {'terminal': 't64'}], focus=True)
        self.assertIn(['herdr-app', 'do', 'agent.focus', json.dumps({'terminal': 't63'})], calls)

    def test_no_workspace_and_no_parked_terminal_creates(self):
        calls = self.exercise_open([], live=False)
        run = next(c for c in calls if c[:2] == ['hc', 'run'])
        self.assertIn('herdr.space=' + bots.space_id(self.bot), run)

    def test_empty_workspace_creates_with_its_id(self):
        calls, out = self.open_in_workspace([])
        run = next(c for c in calls if c[:2] == ['hc', 'run'])
        self.assertIn('herdr.space=bot-real', run)
        self.assertIn('herdr.tab=bot-real-tab', run)
        self.assertEqual(out['terminal'], 'tnew')

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
