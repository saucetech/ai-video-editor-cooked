"""Local, source-based Resolve adapter. Run native calls in Resolve's own Python.

The public functions return JSON-safe dictionaries. ResolveBridge(resolve=fake) is
an injection point for offline tests; no vendor module is imported in the app.
"""
import json
import hmac
import http.client
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import math
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

MANIFEST = 'resolve-manifest.json'
RESOLVE_PYTHON = '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython'
PREFIX = 'COOKED_RESOLVE_JSON:'
DIAGNOSTIC = ('Open Resolve and a dedicated project. Set up the local connection in GenMedia Editor, then paste its '
              'dofile command into Workspace > Console once per Resolve session. '
              'Free Resolve 21.1 may omit Python scripts and not execute menu scripts. '
              'Resolve Studio can alternatively use Preferences > System > General > External scripting: Local. '
              'No scripting preference is changed automatically.')


class BridgeError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _require(value, message, code='resolve_error'):
    if not value:
        raise BridgeError(code, message)
    return value


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _write(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def _rate(fps):
    fps = float(fps)
    _require(math.isfinite(fps) and 1 <= fps <= 240, 'Invalid source FPS.', 'invalid_edit')
    nominal = round(fps)
    if abs(fps - nominal * 1000 / 1001) < .005 and abs(fps - nominal) > .005:
        return Fraction(nominal * 1000, 1001)
    return Fraction(str(fps)).limit_denominator(1001)


def _load_edit(edit):
    try:
        from . import resolve_visuals
    except ImportError:
        import resolve_visuals
    report = _read(edit / 'report.json')
    fps = float(report['fps'])
    rate = _rate(fps)
    source = Path(report['source']).expanduser()
    if not source.is_absolute():
        source = edit / source
    source = source.resolve()
    _require(source.is_file(), 'Original source is missing: ' + str(source), 'invalid_edit')
    with source.open('rb') as f:
        _require(f.read(1), 'Original source is empty.', 'invalid_edit')
    decisions = _read(edit / 'decisions.json')
    _require(isinstance(decisions, list) and decisions, 'No kept decisions.', 'invalid_edit')
    frames = []
    for span in decisions:
        start, end = float(span['start']), float(span['end'])
        _require(math.isfinite(start) and math.isfinite(end) and 0 <= start < end,
                 'Invalid kept source interval.', 'invalid_edit')
        a, b = round(start * fps), round(end * fps)
        _require(b > a, 'A kept interval contains no frames.', 'invalid_edit')
        frames.append([a, b])
    _require(report.get('frames') == frames,
             'decisions.json and report.json frames disagree. Rebuild the cut first.', 'invalid_edit')
    plan = _read(edit / 'plan.json') if (edit / 'plan.json').exists() else {}
    total = sum(b - a for a, b in frames)
    if 'durationInFrames' in plan:
        _require(plan['durationInFrames'] == total, 'Plan duration differs from the cut; plan again.', 'invalid_edit')
    zooms, warnings = [], []
    for z in plan.get('zooms', []):
        if z.get('kind') != 'punch' or any(z.get(k, 0) for k in ('ease_s', 'travel_s')):
            warnings.append('Animated zoom omitted: only static punch ZoomX/ZoomY is supported.')
            continue
        a, b, scale = round(float(z['start']) * fps), round(float(z['end']) * fps), float(z['scale'])
        _require(0 <= a < b <= total and math.isfinite(scale) and .1 <= scale <= 100,
                 'Invalid punch zoom.', 'invalid_edit')
        _require(not any(a < y and x < b for x, y, _ in zooms), 'Overlapping zooms are unsupported.', 'invalid_edit')
        zooms.append((a, b, scale))
    clips, record = [], 0
    for a, b in frames:
        cuts = sorted({record, record + b - a} | {v for x, y, _ in zooms for v in (x, y)
                                                if record < v < record + b - a})
        for left, right in zip(cuts, cuts[1:]):
            scale = next((s for x, y, s in zooms if x <= left < y), 1.0)
            clips.append({'source_start': a + left - record, 'source_end': a + right - record,
                          'record': left, 'duration': right - left,
                          'properties': {'ZoomX': scale, 'ZoomY': scale}})
        record += b - a
    if plan.get('captions') or plan.get('cards') or plan.get('sfx'):
        warnings.append('Captions, graphics and sound cues are not imported by this source-cut adapter.')
    st = source.stat()
    result = {'source': str(source), 'source_stat': [st.st_size, st.st_mtime_ns],
              'rate': [rate.numerator, rate.denominator], 'clips': clips, 'warnings': warnings}
    visual = resolve_visuals.load_bundle(edit, total, rate)
    if visual: result['visual_bundle'] = visual
    return result


def _snapshot(timeline):
    rows, objects = [], {}
    for kind in ('video', 'audio'):
        for track in range(1, timeline.GetTrackCount(kind) + 1):
            for item in timeline.GetItemListInTrack(kind, track) or []:
                uid = item.GetUniqueId()
                media = item.GetMediaPoolItem()
                row = {'id': uid, 'kind': kind, 'track': track, 'start': item.GetStart(),
                       'end': item.GetEnd(), 'duration': item.GetDuration(), 'speed': item.GetSpeed(),
                       'enabled': item.GetClipEnabled(), 'left': item.GetLeftOffset(), 'right': item.GetRightOffset(),
                       'media_id': media.GetUniqueId() if media else None,
                       'media_path': media.GetClipProperty().get('File Path') if media else None}
                if kind == 'video':
                    props = item.GetProperties()
                    row['properties'] = {key: props[key] for key in ('ZoomX', 'ZoomY')}
                rows.append(row)
                objects[uid] = item
    return rows, objects


def _same(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-5)
    return a == b


def _structure(data):
    return {key: data[key] for key in ('source', 'source_stat', 'rate')} | {
        'clips': [{k: v for k, v in clip.items() if k != 'properties'} for clip in data['clips']]}


class ResolveBridge:
    def __init__(self, resolve=None, command=None, timeout=45, runtime=None):
        self.resolve = resolve
        self.command = command or [RESOLVE_PYTHON]
        self.timeout = timeout
        self.runtime = _runtime(runtime)

    def _call(self, action, edit_dir=None, name=None):
        if self.resolve is None:
            try:
                from . import resolve_lua
            except ImportError:
                import resolve_lua
            if resolve_lua.available(self.runtime):
                try:
                    with resolve_lua.Session(self.runtime, timeout=self.timeout) as session:
                        return ResolveBridge(resolve=session.resolve, runtime=self.runtime)._call(action, edit_dir, name)
                except (RuntimeError, OSError, ValueError) as exc:
                    return self._failure(action, 'lua_error', str(exc))
            if resolve_lua.needs_attention(self.runtime):
                return self._failure(action, 'lua_unavailable',
                    'The Lua helper is busy, stale or requires recovery. No other transport was used. Inspect Resolve and the manifest, then Stop the connection before restarting its Console command.')
            embedded = self._embedded_call(action, edit_dir, name)
            if embedded is not None:
                return embedded
            try:
                result = subprocess.run([*self.command, str(Path(__file__).resolve()), '--worker'],
                                        input=json.dumps({'action': action, 'edit_dir': str(edit_dir) if edit_dir else None,
                                                          'name': name}), capture_output=True, text=True,
                                        timeout=self.timeout)
                line = next((s[len(PREFIX):] for s in reversed(result.stdout.splitlines()) if s.startswith(PREFIX)), None)
                if line is None:
                    return self._failure(action, 'disconnected', 'Resolve scripting did not respond. ' + DIAGNOSTIC)
                return json.loads(line)
            except (OSError, subprocess.TimeoutExpired, ValueError):
                return self._failure(action, 'disconnected', 'Resolve scripting is unavailable. ' + DIAGNOSTIC +
                                     (' A timed-out editing request may have partially completed; inspect the manifest before retrying.'
                                      if action != 'status' else ''))
        lock = None
        try:
            if action == 'status':
                return {'connected': True, 'version': self.resolve.GetVersionString(), 'message': 'Resolve scripting connected.'}
            edit = Path(edit_dir).expanduser().resolve()
            lock = edit / '.resolve-bridge.lock'
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                lock = None
                raise BridgeError('busy', 'A Resolve operation is active or was interrupted. Inspect Resolve before removing .resolve-bridge.lock.')
            os.close(fd)
            manager = self.resolve.GetProjectManager()
            project = _require(manager.GetCurrentProject(), 'Open a dedicated Resolve project first.', 'no_project')
            data = _load_edit(edit)
            if action == 'create':
                return self._create(edit, data, project, manager, name)
            return self._update(edit, data, project, manager)
        except BridgeError as exc:
            return self._failure(action, exc.code, str(exc))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            return self._failure(action, 'invalid_edit' if isinstance(exc, (OSError, ValueError, KeyError, TypeError)) else 'resolve_error',
                                 'Resolve operation failed: ' + str(exc) + '. Inspect any incomplete manifest before retrying.')
        except Exception:
            return self._failure(action, 'resolve_error', 'Resolve API operation failed. Inspect any incomplete manifest before retrying.')
        finally:
            if lock:
                lock.unlink(missing_ok=True)

    def _embedded_call(self, action, edit_dir, name):
        try:
            descriptor = _read(self.runtime / 'resolve-bridge.json')
            port = int(descriptor['port'])
            if not 1 <= port <= 65535 or not isinstance(descriptor['token'], str):
                return None
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=self.timeout)
            try:
                body = json.dumps({'action': action, 'edit_dir': str(edit_dir) if edit_dir else None, 'name': name})
                conn.request('POST', '/resolve', body=body, headers={
                    'Authorization': 'Bearer ' + descriptor['token'], 'Content-Type': 'application/json'})
                response = conn.getresponse()
                if response.status != 200:
                    return self._failure(action, 'embedded_error', 'Internal Resolve bridge rejected the request. Restart cooked_resolve_bridge from Workspace > Scripts > Utility.')
                return json.loads(response.read(1024 * 1024))
            finally:
                conn.close()
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
            # An editing request may have been accepted before the connection failed.
            # Never send it again through another transport after an unknown outcome.
            if action == 'status':
                return None
            return self._failure(action, 'embedded_error', 'Internal Resolve bridge did not respond. Inspect Resolve and the manifest before retrying; restart Workspace > Scripts > Utility > cooked_resolve_bridge.')

    @staticmethod
    def _failure(action, code, message):
        if action == 'status':
            return {'connected': False, 'version': None, 'message': message}
        return {'ok': False, 'code': code, 'message': message}

    def status(self): return self._call('status')
    def create_timeline(self, edit_dir, name=None): return self._call('create', edit_dir, name)
    def update_timeline(self, edit_dir): return self._call('update', edit_dir)

    def _create(self, edit, data, project, manager, name):
        path = edit / MANIFEST
        _require(not path.exists(), 'This edit already has a Resolve manifest. Use update; for a separate timeline use a separate edit folder.', 'already_managed')
        pool = project.GetMediaPool()
        media = _require(pool.ImportMedia([data['source']]), 'Resolve could not import the original source.')[0]
        props = media.GetClipProperty()
        _require(Path(props['File Path']).resolve() == Path(data['source']), 'Resolve imported a different source path.', 'invalid_edit')
        _require(_rate(props['FPS']) == Fraction(*data['rate']), 'Source and cut frame rates differ.', 'invalid_edit')
        _require(max(c['source_end'] for c in data['clips']) <= int(props['Frames']),
                 'Kept ranges exceed the original source frame count.', 'invalid_edit')
        current = project.GetCurrentTimeline()
        timeline = None
        page = None
        try:
            if data.get('visual_bundle'):
                # Resolve synchronizes Fusion settings under a render lock. Leave the viewer first.
                page = self.resolve.GetCurrentPage()
                _require(self.resolve.OpenPage('media'), 'Open the Media page before configuring this visual timeline.')
                _require(self.resolve.GetCurrentPage() == 'media', 'Resolve did not leave its active viewer.')
            timeline = _require(pool.CreateEmptyTimeline(name or 'GenMedia ' + edit.name), 'Resolve could not create a new timeline.')
            manifest = dict(data, schema=1, state='incomplete', project_id=project.GetUniqueId(),
                            timeline_id=timeline.GetUniqueId(), timeline_name=timeline.GetName())
            _write(path, manifest)  # interruption is visible; never blindly replay a mutation
            rate = Fraction(*data['rate'])
            label = format(round(float(rate), 3), 'g')
            settings = {'useCustomSettings': '1', 'timelineFrameRate': label}
            if data.get('visual_bundle'):
                settings.update(timelineResolutionWidth=str(data['visual_bundle'].get('native_width',data['visual_bundle']['width'])), timelineResolutionHeight=str(data['visual_bundle'].get('native_height',data['visual_bundle']['height'])))
            _require(timeline.SetSettings(settings),
                     'Resolve rejected the dedicated timeline frame rate; timeline is incomplete.')
            _require(_rate(timeline.GetSettings()['timelineFrameRate']) == rate,
                     'Resolve did not apply the source frame rate; timeline is incomplete.')
            _require(project.SetCurrentTimeline(timeline), 'Resolve could not select the new dedicated timeline.')
            start = timeline.GetStartFrame()
            infos = [{'mediaPoolItem': media, 'startFrame': c['source_start'],
                      'endFrame': c['source_end'], 'recordFrame': start + c['record']}
                     for c in data['clips']]
            _require(pool.AppendToTimeline(infos), 'Resolve did not append the source ranges; timeline is incomplete.')
            rows, objects = _snapshot(timeline)
            videos = sorted((r for r in rows if r['kind'] == 'video'), key=lambda r: r['start'])
            _require(len(videos) == len(data['clips']), 'Resolve created unexpected clips; timeline is incomplete.')
            for row, clip in zip(videos, data['clips']):
                _require(_same([row['start'], row['duration'], row['left']],
                               [start + clip['record'], clip['duration'], clip['source_start']]),
                         'Resolve returned different frame boundaries; timeline is incomplete.')
                _require(objects[row['id']].SetProperties(clip['properties']), 'Resolve rejected zoom properties; timeline is incomplete.')
            rows, _ = _snapshot(timeline)
            for row, clip in zip(sorted((r for r in rows if r['kind'] == 'video'), key=lambda r: r['start']), data['clips']):
                _require(_same(row['properties'], clip['properties']), 'Resolve did not apply zoom properties; timeline is incomplete.')
            if data.get('visual_bundle'):
                try:
                    from . import resolve_visuals
                except ImportError:
                    import resolve_visuals
                manifest['native_layers'] = resolve_visuals.append_layers(pool, timeline, data['visual_bundle'], start)
                rows, _ = _snapshot(timeline)
            manifest.update(state='ready', snapshot=rows, settings=timeline.GetSettings())
            _require(manager.SaveProject(), 'Resolve could not save the project; manifest remains incomplete.')
            _write(path, manifest)
            return self._success(manifest, path, 'Created a native source-cut timeline.')
        finally:
            if current is not None and timeline is not None:
                _require(project.SetCurrentTimeline(current), 'Created timeline, but could not restore the previously selected timeline. Inspect Resolve.')
            if page:
                _require(self.resolve.OpenPage(page), 'Inspect Resolve: its previous page could not be restored.')

    def _update(self, edit, data, project, manager):
        path = edit / MANIFEST
        manifest = _read(path)
        _require(not manifest.get('visual_bundle', {}).get('layers'),
                 'This revision has editable visual layers. Create a new board revision and timeline to preserve native finishing.', 'visual_revision')
        _require(manifest.get('schema') == 1 and manifest.get('state') == 'ready',
                 'Manifest is incomplete or unsupported. Inspect the created timeline; do not retry blindly.', 'incomplete')
        _require(manifest['project_id'] == project.GetUniqueId(), 'Open the project that owns this timeline.', 'wrong_project')
        timeline = next((project.GetTimelineByIndex(n) for n in range(1, project.GetTimelineCount() + 1)
                         if project.GetTimelineByIndex(n).GetUniqueId() == manifest['timeline_id']), None)
        _require(timeline, 'Managed timeline was removed. No timeline was changed.', 'manual_changes')
        _require(_same(_structure(manifest), _structure(data)),
                 'Cuts, source, frame rate or zoom boundaries changed. Create a separate edit folder/timeline to preserve manual edits.', 'structure_changed')
        rows, objects = _snapshot(timeline)
        _require(_same(rows, manifest['snapshot']) and _same(timeline.GetSettings(), manifest['settings']),
                 'Managed clip trims, placement, tracks, source, zoom or timeline settings changed manually. No update applied.', 'manual_changes')
        videos = sorted((r for r in rows if r['kind'] == 'video'), key=lambda r: r['start'])
        # All conflicts are checked before the first write. Unmanaged properties are never set.
        manifest['state'] = 'incomplete'
        _write(path, manifest)
        for row, clip in zip(videos, data['clips']):
            if not _same(row['properties'], clip['properties']):
                _require(objects[row['id']].SetProperties(clip['properties']),
                         'Resolve rejected an update; manifest is incomplete. Inspect the timeline before retrying.')
        rows, _ = _snapshot(timeline)
        for row, clip in zip(sorted((r for r in rows if r['kind'] == 'video'), key=lambda r: r['start']), data['clips']):
            _require(_same(row['properties'], clip['properties']), 'Resolve did not apply zoom update; inspect incomplete manifest.')
        _require(manager.SaveProject(), 'Resolve could not save the updated project; inspect incomplete manifest.')
        manifest.update(data, state='ready', snapshot=rows)
        _write(path, manifest)
        return self._success(manifest, path, 'Updated managed zoom properties; other properties were preserved.')

    @staticmethod
    def _success(manifest, path, message):
        return {'ok': True, 'message': message, 'timeline_id': manifest['timeline_id'],
                'timeline_name': manifest['timeline_name'], 'manifest': str(path),
                'clips': len(manifest['clips']), 'warnings': manifest['warnings']}


