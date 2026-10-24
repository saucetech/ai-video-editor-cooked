"""Source-linked review decisions and immutable, explicitly approved Resolve revisions."""
import contextlib
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from fractions import Fraction
from pathlib import Path

import resolve_bridge as resolve
import board_visuals as visuals

HERE = Path(__file__).resolve().parent
RENDER = HERE.parents[1] / 'skills/cut/scripts/render.py'
_UNSET = object()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


@contextlib.contextmanager
def locked(edit):
    path = Path(edit) / '.edit-board.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('This board is busy or an action was interrupted. Inspect its revision before retrying.') from None
    try:
        yield
    finally:
        os.close(fd)
        path.unlink(missing_ok=True)


def fingerprint(paths):
    h = hashlib.sha256()
    for path in paths:
        h.update(path.name.encode())
        h.update(path.read_bytes() if path.is_file() else b'<missing>')
    return h.hexdigest()


def probe(source):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)],
                            capture_output=True, text=True, timeout=30, check=True)
    data = json.loads(result.stdout)
    v = next(x for x in data['streams'] if x['codec_type'] == 'video')
    fps = float(Fraction(v['r_frame_rate']))  # same frame-index contract as build_timeline.py
    total = int(v.get('nb_frames') or round(float(v.get('duration') or data['format']['duration']) * fps))
    if not math.isfinite(fps) or not 1 <= fps <= 240 or total < 1:
        raise ValueError('Unsupported source frame rate or duration.')
    return fps, total


def context(edit):
    edit = Path(edit).resolve()
    report = read(edit / 'report.json')
    source = Path(report['source']).expanduser()
    source = (source if source.is_absolute() else edit / source).resolve()
    st = source.stat()
    fps, total = probe(source)
    if abs(float(report['fps']) - fps) > .005:
        raise ValueError('The source and cut frame rates disagree. Rebuild the source cut.')
    frames = report['frames']
    if not isinstance(frames, list) or not frames or len(frames) > 500:
        raise ValueError('Choose a nonempty source cut with at most 500 intervals.')
    last = 0
    for span in frames:
        if (not isinstance(span, list) or len(span) != 2 or any(type(n) is not int for n in span)
                or not last <= span[0] < span[1] <= total):
            raise ValueError('The board currently requires ordered, nonoverlapping source frame ranges.')
        last = span[1]
    decisions = read(edit / 'decisions.json')
    if [[round(x['start'] * fps), round(x['end'] * fps)] for x in decisions] != frames:
        raise ValueError('Source decisions and frame report disagree. Rebuild the cut.')
    stamp = fingerprint([edit / name for name in ('report.json', 'decisions.json', 'words.raw.json', 'plan.json')])
    identity = hashlib.sha256(json.dumps([str(source), st.st_size, st.st_mtime_ns, stamp]).encode()).hexdigest()
    return {'source': str(source), 'fps': fps, 'total_frames': total, 'frames': frames, 'fingerprint': identity}


def initial(edit, ctx):
    words_path = edit / 'words.raw.json'
    words = read(words_path) if words_path.exists() else []
    if isinstance(words, dict): words = words.get('words', [])
    if not isinstance(words, list): words = []
    spans, pos = [], 0
    for a, b in ctx['frames']:
        if a > pos: spans.append((pos, a, False))
        spans.append((a, b, True)); pos = b
    if pos < ctx['total_frames']: spans.append((pos, ctx['total_frames'], False))
    rows = []
    for a, b, keep in spans:
        text = ' '.join(str(w.get('word', w.get('text', ''))).strip() for w in words
                        if isinstance(w, dict) and float(w.get('end', 0)) > a / ctx['fps']
                        and float(w.get('start', 0)) < b / ctx['fps'])
        rows.append({'id': uuid.uuid4().hex, 'start_frame': a, 'end_frame': b, 'keep': keep,
                     'protected': False, 'text': text[:8000], 'note': '', 'emphasis': '', 'zoom': 1.0})
    return {'schema': 1, 'version': 1, 'fingerprint': ctx['fingerprint'], 'rows': rows,
            'approved_revision': None, 'sample': False}


