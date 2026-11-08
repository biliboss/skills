import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

INSTALL = Path(__file__).resolve().parents[1] / 'install.py'
LAYOUT = {'id': 'root', 'type': 'row', 'children': [{'id': 'panel', 'type': 'column', 'children': [
    {'id': 'panel-body', 'type': 'stack', 'children': [{'id': 'files', 'type': 'block'}, {'id': 'changes', 'type': 'block'}]}]}]}


def run(home):
    env = {**os.environ, 'HERDR_APP_HOME': str(home)}
    return subprocess.run([sys.executable, str(INSTALL), '--no-check'], env=env, text=True, capture_output=True)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / 'layouts').mkdir()
        for name in ('main', 'bili-bots'):
            (self.home / 'layouts' / f'{name}.json').write_text(json.dumps(LAYOUT))
        (self.home / 'keys.json').write_text(json.dumps({'global': {'cmd-q': 'app.quit'}, 'layout:bili-bots': {'cmd-1': 'x'}}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_installs_only_the_canvas_child_and_binding_idempotently(self):
        first = run(self.home)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(f'Destination: {self.home} (HERDR_APP_HOME)', first.stdout)
        for name in ('main', 'bili-bots'):
            layout = json.loads((self.home / 'layouts' / f'{name}.json').read_text())
            body = layout['children'][0]['children'][0]
            self.assertEqual([c['id'] for c in body['children']], ['files', 'changes', 'canvas'])
            self.assertEqual(body['children'][2]['content'], {'mod': 'herdr-canvas'})
        keys = json.loads((self.home / 'keys.json').read_text())
        self.assertEqual(keys['layout:bili-bots'], {'cmd-1': 'x', 'cmd-alt-c': 'mod.open:herdr-canvas'})
        self.assertEqual(keys['global'], {'cmd-q': 'app.quit'})
        self.assertTrue(list(self.home.glob('keys.json.bak-canvas-*')))
        for f in ('main.js', 'blocks.js', 'store.js', 'notify.js', 'mod.json', 'canvas.svg'):
            self.assertTrue((self.home / 'mods/herdr-canvas' / f).exists(), f)
        backups = len(list(self.home.rglob('*.bak-canvas-*')))
        second = run(self.home)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(list(self.home.rglob('*.bak-canvas-*'))), backups)
        layout = json.loads((self.home / 'layouts/main.json').read_text())
        self.assertEqual(len(layout['children'][0]['children'][0]['children']), 3)

    def test_unset_home_names_default_destination(self):
        env = {k: v for k, v in os.environ.items() if k != 'HERDR_APP_HOME'}
        env['HOME'] = str(self.home / 'nohome')
        result = subprocess.run([sys.executable, str(INSTALL), '--no-check'], env=env, text=True, capture_output=True)
        self.assertIn('default (HERDR_APP_HOME unset)', result.stdout + result.stderr)
        self.assertIn('.config/herdr-app', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