_EMBEDDED = None


def _runtime(runtime=None):
    return Path(runtime or os.environ.get('AI_EDITOR_HOME') or Path.home() / '.ai-video-editor').expanduser().resolve()


def start_embedded(resolve, runtime=None):
    """Call inside Resolve's Python console or a trusted Workspace Utility script.

    Only the three fixed adapter operations are exposed, with an unguessable token.
    No shell commands, eval, arbitrary scripting or remote bind address is accepted.
    """
    global _EMBEDDED
    if _EMBEDDED is not None:
        return {'connected': True, 'version': resolve.GetVersionString(), 'message': 'Internal Resolve bridge already running.'}
    bridge = ResolveBridge(resolve=resolve, runtime=runtime)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)
        def log_message(self, *args): pass  # Never log Authorization or local media paths.
        def do_POST(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            if (self.path != '/resolve' or self.headers.get('Host') != host or
                    self.headers.get('Origin') is not None or
                    self.headers.get('Sec-Fetch-Site') is not None or
                    not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)):
                self.send_error(403); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Unsupported request')
                request = json.loads(self.rfile.read(size))
                if (not isinstance(request, dict) or set(request) - {'action', 'edit_dir', 'name'} or
                        request.get('action') not in ('status', 'create', 'update') or
                        (request.get('action') != 'status' and not isinstance(request.get('edit_dir'), str)) or
                        (request.get('name') is not None and not isinstance(request['name'], str))):
                    raise ValueError('Unsupported action')
                result = bridge._call(request['action'], request.get('edit_dir'), request.get('name'))
                payload = json.dumps(result).encode('utf-8')
            except (ValueError, TypeError):
                self.send_error(400); return
            except Exception:
                payload = json.dumps({'ok': False, 'code': 'resolve_error', 'message': 'Resolve operation failed; inspect manifest before retrying.'}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
        def do_GET(self): self.send_error(405)
        def do_OPTIONS(self): self.send_error(403)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.timeout = 1
    descriptor = bridge.runtime / 'resolve-bridge.json'
    descriptor.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(descriptor, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump({'port': server.server_port, 'token': token, 'pid': os.getpid()}, stream)
    thread = threading.Thread(target=server.serve_forever, name='cooked-resolve', daemon=True)
    _EMBEDDED = (server, descriptor, token)
    thread.start()
    return {'connected': True, 'version': resolve.GetVersionString(), 'message': 'Internal Resolve bridge running locally.'}


def stop_embedded():
    """Stop this interpreter's bridge; used by tests and explicit console shutdown."""
    global _EMBEDDED
    if _EMBEDDED is None:
        return
    server, path, token = _EMBEDDED
    server.shutdown(); server.server_close()
    try:
        if _read(path).get('token') == token:
            path.unlink()
    except (OSError, ValueError):
        pass
    _EMBEDDED = None


def install_internal_bridge(runtime=None, scripts_dir=None):
    """Install only a local import script, without changing Resolve preferences."""
    runtime = _runtime(runtime)
    utility = Path(scripts_dir or Path.home() / 'Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility')
    utility.mkdir(parents=True, exist_ok=True)
    path = utility / 'cooked_resolve_bridge.py'
    source = ('# cooked local Resolve bridge; no uploads, shell commands or paid actions.\n'
              'import sys\n'
              'sys.path.insert(0, ' + repr(str(Path(__file__).resolve().parents[1])) + ')\n'
              'from ai_editor.resolve_bridge import start_embedded\n'
              'print(start_embedded(resolve, runtime=' + repr(str(runtime)) + '))\n')
    path.write_text(source, encoding='utf-8')
    try:
        from . import resolve_lua
    except ImportError:
        import resolve_lua
    lua_path, command = resolve_lua.install(runtime, utility)
    return {'ok': True, 'path': str(path), 'lua_path': str(lua_path), 'console_command': command, 'message':
            'In Resolve, open a dedicated project, then Workspace > Console. Paste the command below and press Return. Leave that Console session running. This macOS Lua connection works without Python or changing scripting preferences.'}


def status(): return ResolveBridge().status()
def create_timeline(edit_dir: Path, name: str | None = None): return ResolveBridge().create_timeline(edit_dir, name)
def update_timeline(edit_dir: Path): return ResolveBridge().update_timeline(edit_dir)


def stop_local_connection():
    try:
        from . import resolve_lua
    except ImportError:
        import resolve_lua
    return resolve_lua.stop(_runtime())


def _worker():
    request = json.load(sys.stdin)
    action = request['action']
    try:
        import DaVinciResolveScript as vendor
        resolve = vendor.scriptapp('Resolve')
        if resolve is None:
            result = ResolveBridge._failure(action, 'disconnected', 'Resolve is not connected. ' + DIAGNOSTIC)
        else:
            result = ResolveBridge(resolve=resolve)._call(action, request.get('edit_dir'), request.get('name'))
    except Exception:
        result = ResolveBridge._failure(action, 'disconnected', 'Resolve scripting could not connect. ' + DIAGNOSTIC)
    print(PREFIX + json.dumps(result))


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    _worker()
