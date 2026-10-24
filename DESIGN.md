---
name: "GenMedia Editor"
description: "A local, media-led editing workspace with a dark glass shell and stable working surfaces."
colors:
  accent: "#e2eaf6"
  accent-hover: "#d0dfef"
  on-accent: "#17232f"
  error: "#f1a49c"
  segment: "#293543"
  canvas: "#141619"
  panel: "#1b1e22"
  sidebar: "#181b1f"
  text: "#eceef0"
  text-secondary: "#b1b7bf"
  text-muted: "#969fa9"
  line: "#30353c"
  field-border: "#464e58"
  surface-active: "#242a31"
  field: "#14181d"
  success: "#b1c9ba"
  glass: "rgba(39,45,55,.68)"
  glass-edge: "rgba(255,255,255,.14)"
  video: "#08090a"
  light-accent: "#425d79"
  light-accent-hover: "#334d67"
  light-on-accent: "#fff"
  light-canvas: "#f5f5f3"
  light-panel: "#fff"
  light-text: "#232528"
  light-text-secondary: "#575b60"
  light-field: "#fff"
  light-field-border: "#c7cbce"
  light-error: "#a13830"
  light-success: "#34664f"
  light-glass: "rgba(246,248,251,.75)"
  light-glass-edge: "rgba(35,50,70,.15)"
typography:
  headline:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: "32px"
    letterSpacing: "-.03em"
  board-title:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "25px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-.025em"
  wordmark:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-.03em"
  body:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "13px"
    lineHeight: 1.5
  passage:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "14px"
    lineHeight: 1.6
  button:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
  field:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "12px"
    lineHeight: 1.5
  label:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",sans-serif"
    fontSize: "11px"
    lineHeight: 1.5
  mono:
    fontFamily: "\"SFMono-Regular\",Consolas,monospace"
    fontSize: "11px"
    lineHeight: 1.5
rounded:
  control: "8px"
  navigation-item: "9px"
  thumbnail: "12px"
  library-panel: "14px"
  passages: "16px"
  shell: "18px"
  library-rail: "20px"
  pill: "999px"
  sequence: "5px"
spacing:
  inline: "8px"
  field-gap: "12px"
  passage-inline: "20px"
  section-gap: "22px"
  workspace-gap: "28px"
  wide-workspace-gap: "40px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "#ffffff07"
    textColor: "{colors.text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
  button-subtle:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "7px 6px"
  field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.text}"
    typography: "{typography.field}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  passages:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.passages}"
  passage-current:
    backgroundColor: "{colors.surface-active}"
    textColor: "{colors.text}"
    typography: "{typography.passage}"
    padding: "16px 20px"
  glass-shell:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.text}"
    rounded: "{rounded.shell}"
  sequence-segment:
    backgroundColor: "{colors.segment}"
    textColor: "{colors.text}"
    rounded: "{rounded.sequence}"
    padding: "8px"
---

# Design System: GenMedia Editor

## Overview

**Creative North Star: "The Dark Glass Editing Desk"**

Apple-inspired dark Liquid Glass frames the video and its edit decisions. Translucent navigation, restrained graphite working surfaces, and pale blue-white actions give the editor a calm, precise character. The content stays stable beneath the shell: media, transcript passages, planning fields, and status are readable on matte surfaces.

This is a web interpretation of the owner-selected direction, informed by the Aura references recorded in docs/design/genmedia-editor-direction.md. It is specific to GenMedia Editor; it does not establish a universal GenMedia palette or reproduce Apple’s native material renderer.

**Key Characteristics:**

- Media and decisions lead the workspace.
- Glass is concentrated in navigation and floating controls.
- Compact platform typography, rounded controls, and explicit state labels.
- Dark appearance by default, with an explicit saved light preference retained.

## Colors

The palette is graphite with a pale blue-white action accent, softened neutral text, and restrained success/error colors. The frontmatter contains observed CSS values; default dark primitives and explicit light counterparts are named separately.

### Primary

- **Pale blue-white** (`accent`, `accent-hover`, `on-accent`): approval, save, creation actions, current interval borders, and focus outlines. Dark foreground keeps primary action labels distinct.
- **Slate blue** (`light-accent`, `light-accent-hover`, `light-on-accent`): the corresponding explicit light appearance action palette.

