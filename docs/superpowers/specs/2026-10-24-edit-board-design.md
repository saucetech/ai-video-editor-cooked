# Reviewable edit board and Resolve workflow

The owner approved the edit-board direction from the October 24 AI Edit Suite review and requested implementation, Resolve handoff and eventual coverage of all showcased workflows. They currently have no footage to test. Deliver a working, clearly labelled synthetic sample and a path for future source-cut projects. This is the implementation of the first slice, not a claim that the full suite exists.

## User experience

Open Edit board from the home header or Resolve panel. Choose a source-cut edit, or create the synthetic sample. The board shows original-source playback, source intervals (including removed gaps), text, keep/restore controls, a protected demonstration hold, editable visual notes, emphasis text and static zoom. Show selected duration and numbered proposed cut order. Notes are planning annotations in this slice, not rendered caption/graphics promises. Preview and Resolve explicitly describe what is actually included: source cuts, matching source audio and static zoom in Resolve. Synthetic transcript labels must never be represented as transcribed speech.

Save uses optimistic concurrency and original-file fingerprints. Editing a saved board invalidates its current approval and preview selection. Preview creates an immutable revision with conventional decisions/report/plan files and a source-cut MP4 through the existing cut renderer. Approval is a separate explicit action after preview. Send to Resolve operates only on an approved completed revision; no arbitrary browser file paths are accepted. Each revision creates its own dedicated native timeline through the current adapter. Repeating Send for the same revision returns the prior verified manifest. An incomplete manifest blocks automatic replay. New cuts create new timelines, preserving every earlier manual adjustment. Structural conflict updates remain blocked by the existing adapter.

The board is served on the authenticated home origin. Reuse home token/cookie, POST origin validation, finite routes and library edit allowlist. Provide streaming Range media for only the chosen source or a known completed board revision. No arbitrary local-file server, remote uploads, external generation or new dependencies. No automatic Codex dispatch or paid action.

## Data and execution

Keep originals and existing decisions/report/plan unchanged. Store board.json with schema, version, input fingerprint, immutable row IDs, frame intervals, keep/protected flags, notes/emphasis and zoom. Initialize from current kept frame ranges plus uncovered source gaps. Prefer word-timing transcript text when present. Source FPS and frame count come from ffprobe, not an untrusted browser payload. Fail mismatched cut/source rates and bounds; cap input/row text and reject overlaps or duplicated IDs.

Snapshots live under edit/board-revisions/<UUID>/ with revision metadata, copied approved row values, decisions.json, report.json, plan.json, render log and cut.mp4. Each revision pins input identity. Source order is retained; arbitrary reorder/multisource is future work. Static zoom applies per kept interval and is frame aligned. Preview shows the spoken/source cut; zoom is explicitly a native Resolve treatment, not baked into this preview. Visual notes and emphasis are retained in revision metadata.

Render in a background process with bounded execution and fixed renderer arguments; track status, PID and error, prevent duplicate jobs and do not make a long render block home polling. Never retry an uncertain native creation automatically. Saves and approval transitions serialize per edit with locks. Multiple processes/tabs cannot approve or send a stale version. Revision failures remain visible. Reject sources that changed since preparation.

## Acceptance

- Test restore/drop/protection and exact source-to-record mapping, persistence, concurrent edits and approval invalidation.
- Test malformed inputs, changed sources, invalid revisions, unauthorized/origin requests and media path confinement/Range responses.
- Test actual FFmpeg preview frame count/audio and unchanged canonical input files.
- Test unapproved/stale/failed revisions never reach Resolve, repeated send returns one verified timeline and incomplete outcomes are not replayed.
- Exercise sample in browser, save correction, preview, approve and create separate native Resolve timelines. Verify timing and unchanged earlier manual property.
- Record the absence of real-footage creative validation and all pending suite capabilities honestly.

## Broader suite scope

Maintain one feature coverage table: first cuts/retakes, semantic B-roll and demonstration holds, creator/reference recipes, blended/hero captions, original line-art/3D treatments, seven opening-hook treatments, faceless presenters/scripts/looks/voice/render, reusable brand settings, editable NLE finishing and review. Reuse current fork capabilities where they exist. Explicitly distinguish existing implementation, this board's planning controls, native validation and future work. No proprietary templates/assets are copied. Avatar/generation work requires separate provider/quality acceptance and does not block this board.

Builder calls: Python stdlib plus existing FFmpeg renderer; vanilla HTML/CSS/JS following home colors; immutable native timelines instead of overwriting finished edits. First version is source-order single-source to match the verified adapter. These are implementation choices, not new owner requirements.
