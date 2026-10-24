"""Local Codex app-server client. Authentication stays inside Codex; no tokens are read here.

One process, one active turn, private stdio. Browser answers are scoped to a connection and turn.
The reader never blocks on a human, so Stop works while an approval or question is open.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


QUESTION_TOOL = {
    "type": "function", "name": "editor_question",
    "description": "Ask the user a question in the cooked browser window. Use for choices and review approval; never ask for credentials.",
    "inputSchema": {"type": "object", "properties": {
        "question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}},
        "required": ["question"], "additionalProperties": False}}


class Bridge:
    def __init__(self, library, plugin, runtime, command=None, on_finish=None, on_progress=None):
        self.library, self.plugin, self.runtime = map(lambda p: Path(p).resolve(), (library, plugin, runtime))
        self.command = command or [shutil.which("codex") or "codex", "app-server", "--stdio"]
        self.on_finish = on_finish or (lambda *a: None)
        self.on_progress = on_progress or (lambda *a: None)
        self.process = None
        self._lock = threading.RLock()
        self._connection_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._waiting, self._seq, self._generation = {}, 0, ""
        self._status, self._error, self._account, self._login_url = "disconnected", "", None, None
        self._active, self._pending, self._messages, self._parts = None, None, [], {}

    def snapshot(self):
        with self._lock:
            return copy.deepcopy({"status": self._status, "error": self._error, "account": self._account,
                                  "loginUrl": self._login_url, "active": self._active,
                                  "pending": {k: v for k, v in (self._pending or {}).items() if not k.startswith("_")} or None,
                                  "messages": self._messages[-40:]})

    def _send(self, message, process=None):
        proc = process or self.process
        if not proc or proc.poll() is not None:
            raise RuntimeError("Codex stopped. Reconnect to continue; unfinished work was not retried.")
        with self._write_lock:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()

    def _rpc(self, method, params, timeout=40):
        with self._lock:
            self._seq += 1
            ident = self._seq
            waiter = {"event": threading.Event()}
            self._waiting[ident] = waiter
        try:
            self._send({"id": ident, "method": method, "params": params})
            if not waiter["event"].wait(timeout):
                raise RuntimeError(f"Codex did not answer {method}. Reconnect and try again.")
            result = waiter.get("message", {})
            if "error" in result:
                raise RuntimeError(str(result["error"].get("message") or "Codex request failed")[:1200])
            return result.get("result", {})
        finally:
            with self._lock:
                self._waiting.pop(ident, None)

    def connect(self):
        with self._connection_lock:
            if self.process and self.process.poll() is None and self._status not in ("failed", "disconnected"):
                return self.snapshot()
            self.close()
            self.library.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._generation = uuid.uuid4().hex
                generation = self._generation
                self._status, self._error = "connecting", ""
            try:
                self.process = subprocess.Popen(self.command, cwd=self.library, stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                text=True, encoding="utf-8", bufsize=1)
                threading.Thread(target=self._read, args=(self.process, generation), daemon=True).start()
                self._rpc("initialize", {"clientInfo": {"name": "cooked_local_editor", "title": "cooked.", "version": "0.1.0"},
                                         "capabilities": {"experimentalApi": True}})
                self._send({"method": "initialized", "params": {}})
                self._check_account()
            except Exception as exc:
                self.close()
                with self._lock:
                    self._status, self._error = "failed", str(exc)[:1200]
                raise RuntimeError(self._error) from exc
            return self.snapshot()

    def _check_account(self):
        result = self._rpc("account/read", {"refreshToken": False})
        account = result.get("account")
        if account and account.get("type") == "chatgpt":
            with self._lock:
                self._account = {k: account[k] for k in ("type", "email", "planType") if k in account}
                self._status, self._error, self._login_url = "connected", "", None
            return
        if account:
            raise RuntimeError("Connect Codex requires a ChatGPT login. Run codex login with your ChatGPT account; API billing was not used.")
        login = self._rpc("account/login/start", {"type": "chatgpt"})
        with self._lock:
            self._status, self._login_url = "signing_in", login.get("authUrl")

    def _instructions(self):
        return f"""You are the editing agent for the local cooked. browser app. The user controls this turn from that app.
