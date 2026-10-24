"""File transport contract; synthetic vendor objects, no Resolve project changes."""
import importlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/ai-editor/lib'))


class LuaTransportTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module('ai_editor.resolve_lua')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = Path(self.tmp.name)
        self.folder = self.runtime / 'resolve-lua'
        self.folder.mkdir(mode=0o700)
        self.mod.write_private(self.folder / 'ready.json', {'generation':'test-generation', 'version':'21.1.1'})

    def peer(self, transform):
        stop = threading.Event()
        self.addCleanup(stop.set)
        def run():
            seen = set()
            while not stop.wait(.005):
                try:
                    request = json.loads((self.folder / 'request.json').read_text(encoding='utf-8'))
                    if request['id'] in seen:
                        continue
                    seen.add(request['id'])
                    response = transform(request)
                    self.mod.write_private(self.folder / 'response.json', {'id':request['id'], 'generation':'test-generation', **response})
                except (OSError, ValueError):
                    continue
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        self.addCleanup(worker.join, .1)

    def test_round_trip_and_private_permissions(self):
        self.peer(lambda r: {'result':'21.1.1'})
        with self.mod.Session(self.runtime, timeout=.4) as session:
            self.assertEqual(session.resolve.GetVersionString(), '21.1.1')
            self.assertEqual((self.folder / 'request.json').stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.folder / 'client.lock').exists())

    def test_handles_are_scoped_and_marshaled_in_nested_arguments(self):
        requests = []
        def reply(r):
            requests.append(r)
            return {'result':{'$ref':'project-1', '$kind':'Project'}} if r['method']=='GetCurrentProject' else {'result':True}
        self.peer(reply)
        with self.mod.Session(self.runtime, timeout=.4) as session:
            project = session.proxy('manager', 'ProjectManager').GetCurrentProject()
            self.assertEqual(project.kind, 'Project')
            session.proxy('pool', 'MediaPool').AppendToTimeline([{'mediaPoolItem':project}])
        self.assertEqual(requests[-1]['args'][0][0]['mediaPoolItem']['$ref'], 'project-1')

    def test_unknown_methods_are_rejected_before_dispatch(self):
        with self.mod.Session(self.runtime, timeout=.1) as session:
            with self.assertRaises(AttributeError):
                session.resolve.Execute('untrusted code')
        self.assertFalse((self.folder / 'request.json').exists())

    def test_client_lock_prevents_interleaved_native_operations(self):
        with self.mod.Session(self.runtime):
            with self.assertRaisesRegex(RuntimeError, 'operation'):
                with self.mod.Session(self.runtime):
                    pass

    def test_stale_ready_is_not_a_connection(self):
        os.utime(self.folder / 'ready.json', (1,1))
        self.assertFalse(self.mod.available(self.runtime))

    def test_stop_is_scoped_to_the_current_helper_generation(self):
        def acknowledge():
            while not (self.folder / 'stop').exists():
                time.sleep(.005)
            self.mod.write_private(self.folder / 'ready.json', {'stopped_generation':'test-generation'})
        peer=threading.Thread(target=acknowledge, daemon=True); peer.start()
        self.mod.stop(self.runtime); peer.join(.2)
        self.assertEqual((self.folder / 'stop').read_text(encoding='utf-8'), 'test-generation')
        self.assertEqual((self.folder / 'stop').stat().st_mode & 0o777, 0o600)

    def test_explicit_stop_releases_only_acknowledged_quarantine(self):
        self.mod.write_private(self.folder/'client.lock', {'state':'quarantined', 'generation':'test-generation'})
        self.mod.write_private(self.folder/'ready.json', {'stopped_generation':'different-generation'})
        self.mod.stop(self.runtime)
        self.assertTrue((self.folder/'client.lock').exists())
        self.mod.write_private(self.folder/'ready.json', {'stopped_generation':'test-generation'})
        self.mod.stop(self.runtime)
        self.assertFalse((self.folder/'client.lock').exists())

    def test_pending_stop_never_claims_a_shutdown(self):
        result=self.mod.stop(self.runtime, timeout=.02)
        self.assertFalse(result['stopped'])
        self.assertTrue(self.mod.available(self.runtime))

    def test_unknown_outcome_is_not_replayed(self):
        self.peer(lambda r: {'id':'wrong-response', 'result':True})
        with self.mod.Session(self.runtime, timeout=.08) as session:
            with self.assertRaisesRegex(RuntimeError, 'not retried'):
                session.resolve.GetVersionString()
            request_before = (self.folder / 'request.json').read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'recovery'):
                session.resolve.GetProjectManager()
            self.assertEqual((self.folder / 'request.json').read_bytes(), request_before)
        self.assertTrue((self.folder / 'client.lock').exists())
        with self.assertRaisesRegex(RuntimeError, 'operation'):
            with self.mod.Session(self.runtime):
                pass
        request = json.loads((self.folder / 'request.json').read_text(encoding='utf-8'))
        self.assertLess(request['expires'], time.time() + 1)

    def test_mutation_error_quarantines_without_a_returned_timeline_handle(self):
        self.peer(lambda r: {'error':'vendor failed after accepting create'})
        with self.mod.Session(self.runtime, timeout=.2) as session:
            with self.assertRaisesRegex(RuntimeError, 'vendor failed'):
                session.proxy('pool', 'MediaPool').CreateEmptyTimeline('synthetic')
        self.assertEqual(json.loads((self.folder / 'client.lock').read_text(encoding='utf-8'))['state'], 'quarantined')


if __name__ == '__main__':
    unittest.main()
