import importlib.util
import json
import runpy
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TableTests(unittest.TestCase):
    def test_export_matches_existing_table_and_hash(self):
        export = load('export_table', ROOT / 'tools/export_morse_table.py')
        original = runpy.run_path(str(ROOT.parent / 'morse_table.py'))
        saved = json.loads((ROOT / 'public/morse_table.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, export.exported_table())
        self.assertEqual(saved['entries'], original['MORSE_TABLE'])
        self.assertEqual(len(saved['entries']), 65)

    def test_write_normalization_cross_language_fixtures(self):
        original = runpy.run_path(str(ROOT.parent / 'morse_table.py'))
        corpus = [chr(c) for c in range(0x3000, 0x3100)] + [chr(c) for c in range(0xff00, 0xfff0)]
        corpus += ['がぱヴｶﾞ１２', 'イイ', 'カ\u3099', 'ｶﾞ', '゛゜', 'イ\nイ', 'A', '漢', '', '😀', 'イ イ']
        rows = []
        for value in corpus:
            try:
                normalized = original['normalize_text'](value)
                if any(c in normalized for c in '（）'):
                    raise ValueError('parentheses deferred in optical phase one')
                rows.append({'input': value, 'output': normalized})
            except ValueError:
                rows.append({'input': value, 'error': True})
        target = ROOT / 'artifacts/normalization_fixtures.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load('optical_server', ROOT / 'serve.py')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), cls.module.PublicHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_only_public_allowlist(self):
        for path in ['/', '/app.js', '/morse_table.json']:
            with urllib.request.urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
        for path in ['/../README.md', '/%2e%2e/morse_table.py', '/artifacts/', '/models/', '/serve.py', '/.git/config', '/C:/Windows/win.ini']:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)

    def test_bind_rejects_wildcard_and_public(self):
        for host in ['0.0.0.0', '8.8.8.8', '::', 'example.com', '224.0.0.1']:
            with self.assertRaises(Exception): self.module.interface(host)
        self.assertEqual(self.module.interface('127.0.0.1'), '127.0.0.1')
        self.assertEqual(self.module.interface('192.168.1.5'), '192.168.1.5')


if __name__ == '__main__':
    unittest.main()
