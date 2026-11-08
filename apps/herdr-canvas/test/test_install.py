import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

INSTALL = Path(__file__).resolve().parents[1] / 'install.py'
LAYOUT = {'id': 'root', 'type': 'row', 'children': [{'id': 'panel', 'type': 'column', 'children': [
    {'id': 'panel-body', 'type': 'stack', 'children': [{'id': 'files', 'type': 'block'}, {'id': 'changes', 'type': 'block'}]}]}]}
TABS_ORIGINAL = '''    const enabled = shared("workspace.panels") ?? ["files", "changes"];
    this.syncPanel(space, panel, body, enabled);
      .when(enabled.includes("files"), el => el.child(panelButton("files", "Files", "mods/files/file.svg")))
      .when(enabled.includes("changes"), el => el.child(panelButton("changes", "Changes", "mods/changes/changes.svg")))
      .when(w?.buttons, el => el.child(button("minimize")))
'''
TABS_BROWSER = TABS_ORIGINAL.replace('const enabled = shared("workspace.panels") ?? ["files", "changes"];',
                                     'const enabled = [...(shared("workspace.panels") ?? ["files", "changes"]), "browser"];').replace(
    '      .when(w?.buttons', '      .child(panelButton("browser", "Browser", "mods/tabs/globe.svg"))\n      .when(w?.buttons')
BUTTON = '.child(panelButton("canvas", "Canvas", "mods/herdr-canvas/canvas.svg"))'
REAL_TABS = Path.home() / '.config/herdr-bili/mods/tabs/main.js'


def run(home, *extra, env=None):
    e = {**os.environ, **({'HERDR_APP_HOME': str(home)} if home else {}), **(env or {})}
    if not home:
        e.pop('HERDR_APP_HOME', None)
    return subprocess.run([sys.executable, str(INSTALL), '--no-check', *extra], env=e, text=True, capture_output=True)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / 'layouts').mkdir()
        (self.home / 'mods/tabs').mkdir(parents=True)
        for name in ('main', 'bili-bots'):
            (self.home / 'layouts' / f'{name}.json').write_text(json.dumps(LAYOUT))
        (self.home / 'keys.json').write_text(json.dumps({'global': {'cmd-q': 'app.quit'}, 'layout:bili-bots': {'cmd-1': 'x'}}))
        self.tabs = self.home / 'mods/tabs/main.js'
        self.tabs.write_text(TABS_BROWSER)

    def tearDown(self):
        self.tmp.cleanup()

    def test_installs_child_button_and_binding_idempotently(self):
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
        for f in ('main.js', 'blocks.js', 'store.js', 'notify.js', 'pagemode.js', 'mod.json', 'canvas.svg'):
            self.assertTrue((self.home / 'mods/herdr-canvas' / f).exists(), f)
        self.assertEqual(len(list(self.home.rglob('*.bak-canvas-*'))), 4)   # 2 layouts, keys, tabs
        patched = self.tabs.read_text()
        self.assertIn('"browser", "canvas"];', patched)
        lines = patched.split('\n')
        at = next(i for i, l in enumerate(lines) if BUTTON in l)
        self.assertIn('panelButton("browser"', lines[at - 1])
        self.assertEqual(patched.count(BUTTON), 1)
        second = run(self.home)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('already has the Canvas button', second.stdout)
        self.assertEqual(len(list(self.home.rglob('*.bak-canvas-*'))), 4)
        self.assertEqual(self.tabs.read_text(), patched)
        self.assertEqual(len(json.loads((self.home / 'layouts/main.json').read_text())['children'][0]['children'][0]['children']), 3)

    def test_tabs_without_browser_patch_gets_canvas_after_changes(self):
        self.tabs.write_text(TABS_ORIGINAL)
        self.assertEqual(run(self.home).returncode, 0)
        patched = self.tabs.read_text()
        self.assertIn('const enabled = [...(shared("workspace.panels") ?? ["files", "changes"]), "canvas"];', patched)
        lines = patched.split('\n')
        self.assertIn('panelButton("changes"', lines[next(i for i, l in enumerate(lines) if BUTTON in l) - 1])

    def test_missing_anchor_changes_nothing(self):
        self.tabs.write_text('export default class Tabs {}\n')
        r = run(self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn('anchor', r.stderr)
        self.assertFalse((self.home / 'mods/herdr-canvas').exists())
        self.assertEqual(list(self.home.rglob('*.bak-canvas-*')), [])
        self.assertEqual(json.loads((self.home / 'layouts/main.json').read_text()), LAYOUT)
        self.assertEqual(self.tabs.read_text(), 'export default class Tabs {}\n')

    def test_missing_tabs_file_errors_unless_skipped(self):
        self.tabs.unlink()
        r = run(self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--skip-tabs', r.stderr)
        self.assertFalse((self.home / 'mods/herdr-canvas').exists())
        self.assertEqual(run(self.home, '--skip-tabs').returncode, 0)

    def test_unset_home_is_refused_and_writes_nothing(self):
        official = self.home / 'fakehome'
        (official / '.config/herdr-app').mkdir(parents=True)
        r = run(None, env={'HOME': str(official)})
        self.assertEqual(r.returncode, 1)
        self.assertIn('HERDR_APP_HOME is not set', r.stderr)
        self.assertEqual(list((official / '.config/herdr-app').iterdir()), [])

    @unittest.skipUnless(REAL_TABS.exists() and shutil.which('node'), 'needs the Herdr Bili tabs mod to read and node')
    def test_patch_on_a_copy_of_the_real_tabs_mod_is_valid_js(self):
        self.tabs.write_text(REAL_TABS.read_text())
        self.assertEqual(run(self.home).returncode, 0)
        copy = self.home / 'check.mjs'
        shutil.copy(self.tabs, copy)
        r = subprocess.run(['node', '--check', str(copy)], text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.tabs.read_text().count(BUTTON), 1)


if __name__ == '__main__':
    unittest.main()
