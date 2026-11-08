import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

CANVAS = Path(__file__).resolve().parent / 'canvas'


class CanvasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.folder = root / 'bot'
        self.folder.mkdir()
        (root / 'bots.json').write_text(json.dumps({'bots': [{'id': 'b1', 'name': 'B1', 'folder': str(self.folder)}]}))
        self.env = {**os.environ, 'CANVAS_BOTS': str(root / 'bots.json'), 'HOME': str(root / 'home')}
        (root / 'page.md').write_text('# T\n\ntexto\n')
        self.page = root / 'page.md'

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CANVAS), *args], env=self.env, text=True, capture_output=True)

    def test_publish_copies_page_and_writes_version(self):
        r = self.run_cli('publish', 'b1', str(self.page))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out['version'].startswith('sha1:'))
        self.assertEqual((self.folder / 'canvas/page.md').read_text(), '# T\n\ntexto\n')
        self.assertEqual((self.folder / 'canvas/version').read_text().strip(), out['version'])

    def test_publish_html_keeps_md(self):
        self.assertEqual(self.run_cli('publish', 'b1', str(self.page)).returncode, 0)
        html = self.page.with_name('p.html')
        html.write_text('<h1>T</h1>')
        r = self.run_cli('publish', 'b1', str(html))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out['page'].endswith('canvas/page.html'))
        self.assertEqual((self.folder / 'canvas/page.html').read_text(), '<h1>T</h1>')
        self.assertEqual((self.folder / 'canvas/page.md').read_text(), '# T\n\ntexto\n')
        self.assertEqual((self.folder / 'canvas/version').read_text().strip(), out['version'])

    def test_refusals_go_to_stderr(self):
        r = self.run_cli('publish', 'nope', str(self.page))
        self.assertEqual(r.returncode, 1)
        self.assertIn('unknown bot', r.stderr)
        self.assertEqual(r.stdout, '')
        r = self.run_cli('publish', 'b1', str(self.page.with_suffix('.txt')))
        self.assertEqual(r.returncode, 1)
        # Unknown bot is refused before anything touches the Herdr window.
        self.assertEqual(self.run_cli('open', 'nope').returncode, 1)

    def test_comments_and_resolve(self):
        canvas = self.folder / 'canvas'
        canvas.mkdir()
        entry = {'id': 'c_1', 'resolved': None, 'body': {'value': 'corta'}, 'target': {'index': 2, 'heading': ['T'], 'selector': [{'exact': 'texto'}]}}
        (canvas / 'comments.jsonl').write_text(json.dumps(entry) + '\n')
        listed = json.loads(self.run_cli('comments', 'b1').stdout)['comments']
        self.assertEqual(len(listed), 1)
        self.assertIsNone(listed[0]['resolved'])
        r = self.run_cli('resolve', 'b1', 'c_1')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNotNone(json.loads(self.run_cli('comments', 'b1').stdout)['comments'][0]['resolved'])
        self.assertIn('Resolvidos (1)', (canvas / 'comments.md').read_text())
        self.assertIn('~~`c_1`', self.run_cli('comments', 'b1', '--md').stdout)
        self.assertEqual(self.run_cli('resolve', 'b1', 'c_zzz').returncode, 1)


if __name__ == '__main__':
    unittest.main()
