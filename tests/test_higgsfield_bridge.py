"""Regression contract from installed Higgsfield CLI --help and read-only JSON metadata."""
import base64
import importlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/ai-editor/lib/ai_editor'))
JOB = '11111111-2222-4333-8444-555555555555'
URL = 'https://cdn.example.org/result.png?signature=private'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/k9sAAAAASUVORK5CYII=')
SCHEMA = {'job_type': 'test_image', 'type': 'image', 'params': [
    {'name': 'prompt', 'type': 'string', 'required': True},
    {'name': 'resolution', 'type': 'string', 'required': False, 'enum': ['1k', '2k']},
    {'name': 'image_references', 'type': 'array', 'required': False},
]}


class Response(io.BytesIO):
    def __init__(self, data=PNG, mime='image/png', status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = {'Content-Type': mime, **(headers or {})}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)


class HiggsfieldTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('higgsfield_bridge'), 'Higgsfield adapter is missing')
        self.h = importlib.import_module('higgsfield_bridge')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h._QUOTES.clear()

    def cli(self, responses):
        def run(argv, **kwargs):
            self.assertIsInstance(argv, list)
            self.assertFalse(kwargs.get('shell', False))
            self.assertIn('--json', argv)
            key = tuple(x for x in argv[1:] if x not in ('--json', '--no-color'))
            value = responses[key]
            if isinstance(value, BaseException):
                raise value
            return subprocess.CompletedProcess(argv, 0, json.dumps(value), '')
        return mock.patch.object(self.h.subprocess, 'run', side_effect=run)

    def job(self, status='completed', url=URL):
        return {'id': JOB, 'status': status, 'job_type': 'test_image', 'result_url': url,
                'thumbnail_url': URL, 'created_at': '2026-10-23T00:00:00Z',
                'params': {'prompt': 'private prompt'}}

    def open_response(self, response):
        return mock.patch.object(self.h, '_open_https', return_value=(mock.Mock(), response))

    def test_status_does_not_expose_account_identifiers_or_raw_errors(self):
        with self.cli({('account', 'status'): {'credits': .54, 'email': 'private@example.org', 'token': 'secret'}}):
            state = self.h.status()
        self.assertTrue(state['connected'])
        self.assertEqual(state['credits'], .54)
        self.assertNotIn('private', json.dumps(state))
        self.assertNotIn('secret', json.dumps(state))
        with mock.patch.object(self.h.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'Bearer secret')):
            state = self.h.status()
        self.assertFalse(state['connected'])
        self.assertNotIn('secret', json.dumps(state))

    def test_list_uses_real_cli_size_and_hides_unfinished_urls_and_prompts(self):
        with self.cli({('generate', 'list', '--image', '--size', '2'): [self.job(), self.job('pending')]}):
            jobs = self.h.recent('image', 2)
        self.assertEqual(jobs[0]['id'], JOB)
        self.assertEqual(jobs[0]['kind'], 'image')
        self.assertEqual(jobs[0]['result_url'], URL)
        self.assertIsNone(jobs[1]['result_url'])
        self.assertIsNone(jobs[1]['thumbnail_url'])
        self.assertNotIn('private prompt', json.dumps(jobs))

    def test_import_completed_fixture_and_provenance_is_idempotent(self):
        with self.cli({('generate', 'get', JOB): self.job()}), self.open_response(Response()) as download:
            result = self.h.import_result(JOB, Path(self.tmp.name))
            again = self.h.import_result(JOB, Path(self.tmp.name))
        self.assertEqual(Path(result['path']).read_bytes(), PNG)
        self.assertEqual(result['path'], again['path'])
        self.assertEqual(download.call_count, 1)
        provenance = json.loads(Path(result['provenance']).read_text(encoding='utf-8'))
        self.assertEqual(provenance['job_id'], JOB)
        self.assertEqual(provenance['provider'], 'higgsfield')
        self.assertNotIn('signature', json.dumps(provenance))
        self.assertNotIn('prompt', json.dumps(provenance))
        self.assertEqual(provenance['bytes'], len(PNG))

    def test_pending_failed_or_missing_result_never_downloads(self):
        for state, url in [('pending', URL), ('failed', URL), ('completed', None)]:
            with self.subTest(state=state), self.cli({('generate', 'get', JOB): self.job(state, url)}), mock.patch.object(self.h, '_open_https') as opened:
                with self.assertRaises(self.h.HiggsfieldError):
                    self.h.import_result(JOB, Path(self.tmp.name))
                opened.assert_not_called()

    def test_download_rejects_redirect_to_private_network(self):
        redirect = Response(status=302, headers={'Location': 'https://127.0.0.1/private.png'})
        with self.open_response(redirect) as opened:
            with self.assertRaises(self.h.HiggsfieldError):
                self.h._download(URL, Path(self.tmp.name) / 'out.png')
            self.assertEqual(opened.call_count, 1)

    def test_private_dns_credentials_non_https_and_alternate_ports_are_rejected(self):
        for url in ['http://cdn.example.org/a.png', 'https://user:pass@cdn.example.org/a.png',
                    'https://127.0.0.1/a.png', 'https://[::1]/a.png', 'https://169.254.169.254/a.png',
                    'https://localhost/a.png', 'https://cdn.example.org:8000/a.png']:
            with self.subTest(url=url), self.assertRaises(self.h.HiggsfieldError):
                self.h._validate_url(url)
        with mock.patch.object(self.h.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('10.0.0.1', 443))]), mock.patch.object(self.h.http.client, 'HTTPSConnection') as connection:
            with self.assertRaises(self.h.HiggsfieldError):
                self.h._open_https(URL)
            connection.assert_not_called()

    def test_https_socket_is_pinned_to_public_dns_answer_and_retains_tls_hostname(self):
        answers = [(2, 1, 6, '', ('93.184.215.14', 443))]
        with mock.patch.object(self.h.socket, 'getaddrinfo', return_value=answers), mock.patch.object(self.h.http.client, 'HTTPSConnection') as factory:
            connection, _ = self.h._open_https(URL)
            factory.assert_called_once_with('cdn.example.org', port=443, timeout=30)
            with mock.patch.object(self.h.socket, 'create_connection') as connect:
                connection._create_connection(('cdn.example.org', 443), 30)
                connect.assert_called_once_with(('93.184.215.14', 443), 30, None)

    def test_mixed_public_private_dns_and_multicast_are_rejected(self):
        for addresses in [['93.184.215.14', '10.0.0.1'], ['224.0.0.1'], ['ff02::1']]:
            answers = [(2, 1, 6, '', (address, 443)) for address in addresses]
            with self.subTest(addresses=addresses), mock.patch.object(self.h.socket, 'getaddrinfo', return_value=answers), mock.patch.object(self.h.http.client, 'HTTPSConnection') as connection:
                with self.assertRaises(self.h.HiggsfieldError):
                    self.h._open_https(URL)
                connection.assert_not_called()

    def test_quote_cannot_be_changed_by_mutating_public_params(self):
        with self.cli({('model', 'get', 'test_image'): SCHEMA,
                       ('generate', 'cost', 'test_image', '--prompt=hello'): {'credits': 2}}):
            q = self.h.quote('test_image', {'prompt': 'hello'})
        q['params']['prompt'] = 'different request'
        with self.cli({('generate', 'create', 'test_image', '--prompt=hello'): self.job('pending')}):
            self.h.generate(q['quote_id'], confirmed=True)

    def test_simultaneous_confirmations_submit_only_once(self):
        with self.cli({('model', 'get', 'test_image'): SCHEMA,
                       ('generate', 'cost', 'test_image', '--prompt=hello'): {'credits': 2}}):
            q = self.h.quote('test_image', {'prompt': 'hello'})
        gate = threading.Barrier(2)
        outcomes = []
        def submit():
            gate.wait(timeout=2)
            try:
                outcomes.append(self.h.generate(q['quote_id'], confirmed=True))
            except self.h.HiggsfieldError as exc:
                outcomes.append(exc)
        with self.cli({('generate', 'create', 'test_image', '--prompt=hello'): self.job('pending')}) as cli:
            threads = [threading.Thread(target=submit) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)
            self.assertEqual(cli.call_count, 1)
        self.assertEqual(len([x for x in outcomes if isinstance(x, dict)]), 1)
        self.assertEqual(len([x for x in outcomes if isinstance(x, self.h.HiggsfieldError)]), 1)

    def test_download_bounds_and_media_content_are_checked_and_partial_files_removed(self):
        cases = [Response(mime='text/html'), Response(b'<html>bad</html>'),
                 Response(headers={'Content-Length': '999999999999'}), Response(PNG * 2, mime='image/png')]
        for response in cases:
            path = Path(self.tmp.name) / 'out.png'
            with self.subTest(headers=response.headers), self.open_response(response), mock.patch.object(self.h, 'MAX_DOWNLOAD_BYTES', 80):
                with self.assertRaises(self.h.HiggsfieldError):
                    self.h._download(URL, path)
                self.assertFalse(path.exists())

    def test_download_rejects_media_extension_mismatch(self):
        with self.open_response(Response(mime='video/mp4')):
            with self.assertRaises(self.h.HiggsfieldError):
                self.h._download(URL, Path(self.tmp.name) / 'out.png')

    def test_quote_reads_current_schema_and_separates_confirmation(self):
        responses = {('model', 'get', 'test_image'): SCHEMA,
                     ('generate', 'cost', 'test_image', '--prompt=hello', '--resolution=1k'): {'credits': 2}}
        with self.cli(responses) as cli:
            quoted = self.h.quote('test_image', {'prompt': 'hello', 'resolution': '1k'})
            self.assertEqual(quoted['credits'], 2)
            self.assertTrue(quoted['quote_id'])
            self.assertFalse(quoted['submitted'])
            with self.assertRaises(self.h.HiggsfieldError):
                self.h.generate(quoted['quote_id'])
            self.assertEqual(cli.call_count, 2)

    def test_media_unknown_and_invalid_values_are_rejected_before_cost(self):
        for params in [{'prompt': 'hello', 'image_references': ['/tmp/source.png']},
                       {'prompt': 'hello', 'video': '/tmp/video.mp4'},
                       {'prompt': 'hello', 'wait': True}, {'prompt': 'hello', 'resolution': '4k'},
                       {'prompt': 'hello', 'output_file': '/tmp/output'}]:
            with self.subTest(params=params), self.cli({('model', 'get', 'test_image'): SCHEMA}) as cli:
                with self.assertRaises(self.h.HiggsfieldError):
                    self.h.quote('test_image', params)
                self.assertLessEqual(cli.call_count, 1)

    def test_explicit_confirmation_submits_once_even_on_unknown_outcome(self):
        with self.cli({('model', 'get', 'test_image'): SCHEMA,
                       ('generate', 'cost', 'test_image', '--prompt=hello'): {'credits': 2}}):
            q = self.h.quote('test_image', {'prompt': 'hello'})
        with mock.patch.object(self.h.subprocess, 'run', side_effect=subprocess.TimeoutExpired('higgsfield', 30)) as cli:
            with self.assertRaisesRegex(self.h.HiggsfieldError, '[Uu]nknown'):
                self.h.generate(q['quote_id'], confirmed=True)
            with self.assertRaises(self.h.HiggsfieldError):
                self.h.generate(q['quote_id'], confirmed=True)
            self.assertEqual(cli.call_count, 1)

    def test_successful_submission_returns_job_and_consumes_quote(self):
        with self.cli({('model', 'get', 'test_image'): SCHEMA,
                       ('generate', 'cost', 'test_image', '--prompt=hello'): {'credits': 2}}):
            q = self.h.quote('test_image', {'prompt': 'hello'})
        with self.cli({('generate', 'create', 'test_image', '--prompt=hello'): self.job('pending')}):
            result = self.h.generate(q['quote_id'], confirmed=True)
        self.assertEqual(result['job_id'], JOB)
        self.assertEqual(result['status'], 'pending')
        with self.assertRaises(self.h.HiggsfieldError):
            self.h.generate(q['quote_id'], confirmed=True)

    def test_expired_quotes_and_non_boolean_confirmation_fail_closed(self):
        with self.cli({('model', 'get', 'test_image'): SCHEMA,
                       ('generate', 'cost', 'test_image', '--prompt=hello'): {'credits': 2}}):
            q = self.h.quote('test_image', {'prompt': 'hello'})
        with self.assertRaises(self.h.HiggsfieldError):
            self.h.generate(q['quote_id'], confirmed='true')
        with mock.patch.object(self.h.time, 'monotonic', return_value=10**20):
            with self.assertRaises(self.h.HiggsfieldError):
                self.h.generate(q['quote_id'], confirmed=True)

    def test_argument_ids_cannot_be_flags_or_paths(self):
        with mock.patch.object(self.h.subprocess, 'run') as cli:
            for value in ['--help', '../bad', 'x;touch /tmp/nope', 'a/b']:
                with self.assertRaises(self.h.HiggsfieldError):
                    self.h.import_result(value, Path(self.tmp.name))
                with self.assertRaises(self.h.HiggsfieldError):
                    self.h.quote(value, {'prompt': 'hello'})
            cli.assert_not_called()


if __name__ == '__main__':
    unittest.main()
