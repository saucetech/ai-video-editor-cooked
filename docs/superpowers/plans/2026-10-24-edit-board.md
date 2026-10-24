# Edit Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review source-linked edit choices, render/approve a revision and create a native Resolve timeline.

**Architecture:** A stdlib board service stores versioned planning rows and immutable source-cut revisions. Authenticated home routes expose finite actions; vanilla UI uses the existing Resolve adapter and renderer. Every revised cut creates a separate timeline.

**Tech Stack:** Python 3.12, unittest, vanilla JavaScript/HTML/CSS, FFmpeg and existing Resolve Lua transport.

**Spec:** docs/superpowers/specs/2026-10-24-edit-board-design.md

## Global Constraints

- No new dependencies, uploads, paid generations or automatic agent dispatch.
- Canonical source-cut files and previous timelines remain untouched.
- Notes/emphasis are planning controls; preview is a source cut and native static zoom is separately labelled.
- The owner has no real footage; synthetic tests establish mechanics only.

## Review Focus

- Stale tabs/source mutation must fail before changes or native calls (Task 1).
- Restored gaps must map to exact source/record frames and protected holds cannot be silently dropped (Task 1).
- Approval must bind the rendered immutable revision, including text/notes/zoom, and cannot survive a draft change (Task 1).
- Interrupted rendering/native calls must never be silently replayed (Tasks 1–2).
- Media URLs must reject unrelated files, traversal and invalid Range requests (Task 2).

### Task 1: Board decisions and revision lifecycle

Files: create lib/ai_editor/edit_board.py and tests/test_edit_board.py.
Interfaces: load(edit), save(edit, expected_version, rows), preview(edit, expected_version), approve(edit, revision_id, expected_version), send_to_resolve(edit, revision_id, expected_version); return JSON-safe state. Media selection remains internal.

- [x] Write red tests for restored intervals, protected rows, concurrency and source fingerprint checks.
- [x] Implement validated frame rows and atomic versioned saves, retaining original cut files.
- [x] Write red tests for approved revision identity, stale/failed revisions and idempotent native send.
- [x] Implement background renderer, immutable revision artifacts and guarded native handoff.
- [x] Verify real synthetic render frames/audio and run the existing adapter tests.

### Task 2: Authenticated routes and usable board

Files: create edit_board_http.py, edit-board.html, edit-board.js, edit-board.css; modify home.py, home.html and integrations.js; add tests/test_edit_board_http.py.
Interfaces: finite /board actions using POST JSON; /edit-board assets; /board/media?edit=...&revision=... with Range support. Existing token and origin checks run first.

- [x] Write red HTTP tests for unauthorized POST, foreign origin, allowlisted edits and confined media ranges.
- [x] Implement routes, synthetic sample creation and streaming media; tests turn green.
- [x] Implement source/preview player, row controls, save, preview status, approval, explicit Resolve create, revision history and visible limitations.
- [x] Verify browser restore/change/save/preview/approve/send and stale draft behavior.

### Task 3: Native proof and full suite coverage

Files: docs/edit-board.md, docs/ai-edit-suite-coverage.md, README.md and this plan's verification record.

- [x] Run the actual sample through Resolve; read back source/record frames and matched audio.
- [x] Change an earlier native Pan value; build a later revised cut into a new timeline and verify the first remains unchanged.
- [x] Document repeatable use/recovery, remaining limits and the complete requested feature inventory.
- [x] Run unittest discovery, plugin validation, JS syntax checks and the repository demos; report named failures and rerun only justified checks.
- [x] Review the diff, commit the verified work to the owner's existing fork branch and update the project setup record.

## Execution and verification record

Base: `b7d6d2a`, existing owner branch `codex/connect-codex-and-integrations`. Ruling: reuse this checkout because it is the installed local app and no background edit job is active; an unrelated worktree would not exercise the owner's runtime. The owner requested implementation of the reviewed direction and has no footage available. Synthetic material is explicit throughout.

Builder check found no important unanswered question. Independent code review found three issues: invalid preview reuse, inconsistent nominal/average source rate and renderer descendants surviving timeout. Each received an observed failing regression and a passing fix; the reviewer rechecked all three. Live UI testing exposed lost edits after state replacement; the UI event-handler regression failed before row rebinding and passed afterward. The full demo run exposed the sample being counted as an unfinished edit; a library-status regression failed, then proper sample review metadata corrected it without fabricating jobs or approvals.

Final unit discovery: **84 tests passed**, plus `node tests/test_edit_board_ui.mjs`. Plugin checks, strict manifest validation and JavaScript syntax checks pass. Board tests include real FFmpeg frame/audio checks. CI now runs the adapter/board tests and UI lifecycle regression alongside the existing self-checks.

The complete offline demo command ran to completion and reported two failures: `review.py demo` (library Making count, caused by the new sample lacking review metadata) and `setup.py demo` (the existing warm-cache `step_warm() == "skipped"` assertion). After the sample fix, the complete review demo passes on rerun. The unchanged setup demo passes with isolated AI_EDITOR_HOME. All other demos passed. This is not a claim of one clean full-suite invocation.

Native proof on free Resolve 21.1.1.10: first revision `d456a9` created 180 frames with matching source audio. Set its first clip Pan to 37 through the native property API. Revision `996ac4` restored/protected the middle hold and created a different 240-frame timeline with video/audio durations `[60,60,120]`, source offsets `[0,60,120]`, and zooms `[1,1,1.2]`. Earlier timeline structure and Pan were unchanged. Browser reloading preserved saved notes, zoom and revision identity, and displayed no console errors. This proves preserving a prior timeline, not merging arbitrary finishing into another timeline. Paid generation, uploads and real-footage creative acceptance were not performed.

The maintained broader feature scope is `docs/ai-edit-suite-coverage.md`; only milestone 1 ships here. Notes/emphasis remain planning annotations. Future visual execution, all hook recipes, CapCut and faceless workflows are explicitly pending.
