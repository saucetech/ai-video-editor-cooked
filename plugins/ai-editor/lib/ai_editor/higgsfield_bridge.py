"""Local authenticated Higgsfield CLI adapter. Stdlib only; never reads auth files.

Connect/list/model calls are read-only. Quotes accept metadata-validated text-only
parameters. Submission requires a separate, short-lived, single-use quote confirmation.
"""
import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


class HiggsfieldError(RuntimeError):
    """Safe-to-display adapter error (raw CLI/network errors never escape)."""


MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
QUOTE_SECONDS = 600
MAX_QUOTES = 128
_QUOTE_LOCK = threading.Lock()
_IMPORT_LOCK = threading.Lock()
_QUOTES = {}
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
_MEDIA_PARAM = re.compile(r'(image|video|audio|media|reference|upload|file|path|url|mask|input)', re.I)
_RESERVED_PARAMS = {'json', 'help', 'no_color', 'wait', 'wait_timeout', 'wait_interval'}
_MEDIA = {
    '.png': ('image/png', 'image'), '.jpg': ('image/jpeg', 'image'),
    '.jpeg': ('image/jpeg', 'image'), '.webp': ('image/webp', 'image'),
    '.gif': ('image/gif', 'image'), '.mp4': ('video/mp4', 'video'),
    '.mov': ('video/quicktime', 'video'), '.webm': ('video/webm', 'video'),
}


