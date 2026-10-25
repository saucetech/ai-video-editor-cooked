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

## Add captions, motion and B-roll

1. Open a kept passage's **Captions & visuals**. Proofread **Caption text**, then enable **Show caption**. The original panel uses passage timing. Clean, Editorial serif and Word spotlight use verified source word timestamps for phrase pages when corrected text still aligns. Otherwise they explicitly fall back to static passage timing. Manual line breaks take precedence over automatic phrase grouping. This is editable Text+, not a Subtitle-track karaoke effect.
2. Choose **Fade title** or **Fade lower third** and enter its text. These retain their original fade controls. Hero reveal, Outline draw and Prompt → result add original native recipes with editable text, sampled easing, accent shapes and a separately editable result. Long copy requires a sufficient readable hold; shorten it or keep a longer passage if the preview rejects it.
3. Choose **Add B-roll** to copy a local video into durable library storage. Saved selections survive temporary-upload cleanup. Select it on a passage and set its in-point in seconds. The clip must cover the full passage from that point. B-roll replaces the picture while retaining source audio; its own audio is excluded.
4. Save, build and watch the preview. It includes enabled captions, motion, B-roll and static zooms. **Download captions · SRT** exports the corrected passage timing.
5. Approve and create the Resolve timeline. V1/A1 retain original source clips/audio, V2 contains ordinary prepared B-roll clips, V3 contains editable motion Text+ compositions, and V4 contains editable caption Text+ compositions.
6. In Resolve, select a text clip and open Fusion. Legacy panels use **GenMediaText**, **GenMediaOutput** and **GenMediaOpacity**. New recipes use visible **GenMedia1**, **GenMedia2** and subsequent text/shape nodes with named Size/Alpha splines. Each visible word in a spotlight caption is editable; rebuild from the board to reflow wording changes across those word nodes. The blank timing carrier contains no baked text. Captions are Text+ clips, not a native Subtitle track.

Browser previews are bounded to 1280 pixels. Native timelines/carriers preserve source resolution and display orientation, including 90-degree phone rotation metadata; B-roll is conformed to the source canvas and timeline FPS and can be relinked to its recorded original. Preview rasterization and Fusion are separate renderers, so font and fade appearance may differ slightly. Use Compare Resolve to inspect actual paired frames. A successful import or matching controls alone does not certify the visual result.

Visual direction and emphasis remain planning notes. Music, animated source zooms, semantic B-roll recommendations and the remaining hook families remain in the [maintained feature inventory](ai-edit-suite-coverage.md). Earlier source-only boards keep their old approval and default all new visuals off. Enabling or changing visuals requires a new preview approval.

## Revision and recovery behavior

Original source/cut/plan files are unchanged. The board saves `board.json`; previews live under `board-revisions/<revision>/` with conventional decisions, report and plan files, a cut preview, render log and native manifest. Visual revisions additionally contain captions.srt, visuals.json and hashed prepared media, transparent carriers and generated compositions. Changed visual assets block approval and native creation. Each revision snapshots its selected B-roll sources before conversion and verifies prepared frame counts. Full selected source copies are retained for reproducibility; large B-roll files increase local storage and preparation work. A source/input fingerprint ties the board to its original cut. If those inputs change, use a separate edit folder for the new cut; the board refuses to apply stale decisions.

Saves check the expected version. A stale tab must reload before overwriting newer choices. **Reload** intentionally discards unsaved browser changes. A selected project is retained in the page URL in the current UI.

If a preview fails, inspect that revision's render log. A damaged completed preview is retained as failed and **Build cut preview** creates a different revision. A timed-out render terminates its renderer process group, including FFmpeg descendants, on POSIX. Windows uses process-tree termination but has not been exercised locally. Reconnecting the browser does not automatically rerun a failed render or native action.

If Resolve creation returns an uncertain/incomplete result, inspect its `resolve-manifest.json` and native timeline before further action. The board blocks replay of that revision. After resolving the cause, explicitly create and review a separate preview/revision; do not delete a manifest to force retry. A stale `.edit-board.lock` means an action was interrupted: confirm that no process/native action remains before recovery. No automatic stale-lock deletion is attempted.

## Acceptance and feedback

The repeatable acceptance path is source → board correction → preview playback → explicit approval → native source/frame readback → one ordinary correction and preserved earlier finishing. For real recordings, also apply the founder's existing common-footage test: meaning, cut edges, demonstration legibility, caption accuracy, audio, operator effort, waiting, retries and all material costs.

Verified locally October 24, 2026 on free Resolve 21.1.1.10: sample v1 produced 180 frames (six seconds) with two video/audio source intervals. A Pan value of 37 was then set on its first clip through the native property API. Sample v2 restored the middle hold and produced 240 frames with three matching video/audio intervals, durations `[60,60,120]`, source offsets `[0,60,120]`, and zooms `[1,1,1.2]`. A different timeline was created and the earlier timeline's structure and Pan remained unchanged. This verifies preserving the earlier version, not merging arbitrary manual edits into a new version. No actual recording or creative-quality comparison was available.

Feedback should identify the board version/revision, the smallest affected passage and the expected result. Keep credentials and personal footage outside Git. Use the native-manifest and test evidence when diagnosing a failure rather than replaying uncertain actions.

