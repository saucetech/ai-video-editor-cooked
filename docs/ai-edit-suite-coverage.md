# AI Edit Suite workflow coverage for this fork

Owner request, October 24, 2026: build the reviewable board and Resolve workflow first, and create original implementations of all workflows showcased by AI Edit Suite. This table is the maintained feature inventory for that request. “Existing” identifies a component in the fork, not acceptance on the owner's footage. No real recording is available yet. Only the synthetic board/Resolve path is verified here.

Sources inspected: [suite showcase](https://softgirlnocode.com/ai-edit-suite), [CapCut workflow](https://softgirlnocode.com/resources/edit-videos-in-capcut-with-codex), [HyperFrames workflow](https://softgirlnocode.com/resources/edit-videos-with-ai-hyperframes), [caption guidance](https://softgirlnocode.com/resources/cinematic-captions), [motion brief](https://softgirlnocode.com/resources/ai-motion-graphics-brief). These public examples define desired behaviors, not private implementation details. No proprietary templates or assets are incorporated.

## Coverage and sequence

| Workflow / feature | Current status | Next demonstrable acceptance |
|---|---|---|
| ChatGPT account and conversational editing | Existing Codex adapter; live synthetic request/question/review tested | Complete an owned recording and a normal correction without a provider switch |
| First cut, retakes, filler and dead air | Existing cut/transcription pipeline; board reads its decisions | Retain best takes and complete words/meaning on representative footage |
| Review before render | **Implemented board**: keep/restore, protection, source playback, visual notes, emphasis, versioned previews and approval | Founder accepts the cut and can revise it without losing choices |
| Editable finishing in a real NLE | **Editable visual slice implemented**: source/audio/static zoom, separate B-roll, Fusion Text+ captions and native caption/hook recipes, with declared-control readback and actual paired preview/Resolve captures; synthetic handoffs, corrections and earlier manual text preservation verified | Validate representative real footage and sound cues |
| Editable CapCut draft handoff | **Pending** CapCut destination integration; Resolve is the owner's first finishing target | Verify official plugin availability/account/region, rebuild the approved source ranges, then edit separate text/audio/visual tracks in CapCut |
| Meaning-aware B-roll matching | **Manual local B-roll placement implemented** with in-point and FPS/canvas conformance; semantic ranking remains pending | Show source-linked alternatives for one spoken passage, choose a shot and revise its placement in Resolve |
| Cut at the phrase ending | Existing frame/word-aware cut machinery; board retains its ranges | Listen to joins, protect consonants and avoid cutting a qualification on real speech |
| Preserve screen-demonstration holds | **Manual board hold protection implemented**; automatic action-aware decisions pending | A demonstration completes visibly; silence trimming does not erase the useful action |
| Reusable brand and reference style | **Analyzed-style board transfer implemented**: source-hashed normalized snapshots, font/measurement provenance, explicit approximations and retained corrections; existing profile/override tools remain | Two reference-derived choices and a founder correction persist across two edits |
| Blended captions / meaningful hero words | **Clean, editorial serif and word spotlight implemented**, with aligned phrase paging, corrected-text static fallback, contrast panels, SRT and visible editable Resolve Text+ nodes; manual emphasis notes remain planning | Accurate, readable phrase captions with controlled emphasis and no face/product occlusion |
| Minimal line-art explanations | Existing motion-design/overlay tools; original reusable recipe pending | A spoken idea receives a useful original line-art explanation timed to its phrase |
| 3D line-art treatment | Existing motion tools; original reusable recipe pending | A briefed dimensional visual explains the selected idea and survives a revision |
| Giant Word Behind opening hook | Cutout and text primitives exist; complete hook recipe pending | Original hero text appears behind a stable subject cutout with clean edges |
| Wall-to-One opening hook | Recipe pending | Multiple relevant visual tiles resolve into one selected idea with controllable timing |
| Outline Draw opening hook | **Original native Outline draw implemented** with text, accent geometry and sampled curves; paired native comparison available | A meaningful original outline is drawn at the intended beat and matches the chosen design |
| Profile Scroll opening hook | Capture primitives exist; complete recipe pending | An owned/authorized profile capture scrolls legibly and lands on a chosen detail |
| Prompt-to-Play opening hook | **Text-only prompt → result variant implemented** with two editable fields; output-media reveal remains pending | A prompt sequence transitions into the associated output using selected original assets |
| Done Wall opening hook | Recipe pending | A collection of completed outputs is presented legibly with a clear focal result |
| Folder-to-Carousel opening hook | Recipe pending | A selected local asset collection becomes an ordered, editable visual sequence |
| Beat-based motion board and proof frames | **Original hero reveal, outline draw and text prompt/result recipes implemented**, plus caption styles, B-roll and actual native proof samples; broader beat generation remains pending | Approved beat notes drive graphics and matching proof frames, then a corrected render |
| Faceless presenter selection | **Pending** avatar workflow and reusable original presenter records | Choose a presenter, preview consistency and retain it across two clips |
| Avatar script authoring | **Pending** dedicated workflow | Script approval and scene timing are retained through a revision |
| Avatar look/theme and caption treatments | Existing brand settings are reusable; avatar scene application pending | Apply a chosen theme and readable captions to the same approved script |
| Avatar voice / synchronized narration | **Pending** provider selection and actual timing tests | Clear approved narration, synchronized presenter and corrected pronunciation |
| Avatar render and review | **Pending** full generation/compositing loop | One completed video plus an ordinary correction, with measured time, spend and quality |
| Higgsfield account and asset integration | Existing account/list/model/quote controls tested; completed generation/import/placement unverified in real use | Explicitly selected/authorized result becomes a replaceable source-linked timeline asset |

## Build milestones

1. **Board and native source cut**: delivered first; mechanics validated with synthetic media. Operating instructions: [Edit board](edit-board.md).
2. **Visual execution**: render the approved caption/motion direction and add selected owned B-roll to the board and Resolve. This makes the current planning annotations produce visible treatments. Verify each destination capability rather than flattening an entire edit by default.
3. **Original reusable recipe library**: implement the caption looks, line-art treatments and all seven showcased hook families using original designs. Use preview and correction to judge each recipe before calling it complete.
4. **Generated-shot completion**: finish Higgsfield quote → explicit generation/import → local media/provenance → selected beat → Resolve, including failures, retries and real cost.
5. **Faceless studio**: presenter, script, theme, voice, render and review as a complete workflow. Reuse the board's approved revisions and asset identities. Provider availability, rights and cost remain decisions to verify before integrating.
6. **Long-form and repurposing**: extend accepted workflows to longer mixed camera/screen recordings and useful short excerpts, with actual quality/effort measurement.

This inventory establishes scope and build order. It does not represent pending features as implemented, reproduce the unreleased course, or support a claim that the fork is better than every competitor. Update each row with the relevant implementation and acceptance evidence as it ships; use the existing founder common-footage procedure once real footage exists.
