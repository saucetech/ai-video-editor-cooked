# Local Resolve source-cut adapter

This is an implemented adapter with offline regression coverage. The native Resolve run is still unverified on the development machine; the connection/bootstrap observations below are separate from the fake API tests.

## Repeatable workflow

Trigger: continue an existing cooked edit in Resolve while retaining editable original media and manual work.

Inputs: an edit folder with `decisions.json` (kept source seconds), `report.json` (`source`, `fps`, integer `[start, end)` `frames`), a readable original file, and optionally `plan.json`. Relative source paths resolve against the edit folder. A plan must have the current cut duration. This adapter follows the original-source export contract in `plugins/ai-editor/skills/style-edit/scripts/export_nle.py` rather than importing a flattened render.

1. Open a dedicated Resolve project. Call `ai_editor.resolve_bridge.status()`; this reads connectivity and does not select a timeline.
2. When external scripting is unavailable, call `install_internal_bridge()`. It writes `cooked_resolve_bridge.py` in the current user's documented Resolve `Fusion/Scripts/Utility` directory. Run that script from Workspace > Scripts (Utility scripts can appear directly in that menu). Restart Resolve if it is not listed. The script must be started once per Resolve session. It imports this checkout, so keep the checkout in place. Alternatively start `start_embedded(resolve)` from Resolve's Python console after adding this checkout's `plugins/ai-editor/lib` directory to `sys.path`. These are local code execution steps; no scripting security preference is changed.
3. Call `create_timeline(Path(edit_folder), name=None)`. It imports the original and creates a new `cooked. <folder>` timeline. It never appends to an existing timeline. On completion it restores the previously selected timeline when one existed. Resolve's project manager saves the current project, including any other existing unsaved project changes; use a dedicated project for isolation.
4. Review the timeline in Resolve. The adapter supports source cuts and constant punch zooms through `ZoomX`/`ZoomY`. It splits clips at static punch boundaries. Animated/eased/push zooms are omitted with a warning. Original audio follows Resolve's normal append behavior; audio cleanup/fades from cooked's rendered cut are not reproduced.
5. If only managed zoom scale values changed in cooked, call `update_timeline(Path(edit_folder))`. It finds the timeline by unique ID without changing the current timeline. It checks all managed video/audio clip identities, source references/paths, trims, placement, duration, speed, enabled state, prior managed zoom values and timeline settings before writing anything. It sets only `ZoomX`/`ZoomY`; manual Pan, Tilt, grading and other properties are preserved.
6. Conflicts return `ok: false` and a reason. Recutting, replacing the original, changing the timebase, adding/removing zoom boundaries, or manually changing managed clips requires a separate edit folder and new timeline. The adapter does not rebuild over the existing timeline. Repeated Create is rejected while a manifest exists.

Deliverables: a dedicated native timeline and `resolve-manifest.json` in the edit folder. The manifest includes project/timeline IDs, source path/stat, rational frame rate, clip mapping, managed zoom values and verified API snapshot. It is local project data, not a repository fixture. No media or runtime secrets belong in Git.

Acceptance: exact source ranges and assembled frame counts, matching source/timeline frame rates, a saved ready manifest, managed zooms readable back through the API, preserved manual unmanaged properties, and conflicts detected before any write. Real acceptance also requires inspecting generated footage and audio in a dedicated Resolve project. Offline fakes alone do not establish native correctness or editorial quality.

Feedback: report the returned error code plus the manifest `state`, and the smallest synthetic reproduction. Keep the original timeline. An `incomplete` manifest means an operation might have partially applied; inspect it in Resolve before any retry. Do not delete a `.resolve-bridge.lock` until confirming no operation is running. No unknown editing request is automatically replayed through another transport.

## Interface and transport

Public functions return JSON-safe dictionaries:

