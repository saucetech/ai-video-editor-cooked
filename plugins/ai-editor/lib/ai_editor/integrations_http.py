"""Finite, authenticated actions for local media integrations; callers check token and origin."""
from pathlib import Path

import higgsfield_bridge as higgsfield
import resolve_bridge as resolve

PATHS = {"/integrations/status", "/integrations/edits", "/integrations/resolve/setup",
         "/integrations/resolve/create", "/integrations/resolve/update", "/integrations/higgsfield/recent",
         "/integrations/higgsfield/import", "/integrations/higgsfield/models", "/integrations/higgsfield/quote",
         "/integrations/higgsfield/generate"}


def edits(home):
    return [{"path": str(p), "name": p.name} for p in home.library.edit_dirs() if (p / "decisions.json").is_file()]


def edit_path(value, home):
    if not isinstance(value, str) or not value:
        raise ValueError("Choose an edit from your library first.")
    path = Path(value).expanduser().resolve()
    if str(path) not in {item["path"] for item in edits(home)}:
        raise ValueError("Choose a source-cut edit from your library; unrelated paths are not accepted.")
    return path


def route(handler, method, path, body, home):
    if path not in PATHS:
        return False
    if not isinstance(body, dict):
        handler.send(400, {"error": "Expected an integration request object."})
        return True
    try:
        if path == "/integrations/status" and method == "GET":
            result = {"resolve": resolve.status(), "higgsfield": higgsfield.status()}
        elif path == "/integrations/edits" and method == "GET":
            result = {"edits": edits(home)}
        elif method != "POST":
            handler.send(405, {"error": "Use the integration button for this action."})
            return True
        elif path == "/integrations/resolve/setup":
            result = resolve.install_internal_bridge()
        elif path == "/integrations/resolve/create":
            name = body.get("name")
            if name is not None and (not isinstance(name, str) or len(name) > 120):
                raise ValueError("Use a timeline name of at most 120 characters.")
            result = resolve.create_timeline(edit_path(body.get("edit"), home), name=name or None)
        elif path == "/integrations/resolve/update":
            result = resolve.update_timeline(edit_path(body.get("edit"), home))
        elif path == "/integrations/higgsfield/recent":
            result = {"results": higgsfield.recent(kind=body.get("kind", "video"), limit=12)}
        elif path == "/integrations/higgsfield/import":
            result = higgsfield.import_result(body.get("job_id"), Path(home.read()["root"]))
        elif path == "/integrations/higgsfield/models":
            result = {"models": higgsfield.models(kind=body.get("kind", "image"))}
        elif path == "/integrations/higgsfield/quote":
            result = higgsfield.quote(body.get("model"), body.get("params"))
        elif path == "/integrations/higgsfield/generate":
            if body.get("confirmed") is not True:
                raise ValueError("Confirm the displayed credit quote before generating.")
            result = higgsfield.generate(body.get("quote_id"), confirmed=True)
        else:
            handler.send(405, {"error": "Unsupported integration action."})
            return True
        if isinstance(result, dict) and result.get("ok") is False:
            raise ValueError(result.get("message") or "The integration did not finish.")
        handler.send(200, result)
    except (ValueError, higgsfield.HiggsfieldError, resolve.BridgeError, OSError) as exc:
        handler.send(400, {"error": str(exc)[:1200]})
    return True
