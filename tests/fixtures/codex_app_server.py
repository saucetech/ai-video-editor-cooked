"""Deterministic stdio peer for bridge protocol tests; never calls a model."""
import json
import os
import sys


def send(**message):
    print(json.dumps(message), flush=True)


def finish(status="completed", text="Ready from Codex"):
    send(method="item/agentMessage/delta", params={"threadId": "thread-test", "itemId": "message-1", "delta": text})
    send(method="turn/completed", params={"threadId": "thread-test", "turn": {"id": "turn-test", "status": status, "error": None}})


waiting = False
for line in sys.stdin:
    msg = json.loads(line)
    method, ident = msg.get("method"), msg.get("id")
    if method == "initialize":
        send(id=ident, result={"userAgent": "bridge-test"})
    elif method == "account/read":
        send(id=ident, result={"account": {"type": os.environ.get("BRIDGE_TEST_AUTH", "chatgpt"), "email": "synthetic@example.com", "planType": "test"}, "requiresOpenaiAuth": True})
    elif method == "thread/start":
        send(id=ident, result={"thread": {"id": "thread-test"}})
    elif method == "turn/start":
        send(id=ident, result={"turn": {"id": "turn-test", "status": "inProgress"}})
        send(method="turn/started", params={"threadId": "thread-test", "turn": {"id": "turn-test"}})
        text = msg["params"]["input"][0]["text"]
        if "crash-test" in text:
            sys.exit(7)
        if "approval-test" in text:
            waiting = True
            send(id=100, method="item/commandExecution/requestApproval", params={"threadId": "thread-test", "turnId": "turn-test", "itemId": "cmd-1", "command": "ffmpeg synthetic.mp4", "reason": "Create test output"})
        elif "question-test" in text:
            waiting = True
            send(id=100, method="item/tool/call", params={"threadId": "thread-test", "turnId": "turn-test", "callId": "q-1", "tool": "editor_question", "arguments": {"question": "Which caption size?", "options": ["Large", "Small"]}})
        elif "wait-test" not in text:
            finish()
    elif method == "turn/interrupt":
        send(id=ident, result={})
        finish("interrupted", "Stopped")
    elif not method and ident == 100 and waiting:
        waiting = False
        finish(text=json.dumps(msg.get("result", {})))
