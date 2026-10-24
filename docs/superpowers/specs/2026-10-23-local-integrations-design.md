# Codex, Resolve and Higgsfield

The owner wants to use cooked's browser app with their existing ChatGPT account, then edit directly in Resolve and use Higgsfield assets. Implement in that order, retaining the existing library, jobs and review screens. This is a local desktop workflow; do not deploy a public service.

## Connect Codex

Use the installed Codex CLI's official app-server over private stdio. Codex owns authentication and token refresh. The app checks `account/read`, requires ChatGPT authentication, and provides the official browser login when needed. Never read, copy or return tokens. No API billing fallback.

Connect is idempotent. Display connected, signing in, working, waiting for an answer, disconnected and failed states truthfully. Keep a single app-server connection per home server, with one job at a time. Each editor job has its own ephemeral Codex thread. Existing queued jobs are claimed atomically; never steal taken jobs or replay completed/failed/cancelled work. Progress and final responses appear in the app. A process crash ends its active job with an actionable error rather than silently retrying work that could spend credits.

Use existing home job descriptions and portable skills. Resolve skill/plugin paths from the full checkout. Tell the agent that the adapter owns dispatch: do not recursively launch Claude or another listener. Use the installed editor Python environment, keep writes scoped to the media library and editor runtime, and retain command approval behavior. Command/file approvals and questions must be answered in the app, with no automatic approval and no stale answer applied to a later request. Unknown server requests fail closed. Stop interrupts the active turn and leaves the editor job cancelled; disconnect stops the app's child without logging the user out of Codex elsewhere.

Add an app panel with Connect Codex, status, latest messages, an input for direct requests, question/approval controls and Stop/Disconnect. Leave Claude available explicitly. While Codex is selected, new video/style jobs must not spawn Claude. Reopening `nextwork-editor` must preserve that choice. Questions and edits still use the existing review flow; document any unimplemented review routing rather than claiming parity.

Acceptance: real ChatGPT account check; a browser request gets an actual streamed response; a synthetic editing request creates its output; questions, cancellation, errors and request approval have deterministic protocol tests. No raw secrets in state or logs. Do not claim quality or time savings from a synthetic test.

## Resolve integration

Use the installed vendor scripting API to connect locally. First ship a source-cut timeline adapter from an existing cooked edit, plus supported zoom properties. Create a dedicated timeline, import original source media and place exact frame ranges; do not flatten the edit as the claimed native result. Save a manifest mapping managed clips. A follow-up updates only explicitly managed properties and detects user changes instead of replacing a manually edited timeline. Offer connection diagnostics and run through the app. Never modify the user's current timeline merely to probe connectivity. Test on generated footage and a dedicated test project/timeline. Establish captions, graphics and sound support separately; render-only graphics are not native Fusion controls.

## Higgsfield integration

Use the installed authenticated `higgsfield` CLI. Show connection state without exposing tokens. First support listing recent results and importing an explicitly selected completed image/video into the media library with provenance. Expose cost estimation and submission separately; no generation or upload as a side effect of connecting, listing or quoting a text-only request. Discover current model/parameter definitions through CLI metadata. Retain job IDs and distinguish pending, failed and completed. Generation requires an explicit request and a displayed quote; do not automatically retry an unknown submission. A browser connection check plus importing a synthetic local fixture can validate the plumbing; real paid generation needs a separate authorized creative brief and budget.

## Verification and feedback

Add meaningful regression tests before implementation. Exercise protocol state changes with a fake app-server subprocess and actual app-server authentication with the installed CLI. Run existing plugin checks and affected script demos, followed by the repository's offline demo suite. Verify the browser controls and a real response in the running app. Record exact outcomes and limits in the implementation notes. Keep media, credentials and account records outside Git. Use approved editorial feedback with the existing taste/style workflow.