def current(edit, expected=_UNSET):
    ctx = context(edit)
    path = edit / 'board.json'
    board = read(path) if path.exists() else initial(edit, ctx)
    if board['fingerprint'] != ctx['fingerprint']:
        raise ValueError('Source or original cut inputs changed. Use a separate edit folder for the new source cut.')
    if expected is not _UNSET and (type(expected) is not int or expected != board['version']):
        raise ValueError('This board changed in another tab. Reload before saving or approving.')
    if not path.exists(): write(path, board)
    return board, ctx


def revision_dir(edit, rid):
    if not isinstance(rid, str) or not re.fullmatch('[0-9a-f]{32}', rid):
        raise ValueError('Choose a saved board revision.')
    root = (edit / 'board-revisions').resolve()
    path = root / rid
    if path.resolve().parent != root or path.is_symlink() or not (path / 'revision.json').is_file():
        raise ValueError('Unknown board revision.')
    return path


def revisions(edit):
    out = []
    for p in (edit / 'board-revisions').glob('*/revision.json'):
        try:
            item = read(revision_dir(edit, p.parent.name) / 'revision.json')
            if item['state'] == 'rendering' and time.time() - item['created'] > 45:
                try: os.kill(item.get('pid', -1), 0) if item.get('pid', 0) > 0 else (_ for _ in ()).throw(ProcessLookupError())
                except ProcessLookupError:
                    item.update(state='failed', error='Preview process stopped. Create a new preview; no Resolve action was sent.')
                    write(p, item)
            out.append(item)
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda x: x['created'], reverse=True)[:40]


def view(edit, board, ctx):
    return {**board, 'rows': [visuals.row_defaults(r) for r in board['rows']], 'edit': str(edit), 'name': edit.name, 'fps': ctx['fps'], 'total_frames': ctx['total_frames'],
            'selected_frames': sum(r['end_frame'] - r['start_frame'] for r in board['rows'] if r['keep']),
            'revisions': revisions(edit)}


def load(edit):
    edit = Path(edit).resolve()
    with locked(edit):
        board, ctx = current(edit)
        return view(edit, board, ctx)


def save(edit, expected_version, rows, asset_roots=None):
    edit = Path(edit).resolve()
    with locked(edit):
        board, ctx = current(edit, expected_version)
        if not isinstance(rows, list) or len(rows) != len(board['rows']):
            raise ValueError('Keep the original board rows and order.')
        clean = []
        for old, row in zip(board['rows'], rows):
            if not isinstance(row, dict) or any(row.get(k) != old[k] for k in ('id', 'start_frame', 'end_frame', 'text')):
                raise ValueError('Source ranges, transcript and row identity cannot be changed by this form.')
            if any(type(row.get(k)) is not bool for k in ('keep', 'protected')):
                raise ValueError('Keep and protection must be checked or unchecked.')
            if row['protected'] and not row['keep']:
                raise ValueError('Unprotect the protected hold before removing it.')
            for k, limit in (('note', 4000), ('emphasis', 200)):
                if not isinstance(row.get(k), str) or len(row[k]) > limit:
                    raise ValueError('Visual note or emphasis text is too long.')
            z = row.get('zoom')
            if type(z) not in (float, int) or not math.isfinite(z) or not 1 <= z <= 2:
                raise ValueError('Use a static zoom between 1 and 2.')
            visual = visuals.validate_row(row, asset_roots or [edit])
            clean.append({**visuals.row_defaults(old), **{k: row[k] for k in ('keep', 'protected', 'note', 'emphasis', 'zoom')},
                          **{k: visual[k] for k in visuals.FIELDS},
                          **({'broll_identity': visual['broll_identity']} if visual.get('broll_identity') else {})})
            if not visual.get('broll_identity'):clean[-1].pop('broll_identity', None)
        if not any(r['keep'] for r in clean): raise ValueError('Keep at least one source interval.')
        if clean != [visuals.row_defaults(r) for r in board['rows']]:
            board.update(rows=clean, version=board['version'] + 1, approved_revision=None)
            write(edit / 'board.json', board)
        return view(edit, board, ctx)


def artifacts(path):
    return fingerprint([path / x for x in ('decisions.json', 'report.json', 'plan.json', 'board-rows.json')])