### Secondary

- **Sage status** (`success`, `light-success`): completion and success text.
- **Soft coral** (`error`, `light-error`): errors and failed-operation messages. Status wording carries meaning alongside color.

### Neutral

- **Graphite desk** (`canvas`, `sidebar`, `panel`, `field`): canvas, rail, stable panels, and recessed form fields.
- **Cool graphite edges** (`line`, `field-border`, `surface-active`, `segment`): dividers, form outlines, current passage background, and kept source intervals.
- **Frosted graphite** (`glass`, `glass-edge`): translucent shell and its highlight edge. Light equivalents are `light-glass` and `light-glass-edge`.
- **Soft white and cool gray** (`text`, `text-secondary`, `text-muted`): primary content, secondary copy, and metadata.
- **Video black** (`video`): letterboxing and video stage.
- **Warm paper light appearance** (`light-canvas`, `light-panel`, `light-field`, `light-text`, `light-text-secondary`, `light-field-border`): explicit light surfaces and content.

These are representative reused tokens, not an exhaustive copy of legacy alias variables. `genmedia.css` remains the implementation source of truth. The sidecar’s synthesized tonal ramps are palette inspection aids, not additional application tokens.

## Typography

**Display and Body Font:** the platform sans stack in the frontmatter, led by Apple system fonts on supported platforms. The explicit light appearance retains the implemented Helvetica Neue/Helvetica/Arial/sans-serif stack.

**Label/Mono Font:** SFMono-Regular with Consolas and monospace fallbacks for timecodes, intervals, and command output.

The compact hierarchy prioritizes footage and decisions. Use sentence case, medium or semibold emphasis, and tabular numerals for durations. There is no marketing display font.

- **Headline:** library page heading; use the `headline` role.
- **Board title:** the edit-board page heading; use `board-title`.
- **Wordmark:** the compact GenMedia Editor identity; use `wordmark`.
- **Body and passage:** working copy uses `body`; passage text uses the larger `passage` role with extra leading.
- **Button, field, label, mono:** controls and metadata stay compact and readable. Preserve field labels when the visual direction disclosure is expanded.

## Layout

The library uses a floating sidebar and media-led project rows. The review route uses a glass rail beside a contained working app; the rail scrolls independently when its contents exceed the viewport. Its assistant toggle occupies header space so feedback and submission remain available.

The board is a centered workspace (maximum width 1760px), padded at 28px horizontally on desktop. Its two columns allocate `minmax(0,1.5fr)` to the viewer and `minmax(330px,1fr)` to passages, with the `workspace-gap`. From 1600px, the viewer grows to 1.65fr, the passage minimum becomes 390px, and the gap uses `wide-workspace-gap`. The player retains a 16:9 aspect ratio, `object-fit: contain`, and a maximum height of 54vh.

At 1050px and below, delivery controls stack. At 760px and below, the workspace becomes one column, main padding becomes 18px horizontally, shell margins tighten, and four workflow stages use equal grid columns. At 460px and below, delivery stacks again, direction fields use one column, and the compact wordmark hides the “Editor” suffix while retaining accessible identity. Review/library also retain their inherited route-specific responsive rules; this is not a single global breakpoint scale.

Prefer the implemented spacing relationships over adding new scales. Source strip segments use frame-duration flex weights, a small gap, and minimum widths for interaction; this is a navigable source overview, not a precision time ruler.

## Elevation & Depth

**The Stable Content Rule.** Use glass for the shell and transient controls; keep media, transcript text, planning fields, and status on stable working surfaces.

The shell uses translucent fills, a fine highlight edge, backdrop blur, and an ambient shadow. Main board chrome uses blur (24px) and saturation (1.3); the assistant panel uses blur (32px). The video stage has a restrained shadow. Avoid applying the shell material to every container.

The exact shadow, blur, and motion values live in `.impeccable/design.json`, because DESIGN.md frontmatter does not support those token classes. Unsupported backdrop filtering falls back to opaque panel surfaces on the library rail, review rail, assistant panel, and board header. Reduced transparency or increased contrast substitutes stable surfaces and removes selected blur/shadow treatments. Reduced motion collapses animations/transitions and disables smooth scrolling. These are implemented fallbacks, not a claim of formal accessibility conformance.

