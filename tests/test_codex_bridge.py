import importlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/ai-editor/lib/ai_editor"))


def eventually(predicate, seconds=4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError("Bridge did not reach the expected state")


class CodexBridgeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("codex_bridge"), "Connect Codex bridge is not implemented")
        self.module = importlib.import_module("codex_bridge")
        self.tmp = tempfile.TemporaryDirectory()
        self.events = []
        self.bridge = self.module.Bridge(
            Path(self.tmp.name), ROOT / "plugins/ai-editor", Path(self.tmp.name) / "runtime",
            command=[sys.executable, str(ROOT / "tests/fixtures/codex_app_server.py")],
            on_finish=lambda *args: self.events.append(args))
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.bridge.close)

    def test_connect_is_idempotent_and_requires_chatgpt(self):
        self.bridge.connect()
        proc = self.bridge.process
        self.bridge.connect()
        self.assertIs(proc, self.bridge.process)
        self.assertEqual(self.bridge.snapshot()["status"], "connected")
        self.assertEqual(self.bridge.snapshot()["account"]["type"], "chatgpt")

    def test_api_key_account_does_not_silently_use_api_billing(self):
        os.environ["BRIDGE_TEST_AUTH"] = "apiKey"
        self.addCleanup(os.environ.pop, "BRIDGE_TEST_AUTH", None)
        with self.assertRaisesRegex(RuntimeError, "ChatGPT"):
            self.bridge.connect()
        self.assertNotEqual(self.bridge.snapshot()["status"], "connected")

    def test_stream_and_completion_are_visible(self):
        self.bridge.connect()
        self.bridge.submit("hello", job={"id": "synthetic-1"})
        eventually(lambda: bool(self.events))
        self.assertEqual(self.events[0][1], "completed")
        self.assertIn("Ready from Codex", self.events[0][2])
        self.assertIsNone(self.bridge.snapshot()["active"])

    def test_consecutive_turns_keep_their_own_messages(self):
        self.bridge.connect()
        for text in ("first request", "second request"):
            self.bridge.submit(text)
            eventually(lambda: self.bridge.snapshot()["active"] is None)
        replies = [m for m in self.bridge.snapshot()["messages"] if m["role"] == "assistant"]
        self.assertEqual(len(replies), 2)

    def test_command_is_never_approved_without_a_browser_answer(self):
        self.bridge.connect()
        self.bridge.submit("approval-test")
        eventually(lambda: self.bridge.snapshot()["pending"])
        pending = self.bridge.snapshot()["pending"]
        self.assertEqual(pending["kind"], "approval")
        self.assertFalse(self.events)
        self.bridge.respond(pending["id"], {"approved": False})
        eventually(lambda: bool(self.events))
        self.assertIn("decline", self.events[0][2])
        with self.assertRaisesRegex(ValueError, "expired"):
            self.bridge.respond(pending["id"], {"approved": True})

    def test_questions_return_browser_answers_to_the_model(self):
        self.bridge.connect()
        self.bridge.submit("question-test")
        eventually(lambda: self.bridge.snapshot()["pending"])
        pending = self.bridge.snapshot()["pending"]
        self.assertEqual(pending["kind"], "question")
        self.bridge.respond(pending["id"], {"answer": "Large"})
        eventually(lambda: bool(self.events))
        self.assertIn("Large", self.events[0][2])

    def test_stop_interrupts_the_turn_and_clears_pending_approval(self):
        self.bridge.connect()
        self.bridge.submit("approval-test")
        eventually(lambda: self.bridge.snapshot()["pending"])
        self.bridge.cancel()
        eventually(lambda: bool(self.events))
        self.assertEqual(self.events[0][1], "interrupted")
        self.assertIsNone(self.bridge.snapshot()["pending"])

    def test_old_approval_cannot_approve_a_reconnected_request_with_same_rpc_id(self):
        self.bridge.connect()
        self.bridge.submit("approval-test")
        eventually(lambda: self.bridge.snapshot()["pending"])
        old = self.bridge.snapshot()["pending"]["id"]
        self.bridge.close()
        self.bridge.connect()
        self.bridge.submit("approval-test")
        eventually(lambda: self.bridge.snapshot()["pending"])
        self.assertNotEqual(old, self.bridge.snapshot()["pending"]["id"])
        with self.assertRaisesRegex(ValueError, "expired"):
            self.bridge.respond(old, {"approved": True})

    def test_process_death_marks_active_work_failed_without_retrying(self):
        self.bridge.connect()
        self.bridge.submit("crash-test", job={"id": "synthetic-1"})
        eventually(lambda: bool(self.events))
        self.assertEqual(self.events[0][1], "failed")
        self.assertIn("stopped", self.bridge.snapshot()["error"].lower())
        self.assertEqual(len(self.events), 1)

    def test_unknown_turn_start_outcome_terminates_connection_before_reuse(self):
        self.bridge.connect()
        proc, rpc = self.bridge.process, self.bridge._rpc
        def lost_ack(method, *args, **kwargs):
            result = rpc(method, *args, **kwargs)
            if method == "turn/start":
                raise RuntimeError("Simulated lost start acknowledgement")
            return result
        self.bridge._rpc = lost_ack
        with self.assertRaisesRegex(RuntimeError, "lost start"):
            self.bridge.submit("wait-test")
        self.assertIsNotNone(proc.poll())
        self.assertNotEqual(self.bridge.snapshot()["status"], "connected")
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0][1], "failed")


if __name__ == "__main__":
    unittest.main()
