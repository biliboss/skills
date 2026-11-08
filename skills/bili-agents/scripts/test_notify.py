#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot_fixture import BotCase, HELPER, LEAD  # noqa: E402
import bots  # noqa: E402

loader = importlib.machinery.SourceFileLoader('ag_notify', str(Path(__file__).with_name('ag-notify')))
notify = importlib.util.module_from_spec(importlib.util.spec_from_loader('ag_notify', loader))
loader.exec_module(notify)

NBSP = ' '
TRANSCRIPT = '❯ an older prompt the owner sent\n\n⏺ Done.\n\n'


class PromptEmpty(unittest.TestCase):
    def test_bare_prompt(self):
        self.assertTrue(notify.prompt_empty('❯'))
        self.assertTrue(notify.prompt_empty('❯ '))
        self.assertTrue(notify.prompt_empty('❯' + NBSP))
        self.assertTrue(notify.prompt_empty(f'❯ {NBSP} \n'))

    def test_typed_text(self):
        self.assertFalse(notify.prompt_empty('❯ hello'))
        self.assertFalse(notify.prompt_empty('❯' + NBSP + 'x'))

    def test_last_prompt_line_decides(self):
        self.assertTrue(notify.prompt_empty(TRANSCRIPT + '❯' + NBSP + '\n  ? for shortcuts'))
        self.assertFalse(notify.prompt_empty(TRANSCRIPT + '❯ typing now'))

    def test_no_prompt_line(self):
        self.assertFalse(notify.prompt_empty(''))
        self.assertFalse(notify.prompt_empty('Compacting conversation...\nworking'))


class Terminals(unittest.TestCase):
    lead = {'id': 'lead', 'name': 'Lead', 'folder': '/tmp/lead', 'session_id': LEAD, 'command': ['x']}
    helper = {'id': 'helper', 'name': 'Helper', 'folder': '/tmp/helper', 'session_id': HELPER, 'command': ['x']}

    def fake_call(self, terminals, cwds):
        def call(argv):
            if argv[:3] == ['hc', 'ls', '--json']:
                return {'terminals': terminals}
            if argv[:2] == ['hc', 'get']:
                return {'cwd': cwds.get(argv[2])}
            raise AssertionError(argv)
        return patch.object(bots, 'call', side_effect=call)

    def test_registered_name_first(self):
        terminals = [{'address': 't1', 'state': 'live', 'name': ''},
                     {'address': 't2', 'state': 'live', 'name': bots.identity(self.lead)}]
        with self.fake_call(terminals, {'t1': '/tmp/lead'}):
            self.assertEqual(notify.listener_terminal(self.lead), 't2')

    def test_folder_fallback_skips_dead_terminals(self):
        terminals = [{'address': 't1', 'state': 'exited', 'name': bots.identity(self.lead)},
                     {'address': 't2', 'state': 'live', 'name': ''},
                     {'address': 't3', 'state': 'live', 'name': ''}]
        with self.fake_call(terminals, {'t2': '/tmp/other', 't3': '/tmp/lead'}):
            self.assertEqual(notify.listener_terminal(self.lead), 't3')
        with self.fake_call(terminals, {'t2': '/tmp/other', 't3': '/tmp/other'}):
            self.assertIsNone(notify.listener_terminal(self.lead))

    def test_target_by_session_then_cwd(self):
        registry = [self.lead, self.helper]
        self.assertEqual(notify.target_bot(registry, {'session_id': HELPER})['id'], 'helper')
        self.assertEqual(notify.target_bot(registry, {'session_id': 'x', 'cwd': '/tmp/lead'})['id'], 'lead')
        self.assertIsNone(notify.target_bot(registry, {'cwd': '/tmp/nowhere'}))

    def test_compose(self):
        payload = {'session_id': HELPER, 'message': 'Claude needs  your\npermission'}
        text = notify.compose(self.helper, 'notification', payload, 't9')
        self.assertEqual(text, f'<hook from="helper">Helper: precisa de alguém (sessão {HELPER[:8]}). '
                               'Claude needs your permission. Leia com hc read t9.</hook>')
        self.assertEqual(notify.compose(self.helper, 'stop', {'session_id': HELPER}),
                         f'<hook from="helper">Helper: terminou o turno (sessão {HELPER[:8]}). '
                         'Leia com hc read da aba do Helper.</hook>')
        self.assertIn('from="stray"', notify.compose(None, 'stop', {'cwd': '/tmp/stray'}))
        self.assertNotIn('\n', notify.compose(self.helper, 'stop', {'message': 'a\nb\n'}))

    def test_deliver_waits_for_empty_prompt_then_sends(self):
        screens = iter(['❯ typing', '❯ still', '❯' + NBSP])
        sent = []
        clock = iter(range(0, 1000, 5))
        with patch.object(notify, 'read_screen', side_effect=lambda a: next(screens)), \
                patch.object(notify.subprocess, 'run', side_effect=lambda argv, **k: sent.append(argv)):
            self.assertTrue(notify.deliver('t1', '<hook/>', sleep=lambda s: None, clock=lambda: next(clock)))
        self.assertEqual(sent, [['hc', 'send', 't1', '<hook/>']])

    def test_deliver_gives_up_without_sending(self):
        clock = iter(range(0, 10000, 100))
        with patch.object(notify, 'read_screen', return_value='❯ owner is typing'), \
                patch.object(notify.subprocess, 'run') as run:
            self.assertFalse(notify.deliver('t1', '<hook/>', sleep=lambda s: None, clock=lambda: next(clock)))
        run.assert_not_called()