## Shapes

Controls use the `control` radius; navigation items are slightly rounder, thumbnails use `thumbnail`, passage containers use `passages`, and floating shell containers use `shell` or `library-rail`. Segmented navigation and assistant toggles use pill shapes. The source interval strip uses compact `sequence` corners to remain visually distinct from the broader media stage. Fine borders separate working regions; the video stage clips its content within its rounded frame.

## Components

### Buttons

Primary buttons use the action palette; secondary buttons use a subtle translucent fill and fine border. Subtle actions remove the visible border and reduce horizontal padding. Board hover states change background and border; primary hover uses `accent-hover`. Disabled buttons reduce opacity (0.42) and use a default cursor. Keyboard focus uses an accent outline (2px) offset by 3px. Minimum board button height is 36px on desktop and 40px at phone widths; passage watch actions and disclosures also expand at phone widths.

### Inputs / Fields

Fields use stable recessed surfaces, the control radius, and a visible border. Textareas may resize vertically. Planning fields sit in the passage disclosure; their summary preserves the presence of notes and non-default zoom. The shared focus outline applies to inputs, select elements, and textareas.

### Navigation

The floating header and library/review rails carry the material treatment. Board navigation uses a small pill group with a softly filled current item. Workflow stages communicate edit decisions, preview, approval, and Resolve delivery; state labels accompany tonal changes. Plain metadata tags remain text rather than introducing a new colored badge system.

### Cards / Containers

Library projects lead with real media thumbnails. The matte passage container uses a thin border and consistent inner padding. The current passage uses `surface-active`; removed passage text is struck through. Keep passage and protected hold controls remain directly available while repeated planning fields are disclosed on demand.

### Source sequence

**The Source Truth Rule.** Build the source sequence from real source intervals. Keep removed intervals visible with dashed borders and strike-through; do not replace data with a decorative waveform.

Each interval is labeled, keyboard focusable, and connected to its source start/end frames. Clicking watches the corresponding source interval and marks its passage current. Keep/protect decisions refresh the source strip; typing planning notes preserves the existing strip controls. The synthetic sample is explicitly identified; its labels are not a transcript.

### Assistant and delivery

The assistant panel uses glass externally and stable fields internally. On review, its header trigger and independently scrollable rail preserve access to feedback. On the board, saved preview selection, explicit approval, and separate Resolve timeline creation remain visible steps. Static zoom applies in Resolve; source-cut preview includes source audio. Visual direction and emphasis are planning notes and do not render captions or graphics.

## Do's and Don'ts

### Do:

- Do use the shared token cascade before adding route-specific styling.
- Do preserve the explicit saved light preference and the motion/transparency fallbacks.
- Do keep approval and creation of a separate Resolve timeline explicit.
- Do retain source media paths, API routes, stored revisions, and existing native timelines across visual changes.
- Do keep the review rail scrollable and its Codex control in header layout space.
- Do identify synthetic sample footage and distinguish planning notes from rendered output.

### Don't:

- Don’t present this editor palette as a settled brand standard for all GenMedia products.
- Don’t put translucent material behind long transcript passages or planning fields.
- Don’t imply captions, graphics, generated B-roll, or preview zooms are rendered when they are not.
- Don’t rename upstream compatibility identifiers or storage paths to satisfy a visible rebrand.
- Don’t infer formal accessibility compliance, creative-quality validation, or measured time savings from screenshots or synthetic samples.


Extraction and limits: documented from the final CSS cascade and route markup on 2026-10-24. Source values were checked against `plugins/ai-editor/lib/ai_editor/genmedia.css` and `edit-board.css`; interval behavior was read from `edit-board.js`. Existing screenshots are under `.impeccable/review/`. This documentation pass did not run browser, real-footage creative-quality, assistive-technology, or native-renderer tests. Refer to the implementation review for actual UI verification.

Verification record: the independent final screenshot/source review returned SHIP for its targeted design scope after confirming rail scrolling, unobstructed feedback, and fresh mobile navigation captures. It did not independently exercise full computed contrast, keyboard traversal, assistive technology, explicit-light rendering, or reduced-preference rendering. Home/review appearance helpers now default to dark when no explicit choice is saved, consistent with the CSS.
