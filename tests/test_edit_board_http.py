import http.client
import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/ai-editor/lib/ai_editor'))


class EditBoardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('edit_board_http'), 'Board routes are not implemented')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.old = {k: os.environ.get(k) for k in ('AI_EDITOR_HOME', 'AI_EDITOR_LIBRARY')}
        self.addCleanup(self.restore)
        os.environ['AI_EDITOR_HOME'] = str(Path(self.tmp.name) / 'runtime')
        os.environ['AI_EDITOR_LIBRARY'] = str(Path(self.tmp.name) / 'library')
        self.home = importlib.import_module('home')
        self.root = Path(os.environ['AI_EDITOR_LIBRARY']); self.root.mkdir()
        self.home.update(lambda d: d.update(root=str(self.root)))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), self.home.make_handler('test-token'))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.stop)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def restore(self):
        for k, v in self.old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def stop(self): self.server.shutdown(); self.server.server_close()

    def request(self, method, path, body=None, auth=True, origin=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        hs = {'Content-Type': 'application/json', **(headers or {})}
        if method == 'POST': hs['Origin'] = origin or self.base
        if auth: path += ('&' if '?' in path else '?') + 't=test-token'
        c.request(method, path, json.dumps(body) if body is not None else None, hs)
        r = c.getresponse(); result = r.status, dict(r.getheaders()), r.read(); c.close()
        return result

    def test_board_requires_token_and_rejects_cross_origin_writes(self):
        self.assertEqual(self.request('GET', '/edit-board', auth=False)[0], 403)
        self.assertEqual(self.request('POST', '/board/sample', {}, origin='https://other.example')[0], 403)
        self.assertFalse((self.root / 'edits/edit-board-sample').exists())
        status, headers, body = self.request('GET', '/edit-board')
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn(b'Edit board', body)

    def test_unrelated_edit_path_is_rejected_before_read_or_write(self):
        status, _, raw = self.request('POST', '/board/load', {'edit': '/tmp/unrelated'})
        self.assertEqual(status, 400)
        self.assertIn('library', json.loads(raw)['error'])

    def test_identity_assets_are_served_with_types_and_theme_is_shared(self):
        import review
        review.set_theme('light')
        status, _, raw = self.request('GET', '/edit-board')
        self.assertEqual(status, 200)
        self.assertIn(b'data-theme="light"', raw)
        self.assertIn(b'GenMedia Editor', raw)
        for path, content_type in [('/genmedia.css', 'text/css'), ('/genmedia-icon.svg', 'image/svg+xml')]:
            status, headers, raw = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertTrue(headers['Content-Type'].startswith(content_type))
            self.assertTrue(raw)
            self.assertEqual(self.request('GET', path, auth=False)[0], 403)

    def test_asset_catalog_is_owned_and_read_only(self):
        asset=self.root/'assets';asset.mkdir();(asset/'broll.mp4').write_bytes(b'video')
        (asset/'not-video.txt').write_text('text',encoding='utf-8')
        (asset/'escape.mov').symlink_to('/etc/hosts')
        status,_,raw=self.request('GET','/board/assets')
        self.assertEqual(status,200);self.assertEqual([a['name'] for a in json.loads(raw)['assets']],['broll.mp4'])
        self.assertEqual(self.request('POST','/board/assets',{})[0],405)

    def test_styles_are_normalized_owned_and_proof_paths_are_finite(self):
        style=self.root/'creator-teardowns'/'serif';style.mkdir(parents=True)
        (style/'style.json').write_text(json.dumps({'captions':{'present':False},'look':{'font_class':'serif'}}),encoding='utf-8')
        status,_,raw=self.request('GET','/board/styles')
        self.assertEqual(status,200)
        data=json.loads(raw);self.assertEqual(data['styles'][0]['style']['font'],'Georgia')
        self.assertEqual(self.request('POST','/board/styles',{})[0],405)
        self.assertEqual(self.request('GET','/board/proof?edit=/tmp/outside&revision=../../&proof=../../&file=/etc/hosts')[0],400)

    def test_board_upload_is_promoted_before_temporary_staging_expires(self):
        stage=self.root/'.staged/drop';stage.mkdir(parents=True);file=stage/'broll.mp4';file.write_bytes(b'owned broll')
        status,_,raw=self.request('POST','/board/import-asset',{'path':str(file)})
        self.assertEqual(status,200)
        destination=Path(json.loads(raw)['path'])
        self.assertTrue(destination.is_relative_to(self.root.resolve()/'assets'))
        self.assertEqual(destination.read_bytes(),b'owned broll')
        self.assertEqual(self.request('POST','/board/import-asset',{'path':'/tmp/outside.mp4'})[0],400)
        assets=json.loads(self.request('GET','/board/assets')[2])['assets']
        self.assertEqual([a['path'] for a in assets],[str(destination)])

    def test_media_range_only_serves_selected_source_or_known_revision(self):
        edit = self.root / 'edits/cut'; edit.mkdir(parents=True)
        src = edit / 'source.mp4'; src.write_bytes(b'0123456789')
        (edit / 'decisions.json').write_text('[]', encoding='utf-8')
        (edit / 'report.json').write_text(json.dumps({'source': str(src)}), encoding='utf-8')
        url = '/board/media?edit=' + quote(str(edit))
        status, headers, body = self.request('GET', url, headers={'Range': 'bytes=2-5'})
        self.assertEqual((status, body), (206, b'2345'))
        self.assertEqual(headers['Content-Range'], 'bytes 2-5/10')
        self.assertEqual(self.request('GET', url, headers={'Range': 'bytes=99-'})[0], 416)
        self.assertEqual(self.request('GET', url, headers={'Range': 'bytes=-3'})[2], b'789')
        self.assertEqual(self.request('GET', url + '&revision=../other')[0], 400)
        self.assertEqual(self.request('GET', '/board/media?edit=/tmp/unrelated')[0], 400)


if __name__ == '__main__': unittest.main()
