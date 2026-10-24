# Review an edit and finish in Resolve

## When to use it

Use the Edit board to review an existing source cut, restore omitted intervals, protect a demonstration hold, retain visual direction and preview an explicitly approved revision in Resolve. Required inputs: a working local editor, FFmpeg, and either a source-cut project in its library or the built-in synthetic sample. Resolve must be open with a dedicated project and the local connection running.

Open **Edit board** in the home header, or **Open edit board** under Resolve & Higgsfield. No agent login is required for these board controls. Codex remains available for creating the original cut through the existing editing workflow.

## Try the sample

1. Choose **Try the synthetic sample**. It generates an original eight-second moving pattern with a tone. Its text is labelled synthetic; there is no spoken transcript or editorial-quality claim.
2. Inspect the original source using **Watch source**. Initially, the two-second middle passage is omitted.
3. Turn on **Protect hold** for passage 2. This restores it and disables removal until you unprotect it. Add a visual note or emphasis text if useful. Choose a static zoom for a kept passage.
4. **Save board**, then **Build cut preview**. Rendering runs separately so home polling remains responsive. Select and watch a completed preview.
5. **Approve this preview**. Changes require a saved new revision and a new approval.
6. In Resolve, open a dedicated project. Expand **Connect Resolve**, choose **Get connection command**, and paste the displayed command into **Workspace → Console**. Leave that session running. See [Resolve operating/recovery instructions](resolve-integration.md).
7. Choose **Create Resolve timeline**. The returned name identifies the board version and revision. Select it in Resolve to finish manually. Sending the same completed revision again returns its previous result.
8. Change the board, preview and approve again. The revised cut creates a separate timeline. Earlier timelines, including manual changes made there, remain available for comparison.

## Use a real recording later

Run the normal cut workflow from **New video** with your own recording. Once its `decisions.json` and `report.json` agree, it appears in the board's project selector. The board reads word timing where available and shows uncovered source intervals as restorable passages. This version retains original source order and the existing cut boundaries; arbitrary trimming, rearrangement and multiple sources are future work.

Visual notes and emphasis text are saved planning annotations. They do not generate or render graphics, captions or B-roll in this release. The browser preview contains source cuts and original audio. Static zoom is applied to the original source clips in Resolve; it is not baked into the browser preview. Native captions, graphics, B-roll layers, music and animated zooms require further implementation and separate verification. Track the complete requested scope in [AI Edit Suite feature coverage](ai-edit-suite-coverage.md).

## Revision and recovery behavior

Original source/cut/plan files are unchanged. The board saves `board.json`; previews live under `board-revisions/<revision>/` with conventional decisions, report and plan files, a cut preview, render log and native manifest. A source/input fingerprint ties the board to its original cut. If those inputs change, use a separate edit folder for the new cut; the board refuses to apply stale decisions.

Saves check the expected version. A stale tab must reload before overwriting newer choices. **Reload** intentionally discards unsaved browser changes. A selected project is retained in the page URL in the current UI.

If a preview fails, inspect that revision's render log. A damaged completed preview is retained as failed and **Build cut preview** creates a different revision. A timed-out render terminates its renderer process group, including FFmpeg descendants, on POSIX. Windows uses process-tree termination but has not been exercised locally. Reconnecting the browser does not automatically rerun a failed render or native action.

If Resolve creation returns an uncertain/incomplete result, inspect its `resolve-manifest.json` and native timeline before further action. The board blocks replay of that revision. After resolving the cause, explicitly create and review a separate preview/revision; do not delete a manifest to force retry. A stale `.edit-board.lock` means an action was interrupted: confirm that no process/native action remains before recovery. No automatic stale-lock deletion is attempted.

## Acceptance and feedback

The repeatable acceptance path is source → board correction → preview playback → explicit approval → native source/frame readback → one ordinary correction and preserved earlier finishing. For real recordings, also apply the founder's existing common-footage test: meaning, cut edges, demonstration legibility, caption accuracy, audio, operator effort, waiting, retries and all material costs.

Verified locally October 24, 2026 on free Resolve 21.1.1.10: sample v1 produced 180 frames (six seconds) with two video/audio source intervals. A Pan value of 37 was then set on its first clip through the native property API. Sample v2 restored the middle hold and produced 240 frames with three matching video/audio intervals, durations `[60,60,120]`, source offsets `[0,60,120]`, and zooms `[1,1,1.2]`. A different timeline was created and the earlier timeline's structure and Pan remained unchanged. This verifies preserving the earlier version, not merging arbitrary manual edits into a new version. No actual recording or creative-quality comparison was available.

Feedback should identify the board version/revision, the smallest affected passage and the expected result. Keep credentials and personal footage outside Git. Use the native-manifest and test evidence when diagnosing a failure rather than replaying uncertain actions.