- `status()` returns `{connected: bool, version: string|null, message: string}`.
- `create_timeline(edit_dir: Path, name: str|None = None)` and `update_timeline(edit_dir: Path)` return `{ok: true, timeline_id, timeline_name, manifest, clips, warnings, message}` or `{ok: false, code, message}`.
- `install_internal_bridge(runtime=None, scripts_dir=None)` returns `{ok, path, message}`. The optional arguments support isolated tests; normal callers use the default user directories.
- `start_embedded(resolve, runtime=None)` is called only inside Resolve; it returns connection status without a credential. `stop_embedded()` stops that interpreter's service.
- `ResolveBridge(resolve=fake)` injects a vendor-shaped object for tests. `ResolveBridge(command=[...], runtime=..., timeout=...)` allows an explicit installed runtime/test transport.

The app first looks for the internal service descriptor under `$AI_EDITOR_HOME` (default `~/.ai-video-editor`). The service binds only `127.0.0.1` on an ephemeral port. Its random bearer token is stored in `resolve-bridge.json` with mode `0600`; token values never appear in returned status or installer output. It accepts only POST `/resolve` with the three fixed adapter actions, exact loopback Host, JSON with bounded length and a valid token. Requests with Origin or browser fetch-site headers are rejected; it supplies no CORS access. It exposes no shell, code evaluation, upload, or generation endpoint. Requests are serialized. It remains active until Resolve exits or explicit stop.

Without an internal service, native calls run in Resolve 21.1+'s bundled `ResolvePython` subprocess to avoid loading vendor native libraries into the home server's Python ABI. A bounded stdout JSON marker carries results. The default macOS executable is the vendor-documented `Contents/Applications/ResolvePython` path. Other OS executable discovery is not implemented.

Source intervals remain exclusive-end internally. The append dictionary converts the end to `endFrame = exclusive_end - 1`; the returned API duration/start/left offset is checked before reporting success. NTSC rates such as 29.97 are retained as `30000/1001` in the manifest and set using Resolve's nominal rate string. Decisions are rounded using the report's actual FPS and checked against report integer frame ranges, avoiding stale-cut imports.

## Verification recorded 2026-10-23

- Wrote and ran tests before implementation: 11 initial failures due to the missing module. Implemented source-cut behavior; all 11 passed.
- Added relink/internal-transport/authorization/installer tests before the fallback: four failures, then all 15 passed after implementation.
- The tests use synthetic path/content and a fake vendor object. They cover frame end conversion, NTSC normalization, static zoom segmentation, source readability/stale-report rejection, manual zoom/trim/relink conflicts, preservation of manual Pan, structural update rejection, repeat-create prevention, missing project, unsupported animation warnings, subprocess errors, authenticated local transport, rejected browser/Host/token requests, and a credential-free installer.
- Final verification: all 15 adapter tests, Python compilation, and `python3 tests/check_plugins.py` passed.
- Real read-only external probes executed with the installed ResolvePython before and after launching Resolve 21.1.1 returned no Resolve connection.
- Opened Resolve through native UI and inspected System > General without saving changes. The UI showed Automatic scripted actions = Allow safe; no External scripting setting was present. The vendor README describes that setting under Studio. This observation does not prove internal scripting is unavailable.
- Created only a new empty project named `cooked Native Adapter Synthetic QA 2026-10-23`. No existing project or timeline was edited. Installed the local Utility import script at the documented user location and restarted Resolve. Workspace > Scripts still showed No Scripts. The initial Console used Lua; a Python prefix was rejected as Lua syntax and a Lua `fusion:RunScript(...)` attempt produced no service descriptor. Subsequent native Console selections did not expose a Python console through the automation interface. Internal native bootstrap remains the concrete unverified step.

## Remaining limits

No native timeline has been created by this adapter on the installed app yet. A user must start the reviewed Utility script/Python bootstrap successfully before native acceptance can run; the adapter does not require purchasing Studio as its assumed resolution. The service and source mapping have fake tests, not a proven native result.

Captions, graphics, music/sound cues, rendered audio cleanup, Fusion controls, animated zooms, speed ramps, multicam, multiple-original joined sources, variable-frame-rate conformance and native source-timecode edge cases are outside this slice. Manual keyframes on managed zoom properties cannot be exhaustively inspected through this static property API; do not update managed zooms after adding such animation. Native transform/keyframe behavior and original-audio assembly need real footage verification. Source identity uses path, size and modification time, not a full media hash. Unmanaged properties are left untouched, but this is not a guarantee against every possible Resolve editing operation. No quality or time-savings claims are made.
