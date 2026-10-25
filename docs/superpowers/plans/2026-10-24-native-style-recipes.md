# Native style recipes implementation plan

> Execute inline using superpowers:executing-plans. Existing authorized feature branch: codex/connect-codex-and-integrations.

**Goal:** Transfer analyzed caption choices and original hook graphics into editable native Resolve graphs with visible transfer evidence.
**Architecture:** bounded normalized style snapshot per row, immutable word snapshots per revision; canonical pixel-space scene drives preview and Fusion; guarded native comparison exports actual frames and verifies controls.
**Tech Stack:** Python/Pillow/FFmpeg, vanilla JS, Resolve Lua mailbox.
**Spec:** docs/superpowers/specs/2026-10-24-native-style-recipes-design.md

## Global Constraints

Keep historical visual bundles and approvals valid. No paid services or external media. No mutation of saved analyses, transcript or source intervals. Maintain original text in visible editable nodes, blank native carriers. Captions opt in. Missing timing means explicit passage fallback. Source size_pct is long-side units. Only supported normalized values cross into recipes; inferred font and unavailable effects reported. Native proof requires matching project and timeline IDs. Preserve native UI state; quarantine uncertain calls. Original synthetic fixtures and private owner evidence stay separate.

## Review Focus

Inspect hostile style data, stale revisions, path/symlink escapes, native changes after proof, invalid/missing/aligned word timings, removed intervals, very short motion holds, portrait geometry, incorrect font metrics, frame-time offsets, restoration after native errors, and historical bundle compatibility. Check actual visible text nodes rather than merely successful API returns.

### Task 1: Normalize analyzed style choices and immutable timing inputs

**Files:** board_styles.py (new), board_visuals.py fields/validation, edit_board.py snapshots, tests/test_board_styles.py (new), tests/test_edit_board.py.
**Interfaces:** produces normalized per-row caption_style object {treatment,font,weight,size_pct,y_pct,words_per_phrase,color,accent,case,box,shadow,stroke,entrance_s,source,transfer}; caption_treatment and motion_result fields; revision words.json optional artifact. Consumers tasks 2/3.
1. RED tests for inferred serif substitution/conflicting absent captions, finite numeric bounds/path scoping, correct timestamp alignment with corrected text fallback, and missing optional snapshot compatibility. Expected failure: missing adapter behavior.
2. Implement catalog under library creator-teardowns; snapshot hashes and field-by-field provenance, report unapplied effects; strict normalized validation. Copy word snapshot before render and bind only existing optional file in artifacts. Keep analysis untouched.
3. Run python unittest discovery for new style/board tests. Expected all pass. Commit task.

### Task 2: Shared scenes and editable caption/hook recipes

**Files:** visual_recipes.py (new), board_visuals.py compile extension, resolve_visuals.py readback, tests/test_visual_recipes.py (new), tests/test_resolve_visuals.py.
**Interfaces:** consumes normalized rows/words; produces scene nodes with text/font/size/position/colors and sampled scalar curves, comp graph + text/control expectations and transfer notes in existing schema1 layer metadata. Task3 consumes metadata for proof.
1. RED tests phrase paging at real word timestamps, correction fallback, two-line bounds, portrait scene layout, hook duration rejection and native/preview sample equivalence. Expected missing recipe behavior.
2. Build Arial clean/Georgia editorial/spotlight; hero reveal/outline draw/prompt_result. Use identical integer-frame samples in PNG preview frames and Fusion scalar curves. Legacy panels remain old path. Blank alpha carrier native, exact frame count. Read back all declared text/font/size/color/curve samples.
3. Run recipe/visual/Resolve tests. Expected all pass. Commit task.

### Task 3: Board controls and verified native comparison

**Files:** edit_board.py, edit_board_http.py, edit-board.{html,js,css}, resolve_proof.py (new), resolve_lua.py, resolve_helper.lua, tests/test_resolve_proof.py (new), tests/test_edit_board_http.py, tests/test_edit_board_ui.mjs.
**Interfaces:** consumes catalog, normalized rows, native manifest, hashed bundle. POST style apply saves with version guard. POST compare exports fresh proof to bounded revision proof subdirectory. GET proof images validates hashes and membership. Produces timestamped comparison report tied to revision/bundle/project/timeline and current native controls.
1. RED tests export path rejection, wrong project/revision, restoration, native text divergence, tampered proof files; UI style/caption/hook persistence. Expected missing compare/control behavior.
2. Add finite endpoints and native still export allowlist with scoped export capability path validation; compare selected start/entrance/hold/exit samples against actual decoded preview frames. No automatic fidelity score. Fresh compare checks native edits; label proof historical capture timestamp. UI shows settings and approximations beside paired frames.
3. Run complete Python suite, UI test, plugin and strict validation. Expected all pass. Commit task.

### Task 4: Native quality verification, documented procedure and final review

**Files:** existing board/Resolve documentation and inventory, reusable synthetic QA script, owner evidence outside repo.
**Interfaces:** consumes all preceding tasks; produces real landscape/portrait captures, native control checks, preserved old revision and quality limits.
1. Create neutral original synthetic demonstration with authored word timings; choose actual serif analysis privately. Build/approve/import; native export real sample frames; inspect playback and compare. Fix observed discrepancies with regression test first. Expected usable readable text/hook holds, matching timing/geometry and editable nodes.
2. Exercise correction/new timeline and preserve previous manual finish. Run full tests and relevant offline demos. Expected all pass. Update maintained procedure and feature inventory with actual limits. Commit task.
3. Fresh most-capable final reviewer checks whole task diff against spec/plan/evidence. Important fixes RED→GREEN, green full suite; record rulings/minors. Push authorized feature branch, leave board and QA ready.
