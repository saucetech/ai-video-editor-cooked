import importlib
import http.client
import json
import os
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/ai-editor/lib/ai_editor"))
from test_codex_bridge import eventually


class CodexJobTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("codex_jobs"), "Codex job dispatch is not implemented")
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("AI_EDITOR_HOME", "AI_EDITOR_LIBRARY", "AI_EDITOR_SESSION_ID", "AI_EDITOR_JOB_ID")}
        os.environ["AI_EDITOR_HOME"] = str(Path(self.tmp.name) / "runtime")
        os.environ["AI_EDITOR_LIBRARY"] = str(Path(self.tmp.name) / "library")
        self.h = importlib.import_module("home")
        self.jobs = importlib.import_module("codex_jobs")
        self.h.update(lambda d: d.update(root=os.environ["AI_EDITOR_LIBRARY"]))
        self.manager = self.jobs.Jobs(self.h, command=[sys.executable, str(ROOT / "tests/fixtures/codex_app_server.py")])
        self.addCleanup(self.clean)

    def clean(self):
        self.manager.close()
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_queued_job_runs_once_and_records_output(self):
        job = self.h.update(lambda d: self.h.queue(d, "skill-new", {"text": "hello"}))
        self.manager.connect()
        eventually(lambda: self.h.read()["jobs"][-1]["state"] == "done")
        done = self.h.read()["jobs"][-1]
        self.assertEqual(done["id"], job["id"])
        self.assertTrue(done["owner"].startswith("codex-"))
        self.assertIn("Ready from Codex", done["result"]["message"])
        self.manager.pump()
        self.assertEqual(len(self.manager.bridge.snapshot()["messages"]), 2)

    def test_completion_and_late_script_status_cannot_resurrect_a_cancelled_job(self):
        self.h.update(lambda d: self.h.queue(d, "skill-new", {"text": "wait-test"}))
        self.manager.connect()
        eventually(lambda: self.h.read()["jobs"][-1]["state"] == "taken")
        job = self.h.read()["jobs"][-1]
        self.manager.cancel(job["id"])
        eventually(lambda: self.manager.bridge.snapshot()["active"] is None)
        self.assertEqual(self.h.read()["jobs"][-1]["state"], "cancelled")
        os.environ["AI_EDITOR_SESSION_ID"], os.environ["AI_EDITOR_JOB_ID"] = job["owner"], job["id"]
        import argparse
        self.h.cmd_status(argparse.Namespace(job="skill-new", step=None, detail=None, progress=None, result=None, done=True, failed=None, if_active=False, key=None))
        self.manager.finish(job, "completed", "late completion")
        self.assertEqual(self.h.read()["jobs"][-1]["state"], "cancelled")

    def test_job_owned_by_another_worker_is_never_taken(self):
        self.h.update(lambda d: self.h.queue(d, "skill-new", {"text": "hello"}).update(state="taken", owner="someone-else"))
        self.manager.connect()
        self.manager.pump()
        self.assertEqual(self.h.read()["jobs"][-1]["owner"], "someone-else")
        self.assertIsNone(self.manager.bridge.snapshot()["active"])

    def test_stopping_review_cancels_pending_continuations_for_only_that_edit(self):
        self.h.update(lambda d: self.h.queue(d, "codex-review", {"edit": "/synthetic/a"}))
        self.h.update(lambda d: self.h.queue(d, "codex-review", {"edit": "/synthetic/b"}))
        self.manager.cancel(edit="/synthetic/a")
        self.assertEqual([j["state"] for j in self.h.read()["jobs"]], ["cancelled", "queued"])

    def test_review_stop_forwards_cancellation_to_home(self):
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        review = importlib.import_module("review")
        edit = Path(self.tmp.name) / "review"
        edit.mkdir()
        (edit / "review.json").write_text(json.dumps({"agent_backend":"codex", "events":[{"type":"send"}],
            "stage":"cut", "round":1, "sent":True, "comments":[]}), encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", 0), review.make_handler(edit, "test-token"))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def forward(handler, method, path, body):
            if path == "/event":
                return False
            self.assertEqual((method, path, body), ("POST", "/codex/cancel", {"edit":str(edit)}))
            handler.send(200, {"ok":True})
            return True
        with patch("codex_http.route", side_effect=forward) as route:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
            conn.request("POST", "/event?t=test-token", json.dumps({"type":"stop"}), {"Content-Type":"application/json"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200, response.read())
            conn.close()
            self.assertEqual(route.call_count, 2)

    def test_review_actions_queue_for_codex_without_launching_claude(self):
        edit = Path(os.environ["AI_EDITOR_LIBRARY"]) / "edits" / "synthetic"
        edit.mkdir(parents=True)
        rj = edit / "review.json"
        rj.write_text('{"stage":"cut","round":1,"sent":true,"comments":[]}', encoding="utf-8")
        self.h.update(lambda d: d.update(agent_backend="codex"))
        review = importlib.import_module("review")
        first = review.reopen(edit, rj, force=True)
        second = review.reopen(edit, rj, force=True)
        self.assertEqual(first["how"], "codex")
        self.assertEqual(first["job"], second["job"])
        self.assertEqual(len(self.h.read()["jobs"]), 1)

    def test_http_connection_requires_token_and_delivers_a_request(self):
        from http.server import ThreadingHTTPServer
        self.h._CODEX[:] = [self.manager]
        self.addCleanup(self.h._CODEX.clear)
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.h.make_handler("test-token"))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def request(path, method="GET", data=None):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
            conn.request(method, path, body=json.dumps(data or {}) if method == "POST" else None,
                         headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            result = response.status, response.read()
            conn.close()
            return result
        self.assertEqual(request("/codex/state")[0], 403)
        code, raw = request("/codex/connect?t=test-token", "POST")
        self.assertEqual(code, 200, raw)
        self.assertEqual(json.loads(raw)["status"], "connected")
        code, raw = request("/codex/message?t=test-token", "POST", {"text": "hello"})
        self.assertEqual(code, 200, raw)
        eventually(lambda: self.manager.bridge.snapshot()["active"] is None)
        code, raw = request("/codex/state?t=test-token")
        self.assertIn("Ready from Codex", raw.decode())


if __name__ == "__main__":
    unittest.main()
