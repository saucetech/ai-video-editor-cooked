"""Private same-user mailbox for Resolve's built-in Lua Console.

Only the adapter's fixed vendor methods are exposed. No socket, shell, eval or
arbitrary file operation is available through a request.
"""
import json
import os
import time
import uuid
from pathlib import Path

METHODS = {
    'Resolve': {'GetVersionString', 'GetProjectManager'},
    'ProjectManager': {'GetCurrentProject', 'SaveProject'},
    'Project': {'GetUniqueId', 'GetName', 'GetMediaPool', 'GetCurrentTimeline', 'SetCurrentTimeline',
                'GetTimelineCount', 'GetTimelineByIndex'},
    'MediaPool': {'ImportMedia', 'CreateEmptyTimeline', 'AppendToTimeline'},
    'MediaPoolItem': {'GetUniqueId', 'GetClipProperty'},
    'Timeline': {'GetUniqueId', 'GetName', 'SetSettings', 'GetSettings', 'GetStartFrame',
                 'GetTrackCount', 'GetItemListInTrack'},
    'TimelineItem': {'GetUniqueId', 'GetStart', 'GetEnd', 'GetDuration', 'GetSpeed', 'GetClipEnabled',
                     'GetLeftOffset', 'GetRightOffset', 'GetMediaPoolItem', 'GetProperties', 'SetProperties'},
}


def write_private(path, value, raw=False):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            if raw:
                stream.write(value)
            else:
                json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def available(runtime):
    path = Path(runtime) / 'resolve-lua/ready.json'
    try:
        return time.time() - path.stat().st_mtime < 5 and bool(json.loads(path.read_text(encoding='utf-8'))['generation'])
    except (OSError, ValueError, KeyError):
        return False


def needs_attention(runtime):
    folder = Path(runtime) / 'resolve-lua'
    if (folder / 'client.lock').exists():
        return True
    try:
        return bool(json.loads((folder / 'ready.json').read_text(encoding='utf-8')).get('generation'))
    except (OSError, ValueError):
        return False


def stop(runtime, timeout=2):
    folder = Path(runtime) / 'resolve-lua'
    try:
        ready = json.loads((folder / 'ready.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        ready = {}
    generation = ready.get('generation') or ready.get('stopped_generation')
    if generation:
        write_private(folder / 'stop', generation, raw=True)
        deadline = time.monotonic() + timeout
        while ready.get('stopped_generation') != generation and time.monotonic() < deadline:
            time.sleep(.03)
            try:
                ready = json.loads((folder / 'ready.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
        if ready.get('stopped_generation') != generation:
            return {'ok':True, 'stopped':False, 'message':'Stop requested. Resolve may still be finishing an operation. Inspect its timeline and manifest, then press Stop again before restarting the helper.'}
        try:
            lock = json.loads((folder / 'client.lock').read_text(encoding='utf-8'))
            if lock.get('state') == 'quarantined' and lock.get('generation') == generation:
                (folder / 'client.lock').unlink()
        except (OSError, ValueError):
            pass
    return {'ok':True, 'stopped':True, 'message':'Local Resolve connection stopped. Inspect any incomplete timeline before restarting the Console command; no work will be replayed.'}


class Proxy:
    def __init__(self, session, ref, kind):
        self.session, self.ref, self.kind = session, ref, kind

    def __getattr__(self, method):
        if method not in METHODS.get(self.kind, set()):
            raise AttributeError('Unsupported Resolve method: ' + method)
        return lambda *args: self.session.call(self.ref, method, args)


class Session:
    def __init__(self, runtime, timeout=15):
        self.folder = Path(runtime) / 'resolve-lua'
        self.timeout, self.id = timeout, uuid.uuid4().hex
        self.resolve = self.proxy('resolve', 'Resolve')
        self.lock, self.poisoned = None, False

    def __enter__(self):
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.folder.chmod(0o700)
        try:
            self.lock = os.open(self.folder / 'client.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RuntimeError('Another Resolve operation is active. Inspect it before removing resolve-lua/client.lock.') from None
        try:
            self.generation = json.loads((self.folder / 'ready.json').read_text(encoding='utf-8'))['generation']
            write_private(self.folder / 'client.lock', {'session':self.id, 'generation':self.generation, 'state':'active'})
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if self.lock is not None:
            os.close(self.lock)
            if not self.poisoned:
                (self.folder / 'client.lock').unlink(missing_ok=True)
            self.lock = None

    def proxy(self, ref, kind):
        return Proxy(self, ref, kind)

    def _pack(self, value):
        if isinstance(value, Proxy):
            if value.session is not self:
                raise ValueError('Resolve handle belongs to another operation.')
            return {'$ref': value.ref}
        if isinstance(value, (tuple, list)):
            return [self._pack(v) for v in value]
        if isinstance(value, dict):
            return {k:self._pack(v) for k,v in value.items()}
        return value

    def _unpack(self, value):
        if isinstance(value, dict):
            if set(value) == {'$ref', '$kind'}:
                if value['$kind'] not in METHODS:
                    raise RuntimeError('Invalid Resolve object type.')
                return self.proxy(value['$ref'], value['$kind'])
            return {k:self._unpack(v) for k,v in value.items()}
        if isinstance(value, list):
            return [self._unpack(v) for v in value]
        return value

    def call(self, target, method, args):
        if self.poisoned:
            raise RuntimeError('Resolve operation requires explicit recovery. No further request was sent.')
        request = {'id':uuid.uuid4().hex, 'session':self.id, 'generation':self.generation,
                   'expires':time.time()+self.timeout, 'target':target, 'method':method, 'args':self._pack(args)}
        write_private(self.folder / 'request.json', request)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                response = json.loads((self.folder / 'response.json').read_text(encoding='utf-8'))
                if isinstance(response, dict) and response.get('id') == request['id'] and response.get('generation') == self.generation:
                    if 'error' in response:
                        self._quarantine()
                        raise RuntimeError('Resolve Lua: ' + str(response['error'])[:1200])
                    try:
                        if 'result' not in response:
                            raise RuntimeError('Resolve returned no result; explicit recovery is required.')
                        return self._unpack(response['result'])
                    except RuntimeError:
                        self._quarantine()
                        raise
            except (OSError, ValueError):
                pass
            time.sleep(.02)
        self._quarantine()
        raise RuntimeError('Resolve Lua did not respond. The request was not retried; inspect the timeline and manifest, then Stop the connection for explicit recovery.')

    def _quarantine(self):
        self.poisoned = True
        write_private(self.folder / 'client.lock', {'session':self.id, 'generation':self.generation, 'state':'quarantined'})


def install(runtime, utility):
    folder = Path(runtime) / 'resolve-lua'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    template = Path(__file__).with_name('resolve_helper.lua').read_text(encoding='utf-8')
    source = template.replace('__RUNTIME__', json.dumps(str(folder), ensure_ascii=False))
    source = source.replace('__METHODS__', json.dumps(json.dumps({k:sorted(v) for k,v in METHODS.items()})))
    helper = folder / 'helper.lua'
    helper.write_text(source, encoding='utf-8')
    helper.chmod(0o600)
    command = 'dofile(' + json.dumps(str(helper), ensure_ascii=False) + ')'
    menu = Path(utility) / 'cooked_resolve_bridge.lua'
    menu.write_text('-- Local cooked helper. Use this same line in Workspace > Console if the menu does not execute.\n' + command + '\n', encoding='utf-8')
    return menu, command
