# Matrix V3 — PR #28 / PR #29 evidence archive (2026-11-01)

**Status: PARTIAL EVIDENCE PRESERVATION — DO NOT CLOSE THE SOURCE PRs YET.**
This branch is separate from `main` and is **not** a production fix. All replay/test and screenshots are historical observations, not Owner visual acceptance.

## Sources and exact revisions

- Production `main` baseline on inventory: `91b765ca6bfb72da6012e4c119a8f3c4e08d9944` (PR #30 already merged).
- PR #28: https://github.com/rezahh107/Matrix-V3.0/pull/28; published Head `82eca13347414024a23b49534b2bad465c232db1`; original capture run `41281584739`, run commit `bcdfb6464f0f843c1ee51c9d2b3b2310635708e1`; artifact `13073348210`. Capture's production base: `782d178f5dc539bc078e04a1e67a10ad6ea5baa4`.
- PR #29: https://github.com/rezahh107/Matrix-V3.0/pull/29; PR Head `867c31125623c3588b1446fd43448cf90690eb68`; diagnostic run `41229347383` on workflow commit `55ef253f28fc70b62df22785fc590e71d1f8858a`. Actual tested source Head: `3aa5e7266a35e56d9bf2dec6705d1fc1d3352812`; tested Base: `782d178f5dc539bc078e04a1e67a10ad6ea5baa4`.
- Original native access violation observed in job `124615002999`, run `41224482102`. Its later rerun succeeded, not evidence of a permanent native fix.

## What this branch contains

- `pr28/captures/`: **84 published UI scenario PNGs**, five contact sheets, `manifest.json`, `SUMMARY.md` and `runner-status.txt`. The files are copied by exact Git blob SHA from PR #28 final Head, not regenerated or scaled.
- `pr28/source/`: original Python capture script and capture workflow **as inert historical files outside** `.github/workflows/`.
- `pr29/source/`: Qt diagnostic workflow as an inert historical file, outside `.github/workflows/`.
- `pr29/artifacts/qt-diagnostic-artifact-contents.tar.xz`: 40 original inner files from the six downloaded diagnostic artifacts, with `SOURCE_ARTIFACT_INVENTORY.json` recording each original Actions ZIP SHA-256, artifact IDs, inner paths, sizes and individual SHA-256 digests. Original inner files were not rewritten.
- `MANIFEST.json`: archive SHA-256, size, original commit/path and Git blob IDs for all **96 copied Git file objects**, plus original PR #28 capture-run ZIP member SHA-256.

## Material source discrepancy — blocking PR closure

Original capture artifact `matrix-dialog-operational-evidence` (ID `13073348210`, run `41281584739`) was downloaded and fully inspected. **Five PNG members in the original Actions ZIP differ byte-for-byte from the PNG files committed in the published PR #28 Head:**

1. `contact-operation.png`
2. `operation-dark-en-controlled-failure.png`
3. `operation-dark-fa-controlled-failure.png`
4. `operation-light-en-controlled-failure.png`
5. `operation-light-fa-controlled-failure.png`

Both original-run member and published-branch SHA-256 identities are recorded in `MANIFEST.json`. **The published-branch copy, not the exact original-run version of these five images, is stored in this Git archive.** The downloaded original ZIP is available as a conversation deliverable and temporarily as a GitHub Actions artifact, but neither establishes an authorized permanent secondary archive. No fake PASS or claim of complete archival is warranted. An authorized durable store for the exact five original-run image bytes (and verification) is required **before PR #29 or PR #28 may close** under the Owner's explicit safeguards. Do not overwrite one capture generation with the other.

## Observed diagnostics and limits

- Run `41229347383`: six Windows/offscreen matrix jobs all **SUCCESS**; repeated single/harness/full UI test processes exited successfully. None reproduced the original native crash.
- Original failing CI job `124615002999`: `Windows fatal exception: access violation`; observed job exit 1. **Root cause UNKNOWN.**
- Six artifact families available: `qt-av-head-single`, `qt-av-base-single`, `qt-av-head-harness_file`, `qt-av-base-harness_file`, `qt-av-head-full_ui`, `qt-av-base-full_ui`. No native binary dump was present in the downloaded artifact contents; only dump indexes and Windows event text evidence were available.
- Diagnostic text/artifacts inspected for secrets and sensitive content before public-branch publication; no password/token/identifying user database or raw memory dump found by bounded inspection. This is not a guarantee against all undiscovered sensitive content.
- PR #28 capture run `41281584739` successful with 84 reported cases and 0 harness failures. Its **latest PR Head** has `action_required` checks, not an exact-Head equivalent success. Screenshots use Qt `offscreen`, synthetic Worker and 96 logical DPI; physical Windows visual acceptance is **not proven**.
- PR #30 (already merged) separately corrected operational progress/status; do not treat it as a crash fix, nor assume all historical PR #28 UI/UX findings have been fixed.

## Reproducing integrity checks

1. Fetch this specific branch and check out a fresh copy: `git fetch origin evidence/matrix-pr28-pr29-archive-20261101 && git checkout --detach origin/evidence/matrix-pr28-pr29-archive-20261101`.
2. Under `evidence/archive/pr28-pr29-20261101/`, parse `MANIFEST.json`; for each `files[]` entry verify `Path.exists()`, `Path.stat().st_size == size_bytes`, `hashlib.sha256(Path.read_bytes()).hexdigest() == sha256`, and that `git hash-object` matches `git_blob_sha1`.
3. Open and verify **all 89 archived PNGs**, including all 84 scenario screenshots and 5 contact sheets, using Pillow's `Image.verify()`; do not resize/re-encode any.
4. Decompress the Qt evidence bundle with `tar -xJf pr29/artifacts/qt-diagnostic-artifact-contents.tar.xz` into a *new safe temporary directory*, inspect `SOURCE_ARTIFACT_INVENTORY.json` and verify every inner checksum against each preserved file. Inspect text before sharing it anywhere else.
5. For the Qt source test, run the archived workflow's pinned revisions in a controlled Windows runner with `uv sync --locked`; use a fresh process for each repetition; it may fail intermittently. The archived workflow is **not active CI**. Original crash reproduction remains unknown.

See `ARCHIVE_VERIFICATION.md` for the independent evidence and the blocking gap. Do not merge this archival branch into `main` as part of this housekeeping task.
