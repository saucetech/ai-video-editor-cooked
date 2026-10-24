# Editable visual execution from the GenMedia edit board

## Intent and authority

The owner requested actual captions, motion graphics, and B-roll in previews and Resolve, continuing the maintained AI Edit Suite inventory's visual-execution milestone. They explicitly selected editable caption text and motion controls with native B-roll clips over flattened matching overlays. Preserve the approved Apple-inspired dark glass interface and existing immutable preview/approval workflow.

## Deliverable

Each kept passage can enable and correct a caption, choose an original title/lower-third treatment with editable text, and select a local B-roll video with a source in-point. Caption words begin from available source transcript text; users can proofread them. This first slice uses passage-level caption timing, visibly labelled as such, not fabricated per-word timing. Use existing source boundaries and kept-order mapping; removed passages produce no visuals. Notes remain planning-only unless converted into explicit caption or motion text.

The browser preview renders captions, animated titles/lower-thirds, static source zoom, and selected B-roll over the retained original audio. Its immutable revision includes the exact visual decisions and copied B-roll assets plus hashes. Every meaningful visual change invalidates approval. Earlier revisions and native timelines remain unchanged.

Resolve gets original source V1/A1, video-only B-roll V2, motion graphics V3 and caption Text+ compositions V4. Captions/motion are separate editable Fusion Text+ compositions, backed by per-cue carrier clips only to provide exact timing. They are not baked into the underlying source. Timing/keyframes, text and layout are retained in generated composition files. Native B-roll audio is excluded. Export caption SRT as an additional delivery artifact, without representing Text+ as a native Subtitle track.

## Mechanism and constraints

Builder choices: validate and compile in a focused board_visuals.py module; use existing FFmpeg and installed Pillow for deterministic local previews and timing carriers, generated original Fusion compositions for native text/animation. Bound browser preview size to 1280 pixels while retaining source resolution for native timelines and transparent carriers. No new paid services or runtime installs. Reuse existing authenticated upload staging for selected local media; expose only staged or library-owned B-roll choices. No external stock retrieval, generation, source upload or credit spend.

Migrate old row data through defaults without silently enabling captions or changing historical previews. Save schema additions under the existing optimistic version check. Reject oversized text, non-finite values, traversal/symlink escapes, unsupported or too-short B-roll, overlaps that would overrun source duration, incompatible rates without explicit conformance, and assets modified after approval. Conform copied B-roll to the timeline rate when necessary so native and preview placements use the same prepared media. All durations use integer frames, exclusive ends.

Resolve API evidence comes from the installed 21.1 developer stubs. Extend the existing private same-user allowlist only for track naming/creation and fixed generated Fusion import/readback. Native probe must verify import, text readback and a keyframe change before UI handoff claims success. Unknown outcomes retain an incomplete manifest and block retries. Zoom-only updates of visually layered revisions must reject rather than touching caption/B-roll clips accidentally. Original source-only revisions remain supported.

## Acceptance

1. An old board loads with unchanged decisions and approval; explicit visual changes increment its version and require new preview approval.
2. Removing/restoring a passage correctly removes/restores its caption, motion, B-roll and output offsets; original audio remains.
3. Preview has visible caption text, motion state changes, chosen B-roll, source zoom, correct duration and audio. No captions are described as speech recognition on synthetic test-pattern data.
4. Native readback verifies all V1/A1/V2/V3/V4 clip frames/source offsets, editable caption and motion text, motion keyframe values and B-roll video-only behavior. Verify actual Resolve viewer pixels, not only successful API returns.
5. Revise one caption and B-roll choice, preview/approve/create a new timeline, and verify manual finishing remains unchanged in the earlier timeline. It is not merged into the new timeline.
6. Regression tests cover stale saves, corrupted previews/assets, missing/short/incompatible media, path escapes and uncertain native outcomes. Existing test suite and relevant demos remain green.

## Boundaries and feedback

This is the first working editable visual slice, not all AI Edit Suite features at once. Semantic B-roll search, advanced caption recipes, seven hook families, avatars, native Subtitle tracks, native kinetic-word typography, and arbitrary source trimming/reordering remain separate inventory rows. Test with original synthetic media until footage exists; no creative-quality or time-savings claim follows from it. Record capability limits, evidence and ordinary correction results in the existing guides and inventory.
