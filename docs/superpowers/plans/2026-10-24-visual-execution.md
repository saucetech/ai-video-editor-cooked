# Editable visual execution implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task in the current feature checkout. Preserve the existing working app and source library.

**Goal:** Actual captions, animated text graphics and B-roll in approved previews and separate editable Resolve tracks.

**Architecture:** Extend board rows with explicit visual fields, compile kept passage ranges into an immutable visual bundle, render locally and import generated Fusion Text+ compositions on exact-duration carriers. Keep original media/audio, native B-roll and each revision separate.

**Tech Stack:** Existing Python/vanilla UI, FFmpeg, installed Pillow, Resolve Lua allowlist. No paid calls or new packages.

**Spec:** docs/superpowers/specs/2026-10-24-visual-execution-design.md

## Global constraints

- Integer frame positions and exclusive ends; remove visuals with their omitted passage.
- Explicit caption/motion fields; generic notes never silently become graphics.
- Default off for migrated boards, optimistic version guard and new preview approval for visual changes.
- Native B-roll excludes audio; editable Text+ captions are not a native Subtitle track.
- Copied media/compositions and carrier integrity bound to the approved revision.
- Original paths, earlier timelines and historical revisions remain usable.

## Review focus

- Assets changed between selection/render/approval/send: fail safely before native creation.
- Short B-roll, non-finite offsets, mixed FPS, symlink/path escapes: reject or conform explicitly.
- Multiple simultaneous visual layers: exact tracks/frames; captions stay above B-roll/graphics.
- Old source-only boards: no automatic captions or new hash requirements on historical ready revisions.
- Interrupted Resolve import or wrong Fusion text: incomplete result blocks blind replay.

### Task 1: Visual decisions and immutable compilation

Files: create board_visuals.py; modify edit_board.py, edit_board_http.py; tests/test_board_visuals.py and test_edit_board.py.

Interfaces: row_defaults(row), validate_row(row, roots), compile_bundle(revision_dir, rows, report), verify_bundle(revision_dir), render_preview(revision_dir). Rows add caption_enabled/caption/motion/motion_text/broll/broll_start. Asset roots are the configured library and existing upload staging folder.

- [ ] Write failing tests for removed-interval mapping, legacy defaults, native composition text escaping, bad offsets/paths/short media, immutable asset tampering, approval invalidation.
- [ ] Run focused tests and observe failures.
- [ ] Implement validation, copied/conformed assets, exact frame cues, SRT, generated Text+ compositions and integrity manifest.
- [ ] Render captions/motion/zoom/B-roll to preview with original source audio; verify output duration/audio and visible changed frames.
- [ ] Run tests and commit.

### Task 2: Native editable layers

Files: create resolve_visuals.py; modify resolve_bridge.py, resolve_lua.py, resolve_helper.lua; tests/test_resolve_visuals.py and existing adapter tests.

Interfaces: load_bundle(edit, total_frames, rate), append_layers(pool, timeline, bundle, start_frame) -> native readback records. Add only fixed track/Fusion methods; generated comp import returns FusionComp, FindTool returns FusionTool, GetInput/limited StyledText SetInput support verification.

- [ ] Write failing tests for V2/V3/V4 placement, video-only imports, wrong text/boundaries, missing bundle assets, update rejection for layered revisions and strict Fusion method allowlist.
- [ ] Extend helper types/methods, restart via acknowledged Stop/setup in the existing dedicated QA project.
- [ ] Verify an actual generated Fusion caption, motion keyframe and editable text change in a separate synthetic probe timeline.
- [ ] Append compiled layers, verify frame/text/keyframe readback, hash/manifest guards and original timeline preservation.
- [ ] Run all adapter tests and commit.

### Task 3: Board controls, correction and delivery proof

Files: edit-board.html/js/css; docs/edit-board.md, docs/resolve-integration.md, docs/ai-edit-suite-coverage.md; tests/test_edit_board_ui.mjs.

- [ ] Add explicit caption correction/enable, title/lower-third text, local B-roll upload/select and in-point controls within the approved UI.
- [ ] Exercise real handlers across save/approval replacements; restore existing keep/protect/zoom behavior.
- [ ] Build original synthetic visual media; preview/approve/import with one normal correction and preserved earlier finishing.
- [ ] Inspect preview stills and native Resolve viewer plus actual API timing/text/layer readback; record constraints honestly.
- [ ] Run full Python tests, UI test, plugin validation and relevant demos. Independent whole-change review; fix material defects and record evidence.
- [ ] Update maintained feature inventory and process, commit/push the existing feature branch.

## Execution ledger

- Owner explicitly chose editable text/motion plus native B-roll. Current request executes the existing milestone 2; no new feature-priority approval needed.
- Builder check resolved one ambiguity: preserve manual work in earlier timeline, do not promise cross-revision reconciliation.
- Native execution in the existing feature checkout maintains the running app's known install path.
