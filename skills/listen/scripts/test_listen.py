#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bili-agents' / 'scripts'))
from bot_fixture import BotCase  # noqa: E402
import bots  # noqa: E402

FOREIGN = {'type': 'command', 'command': '/opt/other/hook.sh stop', 'timeout': 5}


class Listen(BotCase):
    def setUp(self):
        super().setUp()
        self.helper_folder = self.add_helper()
        self.settings = self.helper_folder / '.claude' / 'settings.json'

    def listen(self, *args, cwd=None, **env):
        return self.run_verb('listen', 'helper', *args, cwd=cwd or self.lead_folder, **env)

    def ok(self, *args, **kwargs):
        result = self.listen(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def hooks(self):
        return json.loads(self.settings.read_text()).get('hooks', {})

    def own(self, event, listener='lead'):
        key = bots.HOOK_EVENTS[event]
        return [h for g in self.hooks().get(key, []) for h in g['hooks']
                if bots.notifier_target(h) == (listener, event)]

    def test_registers_both_events_for_the_bot_in_cwd(self):
        out = self.ok()
        self.assertEqual((out['target'], out['listener'], out['events'], out['listening']),
                         ('helper', 'lead', ['stop', 'notification'], True))
        self.assertEqual(out['settings'], str(self.settings))
        self.assertFalse(out['needs_reload'])
        for event in ('stop', 'notification'):
            entries = self.own(event)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['command'], f'{bots.NOTIFIER} lead {event}')
            self.assertTrue(Path(bots.NOTIFIER).is_absolute())
            self.assertTrue(Path(bots.NOTIFIER).exists())

    def test_creates_settings_when_missing(self):
        self.assertFalse(self.settings.parent.exists())
        self.ok()
        self.assertTrue(self.settings.exists())
        self.assertEqual(set(self.hooks()), {'Stop', 'Notification'})

    def test_merges_with_foreign_hooks_and_other_keys(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({
            'permissions': {'allow': ['Read']}, 'outputStyle': 'X',
            'hooks': {'Stop': [{'hooks': [FOREIGN]}], 'PreToolUse': [{'matcher': 'Bash', 'hooks': [FOREIGN]}]}}))
        self.ok()
        data = json.loads(self.settings.read_text())
        self.assertEqual(data['permissions'], {'allow': ['Read']})
        self.assertEqual(data['outputStyle'], 'X')
        self.assertEqual(data['hooks']['PreToolUse'], [{'matcher': 'Bash', 'hooks': [FOREIGN]}])
        self.assertEqual(data['hooks']['Stop'][0], {'hooks': [FOREIGN]})
        self.assertEqual(len(self.own('stop')), 1)
        self.assertEqual(len(self.own('notification')), 1)

    def test_idempotent(self):
        self.ok()
        before = self.settings.read_text()
        self.ok()
        self.assertEqual(self.settings.read_text(), before)
        self.assertEqual(len(self.own('stop')), 1)
        self.assertEqual(len(self.own('notification')), 1)

    def test_replaces_stale_notifier_path(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({'hooks': {'Stop': [{'hooks': [
            {'type': 'command', 'command': '/old/checkout/ag-notify lead stop', 'timeout': 30}]}]}}))
        self.ok()
        self.assertEqual([h['command'] for h in self.own('stop')], [f'{bots.NOTIFIER} lead stop'])

    def test_off_removes_only_this_listener(self):
        self.settings.parent.mkdir()
        other = {'type': 'command', 'command': f'{bots.NOTIFIER} other stop', 'timeout': 30}
        self.settings.write_text(json.dumps({'model': 'opus', 'hooks': {
            'Stop': [{'hooks': [FOREIGN]}, {'hooks': [other]}], 'Notification': [{'hooks': [FOREIGN]}]}}))
        self.ok()
        out = self.ok('--off')
        self.assertFalse(out['listening'])
        self.assertEqual(self.own('stop'), [])
        self.assertEqual(self.own('notification'), [])
        data = json.loads(self.settings.read_text())
        self.assertEqual(data['model'], 'opus')
        self.assertEqual(data['hooks']['Stop'], [{'hooks': [FOREIGN]}, {'hooks': [other]}])
        self.assertEqual(data['hooks']['Notification'], [{'hooks': [FOREIGN]}])

    def test_off_leaves_no_empty_hooks_object(self):
        self.ok()
        self.ok('--off')
        self.assertEqual(json.loads(self.settings.read_text()), {})

    def test_events_filter(self):
        out = self.ok('--events', 'stop')
        self.assertEqual(out['events'], ['stop'])
        self.assertEqual(len(self.own('stop')), 1)
        self.assertNotIn('Notification', self.hooks())
        self.assertEqual(self.listen('--events', 'bogus').returncode, 1)

    def test_listener_resolution(self):
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        result = self.listen(cwd=elsewhere)
        self.assertEqual(result.returncode, 1)
        self.assertIn('--as', result.stderr)
        self.assertFalse(self.settings.exists())
        self.assertEqual(self.ok('--as', 'lead', cwd=elsewhere)['listener'], 'lead')
        self.assertEqual(self.listen('--as', 'ghost', cwd=elsewhere).returncode, 1)
        self.assertEqual(self.listen('--as', 'helper').returncode, 1)
        self.assertEqual(self.run_verb('listen', 'ghost', cwd=self.lead_folder).returncode, 1)

    def test_needs_reload_when_target_is_live(self):
        self.terminals.write_text(json.dumps({'terminals': [
            {'state': 'live', 'address': 'a', 'name': bots.identity(self.bot('helper'))}]}))
        out = self.ok()
        self.assertTrue(out['needs_reload'])
        self.assertIsNone(self.ok(HC_FAIL='1')['target_live'])

    def test_refuses_broken_settings(self):
        self.settings.parent.mkdir()
        self.settings.write_text('{not json')
        self.assertEqual(self.listen().returncode, 1)
        self.assertEqual(self.settings.read_text(), '{not json')

    def test_does_not_change_registry(self):
        before = self.registry.read_text()
        self.ok()
        self.assertEqual(self.registry.read_text(), before)

    def test_roster_reports_listeners(self):
        self.ok()
        result = self.run_verb('roster')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = {row['id']: row['listeners'] for row in json.loads(result.stdout)['bots']}
        self.assertEqual(rows, {'lead': [], 'helper': ['lead']})


if __name__ == '__main__':
    unittest.main()
