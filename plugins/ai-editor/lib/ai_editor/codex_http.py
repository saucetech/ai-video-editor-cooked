"""Authenticated home routes and same-machine proxy for the existing review pages."""
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

PATHS = {"/codex/state", "/codex/connect", "/codex/disconnect", "/codex/message", "/codex/respond", "/codex/cancel"}


def route(handler, method, path, body=None, home_module=None):
    if path in ("/codex.js", "/integrations.js") and method == "GET":
        handler.send(200, Path(__file__).with_name(path[1:]).read_bytes(), "text/javascript; charset=utf-8")
        return True
    import integrations_http
    if path not in PATHS and path not in integrations_http.PATHS:
        return False
    body = body or {}
    if not isinstance(body, dict):
        handler.send(400, {"error": "Expected an editor request object."})
        return True
    if home_module is None:
        # A review page has its own token and origin check. Forward only this finite route set
        # to the home server on loopback; the browser never receives its other token.
        import home
        url = home.running()
        if not url or urlsplit(url).hostname != "127.0.0.1":
            handler.send(503, {"error": "Open the cooked home page to reconnect Codex."})
            return True
        base, query = url.split("?", 1)
        request = urllib.request.Request(base.rstrip("/") + path + "?" + query,
                                         data=json.dumps(body).encode() if method == "POST" else None,
                                         headers={"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                handler.send(response.status, json.loads(response.read()))
        except urllib.error.HTTPError as exc:
            handler.send(exc.code, json.loads(exc.read()))
        except (OSError, ValueError):
            handler.send(503, {"error": "The home page connection stopped. Reopen it and connect Codex again."})
        return True
    if path in integrations_http.PATHS:
        return integrations_http.route(handler, method, path, body, home_module)
    manager = home_module.codex_jobs()
    try:
        if method == "GET" and path == "/codex/state":
            result = manager.bridge.snapshot()
        elif method != "POST":
            handler.send(405, {"error": "Use the editor button for this action."})
            return True
        elif path == "/codex/connect":
            result = manager.connect()
        elif path == "/codex/disconnect":
            manager.disconnect()
            result = manager.bridge.snapshot()
        elif path == "/codex/message":
            manager.message(body.get("text") or "")
            result = {"ok": True}
        elif path == "/codex/respond":
            manager.bridge.respond(body.get("id"), body)
            result = {"ok": True}
        elif path == "/codex/cancel":
            manager.cancel(edit=body.get("edit"))
            result = {"ok": True}
        else:
            handler.send(405, {"error": "Unsupported editor action."})
            return True
        handler.send(200, result)
    except (RuntimeError, ValueError, OSError) as exc:
        handler.send(400 if isinstance(exc, ValueError) else 503, {"error": str(exc)[:1200]})
    return True
