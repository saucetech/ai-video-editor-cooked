"""Finite home-origin edit board actions. Home performs token and POST origin checks first."""
import mimetypes
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import edit_board as board
import integrations_http

HERE = Path(__file__).resolve().parent
ASSETS = {'/edit-board': ('edit-board.html', 'text/html; charset=utf-8'),
          '/edit-board.js': ('edit-board.js', 'text/javascript; charset=utf-8'),
          '/edit-board.css': ('edit-board.css', 'text/css; charset=utf-8')}
PATHS = {'/board/projects', '/board/assets', '/board/load', '/board/save', '/board/preview', '/board/approve',
         '/board/resolve', '/board/sample', '/board/media', '/board/captions'}


def media(handler, file):
    size = file.stat().st_size
    a, b, status = 0, size - 1, 200
    raw = handler.headers.get('Range')
    if raw:
        m = re.fullmatch(r'bytes=(\d*)-(\d*)', raw)
        if not m or not any(m.groups()):
            return handler.send(416, {'error': 'Use one byte range.'})
        if not m[1]: a = max(0, size - int(m[2]))
        else: a, b = int(m[1]), min(size - 1, int(m[2]) if m[2] else size - 1)
        if not 0 <= a <= b < size:
            return handler.send(416, {'error': 'Range is outside this media file.'})
        status = 206
    handler.send_response(status)
    handler.send_header('Content-Type', mimetypes.guess_type(str(file))[0] or 'video/mp4')
    handler.send_header('Content-Length', str(b - a + 1))
    handler.send_header('Accept-Ranges', 'bytes')
    handler.send_header('Cache-Control', 'no-store')
    if status == 206: handler.send_header('Content-Range', f'bytes {a}-{b}/{size}')
    handler.end_headers()
    with file.open('rb') as stream:
        stream.seek(a); left = b - a + 1
        while left:
            chunk = stream.read(min(left, 1 << 20))
            if not chunk: break
            handler.wfile.write(chunk); left -= len(chunk)


def route(handler, method, path, body, home):
    if path not in PATHS and path not in ASSETS: return False
    try:
        if path in ASSETS and method == 'GET':
            file, content_type = ASSETS[path]
            data = (HERE / file).read_bytes()
            if path == '/edit-board':
                import review
                data = review.themed(data)
            handler.send(200, data, content_type, cookie=path == '/edit-board')
            return True
        if path == '/board/projects' and method == 'GET':
            handler.send(200, {'edits': integrations_http.edits(home)})
            return True
        if path == '/board/assets' and method == 'GET':
            root = Path(home.read()['root']).resolve()
            files = []
            for folder in ('videos', 'assets', '.staged'):
                for file in (root / folder).rglob('*'):
                    if len(files) >= 200: break
                    if file.is_file() and file.suffix.lower() in board.visuals.VIDEO_EXTS and file.resolve().is_relative_to(root):
                        files.append({'path': str(file.resolve()), 'name': file.name})
            handler.send(200, {'assets': files})
            return True
        if path == '/board/captions' and method == 'GET':
            q = {k:v[0] for k,v in parse_qs(urlsplit(handler.path).query).items()}
            edit = integrations_http.edit_path(q.get('edit'), home)
            folder = board.revision_dir(edit, q.get('revision'))
            if board.read(folder / 'revision.json')['state'] != 'ready':raise ValueError('The preview is not ready.')
            board.visuals.verify_bundle(folder)
            file = folder / 'captions.srt'
            handler.send(200, file.read_bytes(), 'application/x-subrip; charset=utf-8')
            return True
        if path == '/board/media' and method == 'GET':
            q = {k: v[0] for k, v in parse_qs(urlsplit(handler.path).query).items()}
            edit = integrations_http.edit_path(q.get('edit'), home)
            if q.get('revision'):
                folder = board.revision_dir(edit, q['revision'])
                if board.read(folder / 'revision.json')['state'] != 'ready':
                    raise ValueError('The preview is not ready.')
                file = (folder / 'cut.mp4').resolve()
                if file.parent != folder.resolve(): raise ValueError('Invalid preview path.')
            else:
                file = Path(board.read(edit / 'report.json')['source']).expanduser()
                file = (file if file.is_absolute() else edit / file).resolve()
            if not file.is_file() or file.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi'):
                raise ValueError('The selected media is unavailable.')
            media(handler, file)
            return True
        if method != 'POST' or path in ASSETS or path in ('/board/projects', '/board/assets', '/board/media', '/board/captions'):
            handler.send(405, {'error': 'Use the board control for this action.'}); return True
        if not isinstance(body, dict): raise ValueError('Expected a board request object.')
        import live
        with live.busy():
            if path == '/board/sample': result = board.create_sample(Path(home.read()['root']))
            else:
                edit = integrations_http.edit_path(body.get('edit'), home)
                version, rid = body.get('version'), body.get('revision')
                if path == '/board/load': result = board.load(edit)
                elif path == '/board/save': result = board.save(edit, version, body.get('rows'), [Path(home.read()['root'])])
                elif path == '/board/preview': result = board.preview(edit, version)
                elif path == '/board/approve': result = board.approve(edit, rid, version)
                else: result = board.send_to_resolve(edit, rid, version)
        handler.send(200, result)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        handler.send(400, {'error': str(exc)[:1200]})
    return True
