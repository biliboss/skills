import json, re, subprocess, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from testkit import CANVAS, Sandbox  # noqa: E402

DOC = '# Proposta\n\n## Assinatura\n\nTexto **forte** e `código` com [link](https://exemplo.com).\n\n- a\n- b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```js\nconst x = 1;\n```\n\n> citação\n\n---\n'


class CanvasTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.page = self.sb.md(DOC)

    def tearDown(self):
        self.sb.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CANVAS), *args], env=self.sb.env, text=True, capture_output=True)

    def ok(self, *args):
        r = self.cli(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def html(self):
        return (self.sb.canvas / 'page.html').read_text()

    # ---- render
    def test_publish_md_renders_blocks_with_ids_comment_button_theme_and_no_external_http(self):
        out = self.ok('publish', 'b1', str(self.page))
        self.assertTrue(out['version'].startswith('sha1:'))
        self.assertEqual((self.sb.canvas / 'page.md').read_text(), DOC)
        self.assertEqual((self.sb.canvas / 'version').read_text().strip(), out['version'])
        page = self.html()
        ids = re.findall(r'data-block="(cv-[0-9a-f]{6})"', page)
        self.assertEqual(len(ids), out['blocks'])
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(page.count('class="btn btn-xs btn-ghost cv-comment"'), len(ids))
        self.assertIn('data-theme="light"', page)
        self.assertIn('<strong>forte</strong>', page)
        self.assertIn('<h2 class="cv-h2">Assinatura</h2>', page)
        self.assertIn('<th>A</th>', page)
        self.assertIn('data-lang="js"', page)
        self.assertIn('--color-base-100', page)                  # the vendored daisyUI theme is inline
        # nothing is fetched: no <link>, no src= to a network URL, no @import, no url(http...)
        self.assertNotRegex(page, r'<link\b|\bsrc=["\']?(https?:)?//|@import|url\(\s*["\']?https?:')
        self.assertEqual(re.findall(r'(?:src|href)="(https?://[^"]*)"', page), ['https://exemplo.com'])   # the author's own link only
        self.assertNotIn('cdn.', page)

    def test_markdown_is_escaped(self):
        self.page.write_text('# T\n\n<script>alert(1)</script> [x](javascript:alert(1))\n')
        self.ok('publish', 'b1', str(self.page))
        page = self.html()
        self.assertNotIn('<script>alert', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('href="javascript', page)

    def test_publish_html_splits_top_level_blocks_and_wraps_loose_text(self):
        src = self.sb.md('<h1>Oi</h1>\ntexto solto\n<div class="alert alert-info"><p>a</p><p>b</p></div>\n<hr>\n', 'p.html')
        out = self.ok('publish', 'b1', str(src))
        self.assertEqual(out['blocks'], 4)
        names = sorted(p.name for p in (self.sb.canvas / 'blocks').iterdir())
        self.assertEqual(names, ['001.html', '002.html', '003.html', '004.html'])
        self.assertEqual((self.sb.canvas / 'blocks/003.html').read_text(), '<div class="alert alert-info"><p>a</p><p>b</p></div>')
        self.assertEqual(len(re.findall(r'data-kind="html"', self.html())), 4)
        self.assertFalse((self.sb.canvas / 'page.md').exists())
        self.assertEqual((self.sb.canvas / 'source').read_text().strip(), 'html')

    def test_unbalanced_html_is_one_block(self):
        src = self.sb.md('<div><p>aberto\n<p>outro</div>\n<span>x', 'p.html')
        self.assertEqual(self.ok('publish', 'b1', str(src))['blocks'], 1)

    def test_html_with_script_or_handlers_is_refused(self):
        for bad in ('<script>1</script>', '<img src=x onerror=alert(1)>', '<a href="javascript:1">x</a>', '<iframe src=x></iframe>'):
            r = self.cli('publish', 'b1', str(self.sb.md(bad, 'bad.html')))
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn('refused', r.stderr)
        self.assertFalse((self.sb.canvas / 'page.html').exists())

    def test_republish_md_after_html_drops_blocks(self):
        self.ok('publish', 'b1', str(self.sb.md('<p>x</p>', 'p.html')))
        self.ok('publish', 'b1', str(self.page))
        self.assertFalse((self.sb.canvas / 'blocks').exists())
        self.assertTrue((self.sb.canvas / 'page.md').exists())

    # ---- set / append / remove / show / version
    def test_show_lists_blocks(self):
        self.ok('publish', 'b1', str(self.page))
        shown = self.ok('show', 'b1')
        self.assertEqual([b['kind'] for b in shown['blocks']], ['heading', 'heading', 'paragraph', 'list', 'table', 'code', 'quote', 'hr'])
        self.assertEqual(shown['blocks'][0]['preview'], '# Proposta')
        self.assertEqual(shown['source'], 'md')
        self.assertEqual(shown['version'], (self.sb.canvas / 'version').read_text().strip())

    def test_set_append_remove_edit_page_md_page_html_and_bump_version(self):
        v0 = self.ok('publish', 'b1', str(self.page))['version']
        blocks = self.ok('show', 'b1')['blocks']
        newtext = self.sb.md('Texto **novo**', 'n.md')
        out = self.ok('set', 'b1', blocks[2]['id'], str(newtext))
        self.assertEqual(out['replaced'], blocks[2]['id'])
        self.assertNotEqual(out['version'], v0)
        self.assertIn('Texto **novo**', (self.sb.canvas / 'page.md').read_text())
        self.assertIn('<strong>novo</strong>', self.html())
        self.assertNotIn('<strong>forte</strong>', self.html())
        self.assertEqual((self.sb.canvas / 'version').read_text().strip(), out['version'])
        self.assertEqual(out['blocks'], len(blocks))
        # the number works as a reference too, and ids before the edit stay
        ids_after = [b['id'] for b in self.ok('show', 'b1')['blocks']]
        self.assertEqual(ids_after[:2], [b['id'] for b in blocks[:2]])
        added = self.ok('append', 'b1', str(self.sb.md('## Fim\n', 'a.md')))
        self.assertEqual(added['blocks'], len(blocks) + 1)
        self.assertEqual(len(added['added']), 1)
        self.assertIn('<h2 class="cv-h2">Fim</h2>', self.html())
        gone = self.ok('remove', 'b1', '2')
        self.assertEqual(gone['blocks'], len(blocks))
        self.assertNotIn('Assinatura', (self.sb.canvas / 'page.md').read_text())
        self.assertNotEqual(gone['version'], added['version'])

    def test_html_source_set_append_remove(self):
        self.ok('publish', 'b1', str(self.sb.md('<h1>A</h1><p>B</p><p>C</p>', 'p.html')))
        ids = [b['id'] for b in self.ok('show', 'b1')['blocks']]
        self.ok('set', 'b1', ids[1], str(self.sb.md('<p class="x">B2</p><p>B3</p>', 'n.html')))
        self.assertEqual(self.ok('show', 'b1')['blocks'][1]['preview'], '<p class="x">B2</p>')
        self.assertEqual(len(list((self.sb.canvas / 'blocks').iterdir())), 4)
        self.ok('append', 'b1', str(self.sb.md('<p>Z</p>', 'z.html')))
        self.ok('remove', 'b1', '1')
        self.assertEqual([b['preview'] for b in self.ok('show', 'b1')['blocks']][0], '<p class="x">B2</p>')
        self.assertEqual(len(list((self.sb.canvas / 'blocks').iterdir())), 4)
        self.assertNotIn('<h1>A</h1>', self.html())
        # an md file on an html canvas is refused, and so is a bad block reference
        self.assertEqual(self.cli('append', 'b1', str(self.sb.md('x', 'x.md'))).returncode, 1)
        self.assertEqual(self.cli('remove', 'b1', 'cv-nope').returncode, 1)

    def test_edit_before_publish_is_refused(self):
        r = self.cli('remove', 'b1', '1')
        self.assertEqual(r.returncode, 1)
        self.assertIn('publish first', r.stderr)

    def test_verbs_leave_no_temp_files(self):
        self.ok('publish', 'b1', str(self.page))
        self.ok('append', 'b1', str(self.sb.md('x', 'a.md')))
        self.assertEqual([p.name for p in self.sb.canvas.iterdir() if '.tmp' in p.name], [])

    # ---- comments, refusals
    def test_refusals_go_to_stderr(self):
        r = self.cli('publish', 'nope', str(self.page))
        self.assertEqual(r.returncode, 1)
        self.assertIn('unknown bot', r.stderr)
        self.assertEqual(r.stdout, '')
        self.assertEqual(self.cli('publish', 'b1', str(self.page.with_suffix('.txt'))).returncode, 1)
        self.assertEqual(self.cli('open', 'nope').returncode, 1)
        self.assertEqual(self.sb.herdr_calls(), [])     # unknown bot is refused before anything touches Herdr

    def test_comments_and_resolve(self):
        self.sb.canvas.mkdir()
        entry = {'id': 'c_1', 'resolved': None, 'body': {'value': 'corta'}, 'target': {'index': 2, 'heading': ['T'], 'selector': [{'exact': 'texto'}]}}
        (self.sb.canvas / 'comments.jsonl').write_text(json.dumps(entry) + '\n')
        listed = self.ok('comments', 'b1')['comments']
        self.assertEqual(len(listed), 1)
        self.assertIsNone(listed[0]['resolved'])
        self.ok('resolve', 'b1', 'c_1')
        self.assertIsNotNone(self.ok('comments', 'b1')['comments'][0]['resolved'])
        self.assertIn('Resolvidos (1)', (self.sb.canvas / 'comments.md').read_text())
        self.assertIn('~~`c_1`', self.cli('comments', 'b1', '--md').stdout)
        self.assertEqual(self.cli('resolve', 'b1', 'c_zzz').returncode, 1)

    # ---- open
    def test_open_runs_select_then_show_with_the_target_home_and_nothing_else(self):
        out = self.ok('open', 'b1')
        self.assertTrue(out['opened'])
        calls = self.sb.herdr_calls()
        self.assertEqual([c['argv'] for c in calls], [
            ['do', 'layout.select', '--stack', 'panel-body', '--child', 'canvas'],
            ['do', 'layout.show', '--id', 'panel']])
        self.assertEqual({c['home'] for c in calls}, {str(self.sb.home / '.config/herdr-bili')})
        self.assertTrue(all('pane.split' not in ' '.join(c['argv']) and 'focus' not in ' '.join(c['argv']) for c in calls))
        self.assertTrue((self.sb.home / '.local/state/herdr-canvas/bot').read_text().startswith('b1\t'))

    def test_open_starts_the_server_before_the_layout_calls(self):
        out = self.ok('open', 'b1')
        self.assertTrue(out['server']['running'])
        self.assertTrue(out['server']['started'])
        self.assertNotEqual(out['server']['port'], 47836)
        self.assertTrue(all(c['server_pid'] for c in self.sb.herdr_calls()))
        again = self.ok('open', 'b1')
        self.assertFalse(again['server']['started'])
        self.assertEqual(again['server']['pid'], out['server']['pid'])

    def test_open_goes_on_when_the_server_fails(self):
        self.sb.env['CANVAS_PORT'] = 'abc'
        out = self.ok('open', 'b1')
        self.assertTrue(out['opened'])
        self.assertFalse(out['server']['running'])
        self.assertIn('CANVAS_PORT', out['server']['error'])
        self.assertEqual(len(self.sb.herdr_calls()), 2)

    def test_open_uses_canvas_herdr_home(self):
        self.sb.env['CANVAS_HERDR_HOME'] = str(self.sb.root / 'other')
        self.ok('open', 'b1')
        self.assertEqual({c['home'] for c in self.sb.herdr_calls()}, {str(self.sb.root / 'other')})

    def test_open_failure_stops_before_show(self):
        self.sb.env['FAKE_HERDR_EXIT'] = '3'
        r = self.cli('open', 'b1')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.sb.herdr_calls()), 1)

    def test_cli_source_has_no_focus_or_split_command(self):
        text = '\n'.join(l for l in (Path(CANVAS).read_text()).splitlines() if not l.lstrip().startswith('#'))
        self.assertNotRegex(text, r'pane\.(focus|split|go)|agent\.focus|mod\.open|tab\.select|space\.select')


if __name__ == '__main__':
    unittest.main()
