"""Atomic adapter between the existing home queue and the Codex protocol client."""
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

from codex_bridge import Bridge


class Jobs:
    def __init__(self, home, command=None):
        self.home = home
        self._closed, self._dispatch = threading.Event(), threading.Lock()
        self.bridge = Bridge(home.read()["root"], Path(__file__).resolve().parents[2], home.home().parent,
                             command=command, on_finish=self.finish, on_progress=self.progress)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def connect(self):
        if self.home.listener() is not None:
            raise ValueError("A Claude listener is active. Stop that listener before connecting Codex.")
        state = self.bridge.connect()
        self.home.update(lambda d: d.update(agent_backend="codex"))
        return state

    def _run(self):
        while not self._closed.wait(.2):
            try:
                self.pump()
            except Exception as exc:
                # Bridge failures are visible in its status. An invalid queued job must also stop.
                active = self.bridge.snapshot().get("active")
                if active:
                    self.finish(active.get("job"), "failed", str(exc))

    def pump(self):
        with self._dispatch:
            state = self.bridge.snapshot()
            if state["active"]:
                job = state["active"].get("job")
                if job:
                    current = next((j for j in self.home.read()["jobs"] if j["id"] == job["id"]), None)
                    if not current or current["state"] == "cancelled":
                        self.bridge.cancel()
                return
            if state["status"] != "connected" or self.home.read().get("agent_backend") != "codex":
                return

            def claim(d):
                job = next((j for j in d["jobs"] if j["state"] == "queued" and j["type"] not in ("modal", "modal-test", "update")
                            and not j.get("reserved") and not j.get("owner")), None)
                if job:
                    job.update(state="taken", owner="codex-" + uuid.uuid4().hex, u=time.time(), started=time.time())
                    return json.loads(json.dumps(job))
            job = self.home.update(claim)
            if not job:
                return
            try:
                edit = job.get("args", {}).get("edit")
                if edit:
                    rj = Path(edit) / "review.json"
                    if rj.exists():
                        self.home.update_review_provider(rj, "codex")
                if job["type"] == "codex-review":
                    prompt = (f"Continue the user's edit in {edit}. Read {Path(edit) / 'review.json'} and the saved notes/events. "
                              "The user just sent notes or approved a review stage. Read the relevant cut/style-edit skill, "
                              "perform that action once, update the existing review page, then end this turn. Do not run review.py wait.")
                else:
                    prompt = (f"Read {self.bridge.plugin / 'skills/start/references/home.md'} for this job type. "
                              "The adapter has already claimed this exact job; do not wait or claim another. "
                              + self.home.job_line(job, self.home.read()["root"]))
                self.bridge.submit(prompt, job=job)
            except Exception as exc:
                self.finish(job, "failed", str(exc))

    def message(self, text):
        with self._dispatch:
            return self.bridge.submit(text)

    def progress(self, job, text):
        if not job:
            return
        def change(d):
            current = next((j for j in d["jobs"] if j["id"] == job["id"]), None)
            if current and current["state"] == "taken" and current.get("owner") == job["owner"]:
                current["u"] = time.time()
                if not current["steps"] or current["steps"][-1]["text"] != text:
                    current["steps"].append({"text": text, "detail": None, "progress": None, "t": time.time(), "done": False})
        self.home.update(change)

    def finish(self, job, status, text):
        if not job:
            return
        def change(d):
            current = next((j for j in d["jobs"] if j["id"] == job["id"]), None)
            if not current or current["state"] != "taken" or current.get("owner") != job.get("owner"):
                return
            current.update(state={"completed": "done", "interrupted": "cancelled"}.get(status, "failed"), finished=time.time(), u=time.time())
            current["result"]["message"] = text[-60000:]
            if status != "completed":
                current["error"] = text[:1200] or "Codex did not complete this job."
            for step in current["steps"]:
                if not step.get("done"):
                    step.update(done=True, secs=round(time.time() - step["t"]))
        self.home.update(change)

    def cancel(self, jid=None, edit=None):
        if edit:
            with self._dispatch:
                def cancel_pending(d):
                    for pending in d["jobs"]:
                        if pending["state"] == "queued" and pending.get("args", {}).get("edit") == str(edit):
                            pending.update(state="cancelled", cancel=True, error="Stopped.")
                self.home.update(cancel_pending)
        active = self.bridge.snapshot()["active"]
        job = (active or {}).get("job")
        if jid and (not job or job["id"] != jid) or edit and (not job or job.get("args", {}).get("edit") != str(edit)):
            return
        if job:
            def change(d):
                current = next((j for j in d["jobs"] if j["id"] == job["id"]), None)
                if current and current["state"] == "taken" and current.get("owner") == job["owner"]:
                    current.update(state="cancelled", cancel=True, error="Stopped.")
            self.home.update(change)
        self.bridge.cancel()

    def disconnect(self):
        self.bridge.close()

    def close(self):
        self._closed.set()
        self.bridge.close()
        if self._worker is not threading.current_thread():
            self._worker.join(timeout=2)


def queue_review(folder, rj):
    """Called by a separate review server: queue once; never launch another agent."""
    import home
    data = home.load(rj)
    stable = {k: v for k, v in data.items() if k not in ("claude", "agent_backend")}
    key = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    def add(d):
        found = next((j for j in reversed(d["jobs"]) if j["type"] == "codex-review" and
                      j["args"].get("edit") == str(folder) and j["args"].get("review_key") == key), None)
        return found or home.queue(d, "codex-review", {"edit": str(folder), "review_key": key})
    job = home.update(add)
    return {"opened": True, "how": "codex", "command": "", "job": job["id"], "at": time.time()}