class Hook(BotCase):
    """ag-notify as Claude Code runs it: stdin JSON, the registry from the environment, a fake hc."""

    def run_hook(self, *args, payload=None, **env):
        return subprocess.run([sys.executable, str(Path(__file__).with_name('ag-notify')), *args],
                              input=json.dumps(payload or {}), capture_output=True, text=True,
                              env={**self.env, 'AG_NOTIFY_FOREGROUND': '1', **env})

    def test_silent_without_a_listener_terminal(self):
        self.add_helper()
        result = self.run_hook('lead', 'stop', payload={'session_id': HELPER})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_silent_when_hc_fails_or_listener_is_unknown(self):
        self.assertEqual(self.run_hook('lead', 'stop', HC_FAIL='1').returncode, 0)
        self.assertEqual(self.run_hook('ghost', 'stop').returncode, 0)
        self.assertEqual(self.run_hook('lead', 'bogus').returncode, 2)

    def test_sends_when_the_prompt_is_empty(self):
        self.add_helper()
        log = self.root / 'hc.log'
        fake = self.root / 'bin' / 'hc'
        fake.write_text('#!/bin/sh\n'
                        'echo "$@" >> "$HC_LOG"\n'
                        'if [ "$1" = ls ]; then cat "$HC_TERMINALS"; fi\n'
                        'if [ "$1" = read ]; then printf "%s" "$HC_SCREEN"; fi\n')
        self.terminals.write_text(json.dumps({'terminals': [
            {'state': 'live', 'address': 't7', 'name': bots.identity(self.bot('lead'))}]}))
        result = self.run_hook('lead', 'stop', payload={'session_id': HELPER, 'message': 'all done'},
                               HC_LOG=str(log), HC_SCREEN='❯ ' + NBSP)
        self.assertEqual(result.returncode, 0, result.stderr)
        sent = [line for line in log.read_text().splitlines() if line.startswith('send ')]
        self.assertEqual(sent, [f'send t7 <hook from="helper">Helper: terminou o turno (sessão {HELPER[:8]}). '
                                'all done. Leia com hc read da aba do Helper.</hook>'])


if __name__ == '__main__':
    unittest.main()