def _identifier(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise HiggsfieldError('Invalid Higgsfield ' + label + '.')
    return value


def _run(*args, timeout=60):
    executable = shutil.which('higgsfield')
    if not executable and Path('/opt/homebrew/bin/higgsfield').is_file():
        executable = '/opt/homebrew/bin/higgsfield'
    if not executable:
        raise HiggsfieldError('Higgsfield CLI is unavailable. Install it and sign in from your terminal.')
    try:
        completed = subprocess.run(
            [executable, *args, '--json', '--no-color'], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding='utf-8', timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HiggsfieldError('Higgsfield request timed out.') from None
    except (OSError, UnicodeError):
        raise HiggsfieldError('Higgsfield CLI could not be started or returned unreadable output.') from None
    if completed.returncode:
        # CLI diagnostics may contain account records, prompt text or signed URLs.
        raise HiggsfieldError('Higgsfield request failed. Check CLI sign-in and account availability in your terminal.')
    try:
        return json.loads(completed.stdout)
    except (ValueError, TypeError):
        raise HiggsfieldError('Higgsfield CLI returned an unsupported response.') from None


def status():
    """Check current CLI account without returning email, tokens or raw diagnostics."""
    try:
        account = _run('account', 'status', timeout=20)
        if not isinstance(account, dict) or not _number(account.get('credits')):
            raise HiggsfieldError('Higgsfield account response is unavailable.')
        return {'connected': True, 'state': 'connected', 'credits': account['credits']}
    except HiggsfieldError as exc:
        return {'connected': False, 'state': 'disconnected', 'credits': None, 'error': str(exc)}


def _kind(kind):
    if kind not in ('image', 'video'):
        raise HiggsfieldError('Choose image or video results.')
    return kind


def _public_address(value):
    address = ipaddress.ip_address(value)
    return address.is_global and not address.is_multicast and not address.is_reserved


def _validate_url(url):
    """Validate syntax/literal hosts before DNS; all resolved addresses checked at connect."""
    if not isinstance(url, str) or len(url) > 16384 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise HiggsfieldError('Invalid Higgsfield media URL.')
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError:
        raise HiggsfieldError('Invalid Higgsfield media URL.') from None
    if parts.scheme != 'https' or not host or parts.username is not None or parts.password is not None or port not in (None, 443):
        raise HiggsfieldError('Media downloads require HTTPS without credentials on port 443.')
    host = host.rstrip('.').lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '%' in host or '\\' in parts.netloc:
        raise HiggsfieldError('Private media hosts are not allowed.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not _public_address(address):
        raise HiggsfieldError('Private media hosts are not allowed.')
    return parts


def _url_or_none(url):
    if not url:
        return None
    try:
        _validate_url(url)
        return url
    except HiggsfieldError:
        return None


def _normalize(job, kind=None):
    if not isinstance(job, dict):
        raise HiggsfieldError('Higgsfield returned an unsupported job record.')
    job_id = _identifier(job.get('id'), 'job ID')
    state = str(job.get('status') or 'unknown').lower()
    # Only the documented completed state authorizes fetching result media.
    completed = state == 'completed'
    result_url = _url_or_none(job.get('result_url')) if completed else None
    ext = Path(urlsplit(result_url).path).suffix.lower() if result_url else ''
    actual_kind = _MEDIA.get(ext, (None, kind))[1]
    return {
        'id': job_id, 'job_id': job_id, 'status': state,
        'model': job.get('job_type'), 'display_name': job.get('display_name'),
        'kind': actual_kind or kind, 'created_at': job.get('created_at'),
        'result_url': result_url,
        'thumbnail_url': _url_or_none(job.get('thumbnail_url')) if completed else None,
        'importable': bool(completed and result_url and ext in _MEDIA),
    }


def recent(kind='video', limit=12):
    """Return recent normalized jobs; unfinished jobs never expose result URLs."""
    _kind(kind)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise HiggsfieldError('Result limit must be between 1 and 50.')
    jobs = _run('generate', 'list', '--' + kind, '--size', str(limit))
    if not isinstance(jobs, list):
        raise HiggsfieldError('Higgsfield returned an unsupported job list.')
    return [_normalize(job, kind) for job in jobs[:limit]]


def models(kind='video'):
    """Fetch the live CLI catalog. Parameter definitions are fetched again at quote time."""
    _kind(kind)
    catalog = _run('model', 'list', '--' + kind)
    if not isinstance(catalog, list):
        raise HiggsfieldError('Higgsfield returned an unsupported model catalog.')
    return [{k: model.get(k) for k in ('job_type', 'display_name', 'type')}
            for model in catalog if isinstance(model, dict)]


def _open_https(url):
    """Pin the socket to a checked public DNS answer while preserving TLS SNI/verification."""
    parts = _validate_url(url)
    host = parts.hostname.rstrip('.')
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = [answer[4][0] for answer in answers]
        if not addresses or any(not _public_address(addr) for addr in addresses):
            raise HiggsfieldError('Private media hosts are not allowed.')
        connection = http.client.HTTPSConnection(host, port=443, timeout=30)
        # HTTPSConnection retains the original hostname for certificate validation;
        # socket resolution cannot swap it for an internal destination after validation.
        pinned = addresses[0]
        connection._create_connection = lambda address, timeout, source_address=None: socket.create_connection(
            (pinned, 443), timeout, source_address)
        connection.request('GET', urlunsplit(('', '', parts.path or '/', parts.query, '')),
                           headers={'Accept': 'image/*,video/*', 'Accept-Encoding': 'identity'})
        return connection, connection.getresponse()
    except HiggsfieldError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        if 'connection' in locals():
            connection.close()
        raise HiggsfieldError('Higgsfield media could not be downloaded.') from None


def _magic_ok(data, extension):
    if extension == '.png':
        return data.startswith(b'\x89PNG\r\n\x1a\n')
    if extension in ('.jpg', '.jpeg'):
        return data.startswith(b'\xff\xd8\xff')
    if extension == '.gif':
        return data.startswith((b'GIF87a', b'GIF89a'))
    if extension == '.webp':
        return data.startswith(b'RIFF') and data[8:12] == b'WEBP'
    if extension == '.webm':
        return data.startswith(b'\x1a\x45\xdf\xa3')
    if extension in ('.mp4', '.mov'):
        return len(data) >= 12 and data[4:8] == b'ftyp'
    return False


def _download(url, destination):
    """Bounded HTTPS download with per-hop SSRF checks, media MIME and magic validation."""
    destination = Path(destination)
    ext = destination.suffix.lower()
    if ext not in _MEDIA:
        raise HiggsfieldError('Unsupported Higgsfield image/video extension.')
    temp_path = None
    current = url
    try:
        for redirect in range(4):
            _validate_url(current)
            connection, response = _open_https(current)
            try:
                if response.status in (301, 302, 303, 307, 308):
                    target = response.getheader('Location')
                    if not target or redirect == 3:
                        raise HiggsfieldError('Higgsfield media has too many or invalid redirects.')
                    current = urljoin(current, target)
                    _validate_url(current)
                    continue
                if response.status != 200:
                    raise HiggsfieldError('Higgsfield media is unavailable or its link expired.')
                content_type = response.getheader('Content-Type', '').split(';', 1)[0].strip().lower()
                if content_type != _MEDIA[ext][0]:
                    raise HiggsfieldError('Downloaded media type does not match its extension.')
                length = response.getheader('Content-Length')
                if length is not None:
                    try:
                        expected = int(length)
                    except (ValueError, TypeError):
                        raise HiggsfieldError('Invalid media size.') from None
                    if not 0 < expected <= MAX_DOWNLOAD_BYTES:
                        raise HiggsfieldError('Media exceeds the download limit or is empty.')
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest, size, first = hashlib.sha256(), 0, b''
                with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.higgsfield-', delete=False) as output:
                    temp_path = Path(output.name)
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_DOWNLOAD_BYTES:
                            raise HiggsfieldError('Media exceeds the download limit.')
                        first = (first + chunk)[:32]
                        digest.update(chunk)
                        output.write(chunk)
                if not size or not _magic_ok(first, ext) or (length is not None and size != expected):
                    raise HiggsfieldError('Downloaded data is not valid media or is incomplete.')
                os.replace(temp_path, destination)
                temp_path = None
                return {'bytes': size, 'sha256': digest.hexdigest(), 'content_type': content_type}
            finally:
                response.close()
                connection.close()
    except HiggsfieldError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise HiggsfieldError('Higgsfield media download failed.') from None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def import_result(job_id, library):
    """Import one explicitly selected completed result into videos/higgsfield with provenance."""
    _identifier(job_id, 'job ID')
    job = _normalize(_run('generate', 'get', job_id))
    if job['id'] != job_id or not job['importable']:
        raise HiggsfieldError('Selected job is not a completed image/video with an importable result.')
    url = job['result_url']
    ext = Path(urlsplit(url).path).suffix.lower()
    lib = Path(library).expanduser().resolve()
    directory = lib / 'videos' / 'higgsfield'
    destination = directory / (job_id + ext)
    provenance_path = directory / (job_id + '.json')
    if not destination.resolve().is_relative_to(lib) or not provenance_path.resolve().is_relative_to(lib):
        raise HiggsfieldError('Higgsfield import folder must be inside the media library.')
    with _IMPORT_LOCK:
        try:
            existing = json.loads(provenance_path.read_text(encoding='utf-8'))
            if (destination.is_file() and existing.get('job_id') == job_id and
                    existing.get('sha256') == hashlib.sha256(destination.read_bytes()).hexdigest()):
                return {'job_id': job_id, 'path': str(destination), 'provenance': str(provenance_path),
                        'kind': job['kind'], 'status': 'imported'}
        except (OSError, ValueError):
            pass
        metadata = _download(url, destination)
        parts = urlsplit(url)
        provenance = {
            'provider': 'higgsfield', 'job_id': job_id, 'model': job['model'],
            'created_at': job['created_at'], 'imported_at': datetime.now(timezone.utc).isoformat(),
            'kind': job['kind'], 'source_url': urlunsplit((parts.scheme, parts.netloc, parts.path, '', '')),
            **metadata,
        }
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                             prefix='.provenance-', delete=False) as output:
                tmp = Path(output.name)
                json.dump(provenance, output, indent=2)
                output.write('\n')
            os.replace(tmp, provenance_path)
        except OSError:
            raise HiggsfieldError('Media downloaded, but its provenance could not be saved. Import again to recover.') from None
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return {'job_id': job_id, 'path': str(destination), 'provenance': str(provenance_path),
                'kind': job['kind'], 'status': 'imported'}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _quote_params(schema, params):
    if not isinstance(params, dict) or not params or len(params) > 32:
        raise HiggsfieldError('Supply text-only model parameters including a creative prompt.')
    definitions = schema.get('params')
    if not isinstance(definitions, list):
        raise HiggsfieldError('Current model parameter definitions are unavailable.')
    by_name = {p['name']: p for p in definitions if isinstance(p, dict) and isinstance(p.get('name'), str)}
    args, clean = [], {}
    for key, value in params.items():
        normalized = key.replace('-', '_') if isinstance(key, str) else ''
        if (_MEDIA_PARAM.search(normalized) or normalized in _RESERVED_PARAMS or
                not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', normalized) or normalized not in by_name):
            raise HiggsfieldError('Unsupported parameter or media upload requested. This integration supports text-only quotes.')
        definition = by_name[normalized]
        typ = definition.get('type')
        valid = ((typ == 'string' and isinstance(value, str) and len(value) <= 20000) or
                 (typ in ('number', 'float') and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)) or
                 (typ in ('integer', 'int') and isinstance(value, int) and not isinstance(value, bool)) or
                 (typ in ('boolean', 'bool') and isinstance(value, bool)))
        if not valid or ('enum' in definition and value not in definition['enum']):
            raise HiggsfieldError('Invalid value for Higgsfield parameter ' + normalized + '.')
        if normalized in clean:
            raise HiggsfieldError('Duplicate Higgsfield parameter.')
        clean[normalized] = value
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        # An equals-form argument cannot turn a prompt beginning with -- into a new flag.
        args.append('--' + normalized.replace('_', '-') + '=' + rendered)
    for name, definition in by_name.items():
        if definition.get('required') and definition.get('default') is None and name not in clean:
            raise HiggsfieldError('Missing required model parameter ' + name + '.')
    if not isinstance(clean.get('prompt'), str) or not clean['prompt'].strip():
        raise HiggsfieldError('A non-empty text prompt is required.')
    return clean, args


def quote(model, params):
    """Estimate a text-only request with current CLI metadata; never upload or create a job."""
    _identifier(model, 'model ID')
    schema = _run('model', 'get', model)
    if not isinstance(schema, dict):
        raise HiggsfieldError('Current model definition is unavailable.')
    canonical = _identifier(schema.get('job_type'), 'model ID')
    clean, args = _quote_params(schema, params)
    cost = _run('generate', 'cost', canonical, *args)
    if not isinstance(cost, dict) or not _number(cost.get('credits')):
        raise HiggsfieldError('Higgsfield did not return a usable credit estimate.')
    now = time.time()
    quote_id = secrets.token_urlsafe(24)
    public = {'id': quote_id, 'quote_id': quote_id, 'model': canonical, 'credits': cost['credits'],
              'params': clean, 'expires_at': now + QUOTE_SECONDS, 'submitted': False}
    with _QUOTE_LOCK:
        monotonic = time.monotonic()
        for key in list(_QUOTES):
            if _QUOTES[key]['deadline'] <= monotonic:
                del _QUOTES[key]
        if len(_QUOTES) >= MAX_QUOTES:
            raise HiggsfieldError('Too many open quotes. Wait for earlier quotes to expire.')
        _QUOTES[quote_id] = {'model': canonical, 'args': tuple(args), 'deadline': monotonic + QUOTE_SECONDS,
                             'used': False}
    return public


def generate(quote_id, confirmed=False):
    """Submit exactly once after the displayed quote receives explicit confirmation.

    A lost response remains unknown. The quote is consumed before the external
    side effect, so retries/concurrent requests cannot duplicate paid work.
    """
    if confirmed is not True:
        raise HiggsfieldError('Explicit confirmation of the displayed quote is required.')
    if not isinstance(quote_id, str):
        raise HiggsfieldError('Invalid Higgsfield quote ID.')
    with _QUOTE_LOCK:
        saved = _QUOTES.get(quote_id)
        if saved is None or saved['used'] or saved['deadline'] <= time.monotonic():
            raise HiggsfieldError('Quote is expired, already submitted or unavailable. Check recent jobs before requesting a new quote.')
        saved['used'] = True
        model, args = saved['model'], saved['args']
    try:
        result = _run('generate', 'create', model, *args)
        if isinstance(result, list) and len(result) == 1:
            result = result[0]
        job = _normalize(result)
    except HiggsfieldError:
        raise HiggsfieldError('Submission outcome unknown. Check recent Higgsfield jobs before taking any further generation action; this quote cannot be retried.') from None
    return {'job_id': job['id'], 'id': job['id'], 'status': job['status'], 'model': model,
            'quote_id': quote_id, 'submitted': True}