def preview(edit, expected_version):
    edit = Path(edit).resolve()
    with locked(edit):
        board, ctx = current(edit, expected_version)
        for rev in revisions(edit):
            if rev['board_version'] == board['version'] and rev['state'] in ('rendering', 'ready') and rev.get('native_state') != 'blocked':
                if rev['state'] == 'rendering': return {'revision': rev}
                try:
                    checked_revision(edit, rev['id'], board, ctx)
                    return {'revision': rev}
                except (OSError, ValueError, KeyError):
                    rev.update(state='failed', error='Preview artifacts changed or disappeared. A separate preview was requested.')
                    write(revision_dir(edit, rev['id']) / 'revision.json', rev)
        rid = uuid.uuid4().hex
        path = edit / 'board-revisions' / rid; path.mkdir(parents=True)
        frames = [[r['start_frame'], r['end_frame']] for r in board['rows'] if r['keep']]
        fps, zooms, record = ctx['fps'], [], 0
        for row in board['rows']:
            if not row['keep']: continue
            duration = row['end_frame'] - row['start_frame']
            zooms.append({'start': record / fps, 'end': (record + duration) / fps,
                          'kind': 'punch', 'scale': row['zoom'], 'ease_s': 0})
            record += duration
        write(path / 'decisions.json', [{'start': a / fps, 'end': b / fps} for a, b in frames])
        write(path / 'report.json', {'source': ctx['source'], 'fps': fps, 'duration': ctx['total_frames'] / fps, 'frames': frames})
        write(path / 'plan.json', {'durationInFrames': record, 'zooms': zooms})
        write(path / 'board-rows.json', board['rows'])
        rev = {'id': rid, 'created': time.time(), 'state': 'rendering', 'board_version': board['version'],
               'fingerprint': ctx['fingerprint'], 'artifact_digest': artifacts(path), 'approved': False,
               'native_state': None, 'selected_frames': record, 'error': None}
        write(path / 'revision.json', rev)
        try:
            with (path / 'render.log').open('wb') as log:
                import run
                py = run.venv_python()
                process = subprocess.Popen([str(py) if py.exists() else sys.executable, str(Path(__file__).resolve()), '--render', str(path)],
                                           stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                           start_new_session=True)
            threading.Thread(target=process.wait, daemon=True).start()
        except OSError as exc:
            rev.update(state='failed', error=str(exc)); write(path / 'revision.json', rev)
        return {'revision': rev}


def run_renderer(command, timeout=1800, output=None):
    """Bound the complete render process tree, including FFmpeg descendants."""
    child = subprocess.Popen(command, start_new_session=os.name == 'posix', stdout=output,
                             stderr=subprocess.STDOUT if output is not None else None)
    try:
        code = child.wait(timeout=timeout)
        if code: raise subprocess.CalledProcessError(code, command)
    except BaseException:
        if os.name == 'posix':
            try: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            # The parent can exit before a descendant; ensure the group is gone.
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        else:
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True, timeout=10)
        child.wait()
        raise


def _render_revision(path):
    meta = read(path / 'revision.json')
    meta['pid'] = os.getpid(); write(path / 'revision.json', meta)
    try:
        if artifacts(path) != meta['artifact_digest']: raise ValueError('Revision files changed.')
        report = read(path / 'report.json')
        run_renderer([sys.executable, str(RENDER), report['source'], str(path), '--no-hw', '--max', '720'])
        rows = read(path / 'board-rows.json')
        if any(r.get('caption_enabled') or r.get('motion', 'none') != 'none' or r.get('broll') or r.get('zoom', 1) != 1 for r in rows):
            bundle = visuals.compile_bundle(path, rows, report)
            visuals.render_preview(path, rows, bundle)
            visuals.verify_bundle(path)
            meta['visual_digest'] = visuals.file_hash(path / 'visuals.json')
        if artifacts(path) != meta['artifact_digest']: raise ValueError('Revision files changed during rendering.')
        st = (path / 'cut.mp4').stat()
        meta.update(state='ready', preview_stat=[st.st_size, st.st_mtime_ns])
    except Exception as exc:
        meta.update(state='failed', error='Preview failed: ' + str(exc)[:500])
    write(path / 'revision.json', meta)


