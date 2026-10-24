# Local integrations implementation plan

Goal: connect the existing browser workflow to Codex/ChatGPT, then add tested local Resolve and Higgsfield entry points.
Spec: `docs/superpowers/specs/2026-10-23-local-integrations-design.md`.
Stack: existing Python standard-library HTTP server, vanilla browser JavaScript, Codex JSON-RPC stdio, vendor Resolve scripting, installed Higgsfield CLI. No new package dependency.

## Constraints and review focus

Keep the local token/origin checks, ChatGPT authentication, library/runtime write boundaries and explicit approvals. Do not change global Codex authentication/configuration. Test duplicate Connect, process death during work, stale approval responses, cancelled jobs and malformed/unknown protocol messages. Preserve existing Claude workflows. Never modify an existing Resolve timeline as a connection test. Generation must not happen while checking Higgsfield access.

## 1. Codex protocol bridge

Files: create `plugins/ai-editor/lib/ai_editor/codex_bridge.py` and `tests/test_codex_bridge.py`.
Interfaces: `Bridge.connect()`, `snapshot()`, `submit(text, job=None)`, `respond(id, body)`, `cancel()`, `close()`; callbacks receive progress, final result and terminal status. Queue ownership stays in `home.py`.

- [x] Write failing subprocess-level tests for initialization/account auth, streamed output, questions/approvals, duplicate connect, cancellation and crash recovery.
- [x] Implement request/response correlation, reader-thread events and bounded UI state. Pass schema-compatible tool results; reject stale responses and unsupported server requests.
- [x] Verify against the installed CLI's generated protocol schema and actual `account/read`.

## 2. Browser and queue wiring

Files: modify `home.py`, `home.html`, `askhook.py`, `launcher.py`; add focused home integration tests.

- [x] Write failing tests for atomic dispatch, no Claude spawning in Codex mode, cancellation and authenticated endpoints.
- [x] Add Connect, status, direct message, answer and disconnect routes. Dispatch queued editor jobs using existing `job_line`; report results without mislabeling a stopped or failed job as complete.
- [x] Add the compact Codex connection panel and preserve input while polling. Keep Claude an explicit alternative. Reuse existing state/security mechanisms.
- [x] Verify browser connection, live streamed response and a small synthetic editing task. Update README and operating notes; package the tested Codex slice with the integrations.

## 3. Resolve adapter

Files: create `plugins/ai-editor/lib/ai_editor/resolve_bridge.py`, tests and integration UI/routes.

- [x] Test source frame placement, connection failure and preservation/conflict behavior with a simulated vendor API.
- [x] Implement read-only diagnostics and creation of a dedicated managed timeline from cooked source cuts. Persist mapping in the edit folder; follow-up changes must detect manual modifications.
- [x] Test a dedicated synthetic timeline through the real installed API when a connection is available. Report a concrete external scripting/login limitation if it is not.

## 4. Higgsfield adapter

Files: create `plugins/ai-editor/lib/ai_editor/higgsfield_bridge.py`, tests and integration UI/routes.

- [x] Test auth errors, result normalization, pending/failed handling, unsafe download rejection and provenance.
- [x] Add account check, recent results and explicit completed-media import. Separate model discovery, quote and generation; require explicit quote confirmation for paid requests.
- [x] Verify real account/list access and local import fixture without generation charges.

## 5. Final verification

- [x] Run new tests, `tests/check_plugins.py`, strict plugin validation and affected demos.
- [x] Run `PY=<editor venv>/bin/python bash tests/demos.sh`; report all remaining failures by name.
- [x] Browser test the final app, record evidence/limits, commit changes and update the owner's existing setup record.


## Verification and limits (2026-10-23)

53 adapter tests passed, including the three fixes from independent review: review-page Stop cancels active/pending requests for the edit, unknown turn-start outcomes terminate the child before reuse, and Use Claude keeps its explicit provider label. Plugin checks, strict plugin validation and JavaScript syntax checks passed. The real browser connected with existing ChatGPT authentication and made a synthetic 2-second 540x960 video with audio, verified using ffprobe.

The full offline demo suite was run to completion and initially reported review.py and setup.py. The review failure exposed unnecessary state creation during provider detection; this was changed to a read-only lookup, and the updated provider-label regression was added to its own Node check. The complete review demo then passed. The unchanged setup demo's warm-up assertion saw the actual installed renderer's warm cache; it passed with an isolated AI_EDITOR_HOME. Every other demo passed in the full run. Logs are retained in the owner's setup verification folder, outside this repository. The full suite has not been represented as a clean single invocation.

Higgsfield real authentication/list/model access and a text-only unsent credit quote succeeded; completed-media import is tested with a synthetic fixture. No paid generation, source upload or account asset import was used as a test. Resolve's 15 tests cover synthetic vendor behavior and authenticated local transport. The real app still cannot bootstrap the installed internal Utility script: no native timeline has been created. Native footage/audio/manual-edit acceptance remains outstanding. Implementation does not establish editorial quality or time savings.

Live browser acceptance also passed for editor_question: the model asked for a synthetic caption size and received “Large”. The normal review Submit feedback action dispatched a Codex continuation, acknowledged the synthetic note and produced draft 2 with “Codex review continuation verified”; both draft media files have identical SHA-256 values, as requested. The browser displayed completed Higgsfield results and correctly reported Resolve disconnected. UI contrast was inspected and corrected to use the existing theme panel colours.