Visual follow-up acceptance: the eight-second synthetic visual sample rendered three captions, a title, a lower third and two seconds of B-roll. Board 6 corrected the first caption and replaced the B-roll/in-point, then created a new native timeline with six verified visual clips. The earlier timeline retained its manual Text+ edit. Resolve 21.1.1.10 requires a matching-format timeline template after Fusion graphics exist; a new format must use a fresh dedicated project. See [Resolve integration](resolve-integration.md) for the measured stall, workaround and recovery procedure. Production-footage readability, speech accuracy and creative quality still require real recordings.

Reliability acceptance also covers a 360x640 portrait source stored as a rotated 640x360 video, manual caption line breaks and a four-frame graphic. Preview fade alpha now reaches zero on its last frame, matching the native fade endpoint. Text+ size is calibrated from preview pixel size and canvas aspect ratio; read back the native text and inspect its margins when adding another font or caption recipe. Existing approved bundles remain immutable; build and approve a new revision to use these layout fixes.

The portrait follow-up included a saved correction and separate revised timeline; native readback confirmed the prior manual Text+ change was retained. These checks use the same workflow above, with original synthetic test media.

## Apply an analyzed style and inspect its native transfer

Trigger: a saved creator analysis should guide editable captions or opening graphics. Inputs: the saved `creator-teardowns/<id>/style.json`, a board source cut and optional `words.raw.json`. Original analyses remain untouched.

1. Expand **Use an analyzed style**, choose a reference and apply it to kept passages. Captions remain opt-in and corrected text/ranges stay unchanged. Review **Style transfer details** before saving. Settings distinguish measured candidates, visual inference and defaults; the measured source hash is saved with the row snapshot.
2. Choose a caption treatment, phrase length, text size, vertical position and colors. **Contrast panel** provides light/dark support appropriate to the text color. Source shadow/stroke use this panel approximation, not the original shading. Font portability currently uses installed Arial and Georgia. A source such as Playfair Display is explicitly a substitution. Automatic face/product avoidance is not implemented.
3. Save, build, watch and approve. Revisions snapshot word data and generated scenes, curves and verified assets. Word spotlight uses original source timestamps mapped through omitted intervals. A changed word, missing timing, invalid timing or multiword timestamp record produces a visible passage-fallback note, never fabricated speech synchronization. Dense captions must be shortened/split. Advanced passages are bounded to 60 seconds and 80 editable nodes.
4. Create the separate native timeline, then choose **Compare Resolve**. Keep the owning Resolve project open. The app verifies the project/timeline identity and declared current controls, exports actual native frames and decodes corresponding preview frames. Sample points include starts, entrances, holds, exits and declared word/result reveals, capped at 24 frames. Inspect paired images and playback; this is not a pixel-equivalence score.
5. Changes to checked text, declared controls and clip structure appear as divergence. Additional native effects or nodes outside that declared set require visual inspection of the pairs. The comparison does not overwrite native finishing. Captures display their timestamp and become historical as soon as you continue native finishing; run Compare Resolve again for a fresh check. Current approved revisions only can request new comparisons. Historical saved captures remain viewable. Native UI timeline/page/playhead are restored; uncertain calls retain the existing explicit-recovery behavior. Drop-frame timecode comparisons are currently rejected rather than seeking inaccurate frames.

Verification uses actual exported Resolve stills plus editable control readback. A synthetic portrait calibration exposed a 6.36% narrower Georgia caption before correction; the revised sample's held caption width differed from the preview by 0.91%. This is a measured property of those frames, not a general font-fidelity or editing-quality claim. Free Resolve 21.1.1.10 was used. New fonts, machines and color-management choices require fresh comparisons.

Repeatable local macOS QA (uses existing installed tools and Chrome for H.264 playback; never installs packages or overwrites an existing edit):

```sh
# Supply your configured library and a NEW synthetic edit name. --style is optional.
~/.ai-video-editor/venv/bin/python tests/make_native_style_demo.py LIBRARY NEW_NAME --portrait --style SAVED_ID
# In the board, watch, approve, import and compare in a compatible dedicated QA project.
node tests/browser_edit_board.mjs EDIT_FOLDER EVIDENCE_FOLDER --compare
~/.ai-video-editor/venv/bin/python tests/check_native_style_frames.py PROOF_REPORT_JSON
```

Acceptance: readable held frames and full playback in portrait and landscape; verified visible native text/font/color/curves; matching source audio/ranges; a new corrected timeline retains earlier manual finishing. The geometry helper targets the neutral synthetic demo's first-caption region only; it is not a general quality evaluator. No actual spoken footage is available yet. Feed back the source style hash, revision, passage, sample frame and expected control/appearance; use the existing common-footage procedure when real recordings arrive.

Landscape acceptance also created a separate 1280x720/30fps native timeline, checked 23 actual sampled frames including late result/word reveals, and verified the declared controls. Its checked first-caption width matched the preview. The later refinement adds fitted contrast cards so result text remains readable over occupied source imagery. This remains synthetic layout/mechanism evidence, not validation of speech accuracy or automatic face placement.
