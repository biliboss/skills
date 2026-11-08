import http.client, json, os, signal, stat, subprocess, sys, threading, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from testkit import CANVAS, Sandbox  # noqa: E402

DOC = '# Proposta\n\ntexto um\n\ntexto dois\n'


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.sb.env['CANVAS_PORT'] = '0'          # ephemeral
        subprocess.run([sys.executable, str(CANVAS), 'publish', 'b1', str(self.sb.md(DOC))], env=self.sb.env, check=True, capture_output=True)
        self.proc = subprocess.Popen([sys.executable, str(CANVAS), 'serve'], env=self.sb.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        info = json.loads(self.proc.stdout.readline())
        self.port, self.state = info['port'], self.sb.home / '.local/state/herdr-canvas'
        self.token = (self.state / 'token').read_text().strip()
        self.origin = f'http://127.0.0.1:{self.port}'
        self.block = self.blocks()[2]

    def tearDown(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            self.proc.wait(timeout=10)
        self.proc.stdout.close()
        self.proc.stderr.close()
        self.sb.cleanup()

    def blocks(self):
        show = subprocess.run([sys.executable, str(CANVAS), 'show', 'b1'], env=self.sb.env, text=True, capture_output=True, check=True)
        return json.loads(show.stdout)['blocks']

    def req(self, method, path, body=None, headers=None, host=None, raw_len=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        c.putheader('Host', host or f'127.0.0.1:{self.port}')
        data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
        for k, v in (headers or {}).items():
            c.putheader(k, v)
        if data is not None:
            c.putheader('Content-Length', str(len(data) if raw_len is None else raw_len))
        c.endheaders(data)
        r = c.getresponse()
        out = (r.status, dict(r.getheaders()), r.read())
        c.close()
        return out

    def post(self, body, **over):
        headers = {'Origin': self.origin, 'X-Canvas-Token': self.token, 'Content-Type': 'application/json', **over.pop('headers', {})}
        headers = {k: v for k, v in headers.items() if v is not None}
        return self.req('POST', over.pop('path', '/b1/comments'), body, headers, **over)

    def valid(self, text='ajuste isto'):
        return {'blockId': self.block['id'], 'body': text}

    def lines(self):
        p = self.sb.canvas / 'comments.jsonl'
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def wait_for(self, fn, secs=8):
        end = time.time() + secs
        while time.time() < end:
            v = fn()
            if v:
                return v
            time.sleep(0.05)
        return fn()

    # ---- GET
    def test_get_serves_the_page_with_theme_token_and_existing_comments(self):
        self.assertEqual(self.post(self.valid('primeiro'))[0], 200)
        status, headers, body = self.req('GET', '/b1/?theme=dark')
        page = body.decode()
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers['Content-Type'])
        self.assertIn('<html lang="pt-BR" data-theme="dark">', page)
        self.assertIn(f'"token": "{self.token}"', page)
        self.assertIn('"post": "/b1/comments"', page)
        self.assertIn('"body": "primeiro"', page)
        self.assertIn(f'data-block="{self.block["id"]}"', page)
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        self.assertIn('data-theme="light"', self.req('GET', '/b1/?theme=evil"')[2].decode())     # unknown theme -> light
        self.assertEqual(self.req('GET', '/b1')[0], 200)
        self.assertEqual(self.req('GET', '/health')[2], b'ok')

    def test_token_file_is_0600_and_changes_per_process(self):
        self.assertEqual(stat.S_IMODE((self.state / 'token').stat().st_mode), 0o600)
        self.assertGreaterEqual(len(self.token), 32)

    # ---- POST
    def test_valid_post_writes_jsonl_markdown_and_messages_the_bot_with_argv(self):
        evil = 'troca $(touch /tmp/x) "aspas" `crase`; rm -rf ~\ncom quebra'
        status, _, body = self.post(self.valid(evil))
        self.assertEqual(status, 200, body)
        cid = json.loads(body)['id']
        (entry,) = self.lines()
        self.assertEqual(entry['id'], cid)
        self.assertEqual(entry['type'], 'Annotation')
        self.assertEqual(entry['body']['value'], evil)
        self.assertEqual(entry['target']['blockId'], self.block['id'])
        self.assertEqual(entry['target']['index'], 3)
        self.assertEqual(entry['target']['heading'], ['Proposta'])
        self.assertTrue(entry['target']['version'].startswith('sha1:'))
        md = (self.sb.canvas / 'comments.md').read_text()
        self.assertIn('## Abertos (1)', md)
        self.assertIn(cid, md)
        calls = self.wait_for(self.sb.hc_calls)
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertEqual(args[:2], ['send', 't9'])
        self.assertNotIn('--if', args)
        self.assertNotIn('--force', args)
        self.assertEqual(len(args), 3)                       # the whole message is one argv item
        self.assertTrue(args[2].startswith('[herdr-canvas] Novo comentário do dono no bloco 3 (Proposta).'))
        self.assertEqual(len(args[2].split('\n')), 4)
        self.assertIn('Comentário: troca $(touch /tmp/x) "aspas" `crase`; rm -rf ~ com quebra', args[2])
        self.assertIn(f'canvas resolve b1 {cid}', args[2])
        self.assertFalse(Path('/tmp/x').exists() and Path('/tmp/x').stat().st_mtime > time.time() - 60)
        log = self.wait_for(lambda: (self.sb.canvas / 'notify.log').exists() and (self.sb.canvas / 'notify.log').read_text())
        self.assertRegex(log, r't9 tentativa 1 enviado')

    def test_post_replies_before_the_bot_answers_and_retries_refused_sends(self):
        self.proc.send_signal(signal.SIGTERM)
        self.proc.wait(timeout=10)
        self.proc.stdout.close(); self.proc.stderr.close()
        self.sb.env['FAKE_HC_FAIL_FIRST'] = '1'
        self.setUpServer()
        t0 = time.time()
        self.assertEqual(self.post(self.valid())[0], 200)
        self.assertLess(time.time() - t0, 2)
        sends = self.wait_for(lambda: len(self.sb.hc_calls()) >= 2 and self.sb.hc_calls())
        self.assertEqual(len(sends), 2)                      # first refused (exit 1), second accepted
        log = self.wait_for(lambda: 'tentativa 2 enviado' in (self.sb.canvas / 'notify.log').read_text() and (self.sb.canvas / 'notify.log').read_text())
        self.assertIn('tentativa 1 recusado: busy', log)

    def _post_with_state(self, state):
        self.proc.send_signal(signal.SIGTERM)
        self.proc.wait(timeout=10)
        self.proc.stdout.close(); self.proc.stderr.close()
        self.sb.env['FAKE_HC_STATE'] = state
        self.setUpServer()
        self.assertEqual(self.post(self.valid())[0], 200)

    def notify_log(self, needle):
        f = self.sb.canvas / 'notify.log'
        return f.exists() and needle in f.read_text() and f.read_text()

    def sent(self):
        return [c for c in self.sb.hc_calls() if c[:1] == ['send']]

    def test_idle_and_done_bots_get_the_message_without_if(self):
        for state in ('idle', 'done'):
            with self.subTest(state=state):
                self.sb.hc_log.unlink(missing_ok=True)
                self._post_with_state(state)
                sends = self.wait_for(self.sent)
                self.assertEqual(sends[0][:2], ['send', 't9'])
                self.assertNotIn('--if', sends[0])
                self.assertNotIn('--force', sends[0])
                self.wait_for(lambda: self.notify_log('tentativa 1 enviado'))

    def test_working_bot_is_not_sent_to_and_is_retried_three_times(self):
        self._post_with_state('working')
        log = self.wait_for(lambda: self.notify_log('tentativa 3'))
        self.assertIn('tentativa 1 recusado: status working', log)
        self.assertEqual(self.sent(), [])

    def test_blocked_bot_is_not_sent_to(self):
        self._post_with_state('blocked')
        log = self.wait_for(lambda: self.notify_log('tentativa 1 recusado'))
        self.assertIn('status blocked', log)
        self.assertEqual(self.sent(), [])

    def setUpServer(self):
        self.proc = subprocess.Popen([sys.executable, str(CANVAS), 'serve'], env=self.sb.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        info = json.loads(self.proc.stdout.readline())
        self.port = info['port']
        self.token = (self.state / 'token').read_text().strip()
        self.origin = f'http://127.0.0.1:{self.port}'

    def test_refusals(self):
        before = len(self.lines())
        self.assertEqual(self.post(self.valid(), headers={'X-Canvas-Token': None})[0], 403)                 # no token
        self.assertEqual(self.post(self.valid(), headers={'X-Canvas-Token': 'x' * 43})[0], 403)             # wrong token
        self.assertEqual(self.post(self.valid(), headers={'Origin': 'http://evil.example'})[0], 403)        # wrong origin
        self.assertEqual(self.post(self.valid(), headers={'Origin': f'http://localhost:{self.port}'})[0], 403)
        self.assertEqual(self.post(self.valid(), headers={'Origin': None})[0], 403)                         # no origin
        self.assertEqual(self.post(self.valid(), host='evil.example')[0], 403)                              # DNS rebinding
        self.assertEqual(self.post(self.valid(), headers={'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.post(b'{not json')[0], 422)
        self.assertEqual(self.post({'blockId': self.block['id'], 'body': '   '})[0], 422)
        self.assertEqual(self.post({'blockId': 7, 'body': 'x'})[0], 422)
        self.assertEqual(self.post({'blockId': 'cv-000000', 'body': 'x'})[0], 404)                          # no such block
        self.assertEqual(self.post(self.valid(), path='/nope/comments')[0], 404)                            # bot not in bots.json
        self.assertEqual(self.post(self.valid(), path='/b1/other')[0], 404)
        self.assertEqual(self.lines(), [] if before == 0 else self.lines())
        self.assertEqual(len(self.lines()), before)
        self.assertEqual(self.sb.hc_calls(), [])

    def test_body_over_64_kib_is_refused_unread(self):
        status, _, _ = self.post(b'{"blockId":"' + b'a' * 70000 + b'","body":"x"}')
        self.assertEqual(status, 413)
        self.assertEqual(self.lines(), [])
        ok_big = self.post({'blockId': self.block['id'], 'body': 'x' * 4001})
        self.assertEqual(ok_big[0], 422)
        self.assertEqual(self.post(self.valid(), headers={'Content-Type': 'application/json; charset=utf-8'})[0], 200)

    def test_bot_and_path_come_only_from_the_registry(self):
        for path in ('/nope/', '/../', '/../etc/passwd', '/%2e%2e/', '/%2e%2e%2fetc/', '/b1/../b1/', '/b1/../../x', '/b1%2f..%2f', '/b1/page.html',
                     '/b1/canvas/page.html', '/b1/comments.jsonl', '/', '/index.html', '/%00', '/b1%00/'):
            status = self.req('GET', path)[0]
            self.assertIn(status, (404, 403), path)
        # a bot folder is never read through the URL: the registry is the only lookup
        self.assertEqual(self.req('GET', f'/{self.sb.folder}/')[0], 404)

    def test_concurrent_posts_are_serialised(self):
        n, results = 25, []
        lock = threading.Lock()

        def one(i):
            r = self.post(self.valid(f'comentário {i}'))
            with lock:
                results.append(r[0])
        threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results, [200] * n)
        lines = self.lines()                                    # every line parses: none interleaved
        self.assertEqual(len(lines), n)
        self.assertEqual(len({l['id'] for l in lines}), n)
        self.assertEqual(len({l['body']['value'] for l in lines}), n)
        self.assertIn(f'## Abertos ({n})', (self.sb.canvas / 'comments.md').read_text())

    def test_cli_comments_and_resolve_read_what_the_server_wrote(self):
        cid = json.loads(self.post(self.valid())[2])['id']
        out = subprocess.run([sys.executable, str(CANVAS), 'resolve', 'b1', cid], env=self.sb.env, text=True, capture_output=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('Resolvidos (1)', (self.sb.canvas / 'comments.md').read_text())
        self.assertNotIn('"body": "ajuste isto"', self.req('GET', '/b1/')[2].decode())     # resolved ones do not reach the page

    # ---- quote (comment mode)
    def selector(self, body):
        status, _, out = self.post(body)
        self.assertEqual(status, 200, out)
        return self.lines()[-1]['target']['selector'][0]

    def test_valid_quote_is_stored_in_the_selector_and_used_in_the_message(self):
        sel = self.selector({**self.valid(), 'quote': {'exact': 'texto  dois', 'prefix': 'x' * 50, 'suffix': ' fim'}})
        self.assertEqual(sel, {'type': 'TextQuoteSelector', 'exact': 'texto dois', 'prefix': 'x' * 32, 'suffix': ' fim'})
        calls = self.wait_for(self.sb.hc_calls)
        self.assertIn('> "texto dois"', calls[0][2])

    def test_quote_outside_the_block_falls_back_to_the_block_start_without_losing_the_comment(self):
        sel = self.selector({**self.valid(), 'quote': {'exact': 'frase de outro bloco', 'prefix': '', 'suffix': ''}})
        self.assertEqual(sel['exact'], 'texto dois')
        self.assertEqual(len(self.lines()), 1)

    def test_malformed_quotes_do_not_break_the_post(self):
        for i, bad in enumerate([None, 'texto', 7, [], {'exact': 5}, {'exact': ''}, {'exact': ' '}, {'exact': 'texto', 'prefix': 3},
                                 {'exact': 'x' * 5000}, {'prefix': 'a'}]):
            with self.subTest(bad=bad):
                sel = self.selector({**self.valid(f'c{i}'), 'quote': bad})
                self.assertEqual(sel['exact'], 'texto dois')
                self.assertEqual((sel['prefix'], sel['suffix']), ('', ''))

    def test_quote_with_inline_markdown_matches_the_rendered_text(self):
        doc = 'Abertura.\n\nO preço é **R$ 10** por [mês](https://x.com), com `código` incluso.\n'
        subprocess.run([sys.executable, str(CANVAS), 'publish', 'b1', str(self.sb.md(doc))], env=self.sb.env, check=True, capture_output=True)
        self.block = self.blocks()[1]
        sel = self.selector({**self.valid(), 'quote': {'exact': 'O preço é R$ 10 por mês, com código incluso.', 'prefix': '', 'suffix': ''}})
        self.assertEqual(sel['exact'], 'O preço é R$ 10 por mês, com código incluso.')

    def test_page_after_a_comment_lists_only_open_ones_for_the_pins(self):
        self.post({**self.valid('aberto')})
        cid = self.lines()[0]['id']
        self.post(self.valid('fechado'))
        second = self.lines()[1]['id']
        subprocess.run([sys.executable, str(CANVAS), 'resolve', 'b1', second], env=self.sb.env, check=True, capture_output=True)
        page = self.req('GET', '/b1/')[2].decode()
        self.assertIn(f'"id": "{cid}"', page)
        self.assertIn('"body": "aberto"', page)
        self.assertNotIn('fechado', page)


class ServeLifecycleTest(unittest.TestCase):
    def test_detach_is_idempotent_and_stop_cleans_up(self):
        sb = Sandbox()
        try:
            sb.env['CANVAS_PORT'] = '0'
            subprocess.run([sys.executable, str(CANVAS), 'publish', 'b1', str(sb.md(DOC))], env=sb.env, check=True, capture_output=True)
            run = lambda *a: subprocess.run([sys.executable, str(CANVAS), 'serve', *a], env=sb.env, text=True, capture_output=True, timeout=30)
            first = run('--detach')
            self.assertEqual(first.returncode, 0, first.stderr)
            info = json.loads(first.stdout)
            self.assertTrue(info['started'])
            second = json.loads(run('--detach').stdout)
            self.assertFalse(second['started'])
            self.assertEqual(second['pid'], info['pid'])
            self.assertEqual(second['port'], info['port'])
            self.assertEqual(run().returncode, 1)                 # a second foreground server is refused
            self.assertIn('already running', run().stderr)
            c = http.client.HTTPConnection('127.0.0.1', info['port'], timeout=5)
            c.request('GET', '/b1/')
            self.assertEqual(c.getresponse().status, 200)
            stopped = json.loads(run('--stop').stdout)
            self.assertTrue(stopped['stopped'])
            state = sb.home / '.local/state/herdr-canvas'
            self.assertEqual([p.name for p in state.iterdir() if p.name in ('server.pid', 'port', 'token')], [])
            with self.assertRaises(OSError):
                os.kill(info['pid'], 0)
            self.assertFalse(json.loads(run('--stop').stdout)['stopped'])
        finally:
            subprocess.run([sys.executable, str(CANVAS), 'serve', '--stop'], env=sb.env, capture_output=True)
            sb.cleanup()


if __name__ == '__main__':
    unittest.main()