def checked_revision(edit, rid, board, ctx):
    path = revision_dir(edit, rid); rev = read(path / 'revision.json')
    if (rev['board_version'] != board['version'] or rev['fingerprint'] != ctx['fingerprint']
            or rev['state'] != 'ready' or artifacts(path) != rev['artifact_digest']):
        raise ValueError('This revision changed, failed or is still rendering. Preview the current board first.')
    st = (path / 'cut.mp4').stat()
    if [st.st_size, st.st_mtime_ns] != rev['preview_stat']:
        raise ValueError('The preview changed. Create a new preview before approval.')
    if rev.get('visual_digest'):
        if visuals.file_hash(path / 'visuals.json') != rev['visual_digest']:
            raise ValueError('Visual decisions changed. Build and approve a new preview.')
        visuals.verify_bundle(path)
    return path, rev


def approve(edit, revision_id, expected_version):
    edit = Path(edit).resolve()
    with locked(edit):
        board, ctx = current(edit, expected_version)
        path, rev = checked_revision(edit, revision_id, board, ctx)
        rev.update(approved=True); write(path / 'revision.json', rev)
        board['approved_revision'] = revision_id; write(edit / 'board.json', board)
        return view(edit, board, ctx)


def send_to_resolve(edit, revision_id, expected_version):
    edit = Path(edit).resolve()
    with locked(edit):
        board, ctx = current(edit, expected_version)
        path, rev = checked_revision(edit, revision_id, board, ctx)
        if board['approved_revision'] != revision_id or not rev['approved']:
            raise ValueError('Approve the current preview before sending this revision to Resolve.')
        if rev['native_state'] == 'ready': return rev['native_result']
        if rev['native_state'] or (path / resolve.MANIFEST).exists():
            raise ValueError('Resolve creation was interrupted or incomplete. Inspect its manifest; it will not be replayed.')
        status = resolve.status()
        if not status.get('connected'): raise ValueError(status.get('message') or 'Connect Resolve first.')
        rev['native_state'] = 'sending'; write(path / 'revision.json', rev)
        try:
            result = resolve.create_timeline(path, name=f'GenMedia {edit.name[:50]} · board {board["version"]} · {revision_id[:6]}')
            rev.update(native_state='ready' if result.get('ok') else 'blocked', native_result=result)
            write(path / 'revision.json', rev)
        except Exception:
            rev['native_state'] = 'blocked'; write(path / 'revision.json', rev)
            raise
        if not result.get('ok'): raise ValueError(result.get('message') or 'Resolve did not finish; inspect the revision.')
        return result


def _sample_review(path):
    if (path / 'review.json').exists(): return
    with (path / 'sample-render.log').open('wb') as log:
        run_renderer([sys.executable, str(RENDER), str(path / 'source.mp4'), str(path), '--no-hw', '--max', '720'],
                     timeout=120, output=log)
    sys.path.insert(0, str(HERE.parent))
    import review
    from types import SimpleNamespace
    review.cmd_start(SimpleNamespace(stage='cut', video=str(path / 'cut.mp4'), transcript=None, plan=None,
                                    note='Synthetic board sample. Use Edit board for source decisions, preview approval and Resolve revisions.',
                                    name='Edit board sample (synthetic)', raw=False), path)
    data = read(path / 'review.json'); data.update(sample=True, agent_backend='codex')
    write(path / 'review.json', data)


def _make_sample(root):
    """Original synthetic material; never uses a provider or represents a real transcription."""
    path = Path(root) / 'edits' / 'edit-board-sample'
    path.mkdir(parents=True, exist_ok=True)
    if (path / 'board.json').exists():
        _sample_review(path)
        return load(path)
    source = path / 'source.mp4'
    if source.exists(): raise ValueError('A partial sample exists. Inspect edit-board-sample before recreating it.')
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '8',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(source)], check=True, timeout=30)
    write(path / 'report.json', {'source': str(source), 'fps': 30, 'frames': [[0, 60], [120, 240]]})
    write(path / 'decisions.json', [{'start': 0, 'end': 2}, {'start': 4, 'end': 8}])
    with locked(path):
        board, ctx = current(path)
        board['sample'] = True
        for row, text in zip(board['rows'], ('Opening · synthetic label', 'Demonstration hold · restore to keep', 'Result · synthetic label')):
            row['text'] = text
        write(path / 'board.json', board)
    _sample_review(path)
    return load(path)


def create_sample(root):
    folder = Path(root) / 'edits'
    folder.mkdir(parents=True, exist_ok=True)
    with locked(folder):
        return _make_sample(root)


if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--render':
    _render_revision(Path(sys.argv[2]).resolve())