Full plugin source: {self.plugin}. Creator teardown plugin: {self.plugin.parent / 'creator-teardown'}.
Library: {self.library}. Editor runtime: {self.runtime}.
Read each relevant skills/<name>/SKILL.md before doing its work. In skill instructions replace
CLAUDE_PLUGIN_ROOT with the plugin source above and CLAUDE_SKILL_DIR with the actual skill folder.
The adapter owns job dispatch: do NOT start home.py wait, another agent, Claude, a terminal or another app-server.
Use editor_question for all user questions and approvals. Never request API keys, tokens or passwords.
Run one useful stage, open the existing review page when appropriate, explain what needs review and END the turn.
Do NOT block on review.py wait; the adapter will send the next review action in a new turn.
Use home.py status for the assigned job's progress, but never report a cancelled job as done.
Local integration modules are in {self.plugin / 'lib/ai_editor'}: resolve_bridge.py and higgsfield_bridge.py.
Read their APIs before calling them. Resolve creates a separate source timeline and detects manual changes.
Higgsfield connection/list/model discovery are read-only. Quote and generation are separate: show credits,
ask explicit confirmation with editor_question, and submit the single-use quote only after the user agrees.
Never claim an import, native property or generation is finished without checking its actual result.
The Python environment is {self.runtime / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')}.
Read source media; preserve originals and manual edits. Never upload media, spend credits, publish, or delete a project
unless this user request explicitly authorizes it. A connection check does not authorize generation.
For direct app messages do the user's requested work within the library; do not manufacture a queued job.
"""

    def submit(self, text, job=None):
        text = str(text).strip()
        if not text or len(text) > 30000:
            raise ValueError("Enter a request of 1 to 30000 characters.")
        with self._lock:
            if self._status != "connected" or self._active:
                raise ValueError("Connect Codex and wait for the current request to finish first.")
            owner = (job or {}).get("owner") or "codex-" + uuid.uuid4().hex
            self._active = {"threadId": None, "turnId": None, "job": copy.deepcopy(job), "owner": owner,
                            "messageKey": uuid.uuid4().hex, "cancelled": False}
            self._parts = {}
            self._messages.append({"role": "user", "text": text})
            self._messages = self._messages[-40:]
            self._status, self._error = "working", ""
        try:
            env = {"AI_EDITOR_HOME": str(self.runtime), "AI_EDITOR_LIBRARY": str(self.library),
                   "AI_EDITOR_SESSION_ID": owner, "AI_EDITOR_JOB_ID": str((job or {}).get("id") or "")}
            vbin = self.runtime / "venv" / ("Scripts" if os.name == "nt" else "bin")
            if vbin.is_dir():
                env["PATH"] = str(vbin) + os.pathsep + os.environ.get("PATH", "")
            thread = self._rpc("thread/start", {
                "cwd": str(self.library), "ephemeral": True, "approvalPolicy": "on-request", "sandbox": "workspace-write",
                "developerInstructions": self._instructions(), "dynamicTools": [QUESTION_TOOL],
                "config": {"shell_environment_policy.set": env,
                           "sandbox_workspace_write.writable_roots": [str(self.library), str(self.runtime)]}})
            with self._lock:
                if not self._active:
                    return
                self._active["threadId"] = thread["thread"]["id"]
                tid = self._active["threadId"]
            result = self._rpc("turn/start", {"threadId": tid, "input": [{"type": "text", "text": text}]})
            with self._lock:
                if self._active:
                    self._active["turnId"] = result["turn"]["id"]
                    cancelled = self._active["cancelled"]
                else:
                    cancelled = False
            if cancelled:
                self.cancel()
        except Exception as exc:
            # An accepted start can lose its reply. Quarantine before dispatch can
            # reuse this connection, then terminate the possibly running turn.
            self._finish("failed", str(exc), connected=False)
            self.close()
            with self._lock:
                self._status, self._error = "failed", str(exc)[:1200]
            raise

    def _read(self, proc, generation):
        try:
            for line in proc.stdout:
                if generation != self._generation:
                    break
                try:
                    msg = json.loads(line)
                    if "method" not in msg:
                        with self._lock:
                            waiter = self._waiting.get(msg.get("id"))
                            if waiter:
                                waiter["message"] = msg
                                waiter["event"].set()
                    elif "id" in msg:
                        self._server_request(msg)
                    else:
                        self._event(msg["method"], msg.get("params") or {})
                except (ValueError, KeyError, TypeError):
                    continue  # a malformed notification must not approve or complete work
        finally:
            if generation == self._generation:
                error = "Codex stopped. Reconnect to continue; unfinished work was not retried."
                with self._lock:
                    self._error, self._status, self._pending = error, "failed", None
                    for waiter in self._waiting.values():
                        waiter["message"] = {"error": {"message": error}}
                        waiter["event"].set()
                self._finish("failed", error, connected=False)

    def _event(self, method, params):
        if method == "account/login/completed":
            if params.get("success"):
                threading.Thread(target=self._check_account, daemon=True).start()
            else:
                with self._lock:
                    self._status, self._error = "failed", "ChatGPT sign-in did not finish. Reconnect to try again."
            return
        with self._lock:
            active = self._active
            if not active or params.get("threadId") != active.get("threadId"):
                return
            if method == "turn/started":
                active["turnId"] = params["turn"]["id"]
            elif method == "item/agentMessage/delta":
                ident = str(params.get("itemId") or "message")
                self._parts[ident] = (self._parts.get(ident, "") + str(params.get("delta") or ""))[-60000:]
                existing = next((m for m in self._messages if m.get("id") == ident and m.get("generation") == active["messageKey"]), None)
                if existing:
                    existing["text"] = self._parts[ident]
                else:
                    self._messages.append({"role": "assistant", "text": self._parts[ident], "id": ident, "generation": active["messageKey"]})
            elif method == "item/started" and params.get("item", {}).get("type") == "commandExecution":
                self.on_progress(active.get("job"), "Running an editing step")
            elif method == "turn/completed":
                turn = params["turn"]
                status = "interrupted" if active["cancelled"] else turn.get("status", "failed")
                text = "\n\n".join(self._parts.values())
                if turn.get("error"):
                    text = str(turn["error"].get("message") or "Codex could not finish this request")
                self._finish(status, text)

    def _server_request(self, msg):
        method, params = msg["method"], msg.get("params") or {}
        with self._lock:
            active = self._active
            if not active or params.get("threadId") != active.get("threadId") or active["cancelled"]:
                self._send({"id": msg["id"], "error": {"code": -32600, "message": "This editing turn is no longer active"}})
                return
            pending = {"id": f"{self._generation}:{active.get('threadId')}:{params.get('turnId')}:{msg['id']}",
                       "_rpc": msg["id"], "_method": method}
            if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
                pending.update(kind="approval", question=params.get("reason") or "Allow Codex to make this change?",
                               command=params.get("command") or "Apply the displayed file changes")
            elif method == "item/tool/call" and params.get("tool") == "editor_question":
                args = params.get("arguments") or {}
                pending.update(kind="question", question=str(args.get("question") or "Codex needs your answer"), options=args.get("options") or [])
            elif method == "item/tool/requestUserInput":
                pending.update(kind="questions", questions=params.get("questions") or [])
            else:
                self._send({"id": msg["id"], "error": {"code": -32601, "message": "This request is not supported by the editor; no permission was granted"}})
                return
            if self._pending:
                self._send({"id": msg["id"], "error": {"code": -32600, "message": "Answer the existing editor question first"}})
                return
            self._pending, self._status = pending, "waiting"

    def respond(self, ident, body):
        with self._lock:
            pending = self._pending
            if not pending or ident != pending["id"]:
                raise ValueError("This question or approval has expired. Use the current card.")
            if pending["kind"] == "approval":
                if not isinstance(body.get("approved"), bool):
                    raise ValueError("Choose Allow once or Deny.")
                result = {"decision": "accept" if body["approved"] else "decline"}
            elif pending["kind"] == "questions":
                answers = body.get("answers")
                if not isinstance(answers, dict) or any(not isinstance(answers.get(q["id"]), str) or not answers[q["id"]].strip() for q in pending["questions"]):
                    raise ValueError("Answer every question before sending.")
                result = {"answers": {q["id"]: {"answers": [answers[q["id"]]]} for q in pending["questions"]}}
            else:
                answer = str(body.get("answer") or "").strip()
                if not answer or len(answer) > 10000:
                    raise ValueError("Enter an answer of 1 to 10000 characters.")
                result = {"contentItems": [{"type": "inputText", "text": answer}], "success": True}
            self._send({"id": pending["_rpc"], "result": result})
            self._pending, self._status = None, "working"

    def _finish(self, status, text, connected=True):
        with self._lock:
            active = self._active
            if not active:
                return
            self._active, self._pending = None, None
            self._status = "connected" if connected else "failed"
            if status == "failed":
                self._error = text[:1200]
            if text and not self._parts:
                self._messages.append({"role": "assistant", "text": text[:60000]})
        self.on_finish(active.get("job"), status, text)

    def cancel(self):
        with self._lock:
            if not self._active:
                return
            self._active["cancelled"], self._pending = True, None
            thread, turn = self._active.get("threadId"), self._active.get("turnId")
        if thread and turn:
            self._rpc("turn/interrupt", {"threadId": thread, "turnId": turn}, timeout=10)

    def close(self):
        self._finish("interrupted", "Codex disconnected. No work was retried.")
        with self._lock:
            self._generation = uuid.uuid4().hex
            proc, self.process = self.process, None
            self._pending, self._status, self._account, self._login_url = None, "disconnected", None, None
            for waiter in self._waiting.values():
                waiter["message"] = {"error": {"message": "Codex disconnected"}}
                waiter["event"].set()
        if proc:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            for stream in (proc.stdin, proc.stdout):
                if stream:
                    stream.close()
