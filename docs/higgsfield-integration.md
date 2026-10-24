# Local Higgsfield integration

The editor uses the installed authenticated `higgsfield` CLI. Authentication and
credential storage remain owned by that CLI. The adapter does not open credential
files, return account email, or expose raw CLI errors. No dependency was added.

## Repeatable workflow

Trigger: connect an existing Higgsfield account, browse recent generated media,
import a selected result, or request a new text-only generation.

Inputs: a signed-in CLI; a media library path; an explicitly selected completed job
ID for import; or a model ID, text parameters and a separately confirmed quote for
new generation.

1. Check `status()` and list `recent(kind, limit)`. These do not generate or upload.
2. Import the user's selected completed result with `import_result(job_id, library)`.
   It re-fetches the job, confirms `completed`, and imports one image/video result
   into `videos/higgsfield/<job-id>.<extension>`. A neighboring `<job-id>.json`
   records provider, job ID, model, timestamps, URL without its signed query,
   byte count, media type and SHA-256. It excludes prompts and reference inputs.
   Importing an unchanged verified result again reuses the local file.
3. For new work, browse `models(kind)` and call `quote(model, params)`. The adapter
   reads `model get` metadata on every quote and validates scalar parameters and
   enum values. Media/reference/file/path/URL inputs are rejected because the CLI
   explicitly documents that even `generate cost` auto-uploads local file inputs.
4. Display the returned model, parameters and estimated credits. A quote expires
   after ten minutes and belongs to the current home-server process. It is not a
   reserved price or a generation job. Check the available credit balance before
   choosing whether to proceed.
5. Only a separate explicit confirmation calls `generate(quote_id, confirmed=True)`.
   The adapter consumes the quote under a lock before invoking the CLI. A double
   click, concurrent confirmation, timeout or lost response cannot reuse it. An
   unknown outcome tells the user to inspect recent jobs; it never retries the
   submission. Restarting the home server invalidates open quotes.
6. Retain the submitted job ID and refresh recent results. Pending and failed jobs
   do not become importable, even if their records contain a URL.

Deliverables: local media plus provenance, or a credit estimate, or a submitted
job ID with its actual state. These are separate outcomes. Successful plumbing
checks are not evidence of creative quality or time saved.

Acceptance: no upload/generation during account/list/model/text-quote calls;
completed-state verification before import; bounded public HTTPS downloads;
provenance matches the imported bytes; separate single-use confirmed submission;
unknown submission outcome remains unknown; credentials and raw errors stay out
of UI state. Feedback about unsupported CLI shapes goes into a sanitized fixture
in `tests/test_higgsfield_bridge.py` before changing normalization. Re-run the
focused tests and a read-only real CLI check. Do not capture account records,
prompts or signed URLs in Git.

## Python API used by the home server

The module is `plugins/ai-editor/lib/ai_editor/higgsfield_bridge.py`. Errors from
operations other than status raise `HiggsfieldError` with safe display text.

| Function | Result |
| --- | --- |
| `status()` | `{connected, state, credits, error?}`; state is `connected` or `disconnected` |
| `recent(kind='video', limit=12)` | list of `{id, job_id, status, model, display_name, kind, created_at, result_url, thumbnail_url, importable}`; URLs are null unless completed |
| `models(kind='video')` | current list of `{job_type, display_name, type}` |
| `import_result(job_id, library: Path)` | `{job_id, path, provenance, kind, status: 'imported'}` |
| `quote(model, params)` | `{id, quote_id, model, credits, params, expires_at, submitted: false}`; expiry is Unix seconds |
| `generate(quote_id, confirmed=False)` | `{job_id, id, status, model, quote_id, submitted: true}` |

Image/video kinds are supported; recent limit is 1–50. Result URLs remain in local
UI memory for previews, and signed queries are excluded from provenance. The
adapter does not log CLI stdout/stderr. The home server must continue to protect
these local-only endpoints and require an explicit browser action for imports or
paid submissions. A boolean confirmation is required; the string `"true"` fails.

## Download boundary

Downloads permit HTTPS port 443 without URL credentials. Local, private, reserved,
multicast and link-local hosts are rejected, including mixed public/private DNS
answers. Each redirect is checked; at most three redirects are followed. The socket
is pinned to a checked public address while TLS still validates the original
hostname, preventing a second DNS lookup from switching to an internal address.
No proxy environment variables or arbitrary browser-supplied fetch URLs are used.
Import always obtains its URL from `generate get <selected-id>`.

Downloads are limited to 256 MiB, require a matching recognized image/video MIME
and extension, verify the file signature, reject mismatched content lengths and
remove partial files. Supported formats: PNG, JPEG, WebP, GIF, MP4, MOV with an
`ftyp` header, and WebM. A signature check is not a complete media decoder. Large
or unsupported containers require a separate future workflow. Imports stay inside
the selected media library, including when a folder is a symlink.

## Verification recorded 2026-10-23

- Read actual installed CLI help for account, generation list/get/cost/create and
  model list/get. List uses `--size`, while quotes/submission accept model flags.
- Read-only `account status` and the adapter's `status()` both confirmed the
  existing sign-in. Account identifiers and balances are not retained in this repository.
- The adapter listed two recent videos, both with `completed` state, and read the
  current image model catalog (40 entries at verification time).
- A real text-only `nano_banana_pro` quote for a synthetic blue-circle prompt
  returned an estimate of **2 credits** and `submitted: false`. This estimate is
  specific to that request, not a general price or committed spend.
- Wrote the initial 14 tests first; they failed because the adapter was missing.
  Added four follow-up tests, including an observed multicast-host validation
  failure, then fixed it. **18 focused regression tests passed.** They cover
  account redaction, actual CLI argument forms, unfinished-job URL suppression,
  synthetic PNG import and provenance, idempotency, failed/pending import refusal,
  HTTPS/DNS/redirect restrictions, socket pinning, bounded MIME/signature checks,
  live parameter validation, confirmation, expiry, concurrent submission and
  timeout/no-retry behavior.
- The import fixture uses mocked CLI/network boundaries and a local synthetic
  one-pixel PNG. No real account media was downloaded for these tests.
- **No source upload, paid generation, or credit spend was performed.** Actual
  submission output normalization accepts a direct job object or a single-item
  job list; paid submission remains unverified until a separate creative brief
  and budget are authorized. Browser controls and whole-app checks are recorded
  by the home-server integration work, rather than inferred from these tests.

Focused verification:

```sh
python3 -m unittest discover -s tests -p test_higgsfield_bridge.py
```
