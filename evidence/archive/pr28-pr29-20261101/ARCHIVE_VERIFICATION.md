# Archive verification — PR #28 and PR #29 (2026-11-01)

## Verdict

**PARTIALLY VERIFIED / BLOCKED_EVIDENCE_PRESERVATION. Do not close either PR.** The published PR #28 evidence and PR #29 diagnostic text are independently represented and crosschecked, but five exact original-run PNG versions have not been preserved in an authorized, persistent secondary Git/restricted archive. The owner's mandatory closure condition therefore fails.

## Source identities and inventory

| Evidence | Original identity | What is stored in this branch |
|---|---|---|
| PR #28 source Head | `82eca13347414024a23b49534b2bad465c232db1` | 84 original *published branch* scenario PNGs, five contact sheets, published manifest/summary/runner-status; immutable Git-blob copied |
| PR #28 original capture Actions artifact | run `41281584739`, SHA `bcdfb6464f0f843c1ee51c9d2b3b2310635708e1`, artifact ID `13073348210` | Original ZIP downloaded, SHA256 checked, every one of its 89 PNG members validated locally; five original-run versions **not** in persistent archive |
| PR #28 tools/workflow | captured from PR Head `82eca13347414024a23b49534b2bad465c232db1` | Python capture harness and workflow inert under archive path |
| PR #29 workflow | PR Head `867c31125623c3588b1446fd43448cf90690eb68` | Inert diagnostic workflow under archive path |
| PR #29 result artifacts | run `41229347383`, workflow SHA `55ef253f28fc70b62df22785fc590e71d1f8858a` | Six artifact datasets, **40 original text entries**, preserved bytewise in a tar.xz + per-file integrity inventory |

Independent branch was created from current `main` `91b765ca6bfb72da6012e4c119a8f3c4e08d9944`. The archive branch is `evidence/matrix-pr28-pr29-archive-20261101`. Archive **commit to cite is current branch HEAD at the time of final readback**; this file documents prior verification and cannot contain its own eventual commit hash.

## Commands and observed results

1. Read live GitHub REST branch refs for `main`, PR #28 and PR #29; read each PR's current state/Head/Base. **PASS at inventory**: both Draft/Open, unchanged source Heads, PR #29 based on PR #28, PR #30 already Merged.
2. Read GitHub Actions run `41281584739` and its job. **PASS**: capture job succeeded, publish job skipped on PR event. Capture artifact `13073348210` present and not expired. Latest PR #28 Head has **`action_required`** checks; distinguish these facts.
3. Download original Actions capture ZIP and examine with `zipfile.ZipFile`; calculate `hashlib.sha256`; parse manifest and open **all 89** PNGs with Pillow `Image.verify()`. **PASS for downloaded ZIP**: 84 cases + five sheets, no corrupt PNG, failure_count 0. Reported synthetic/offscreen coverage does not prove Owner visual acceptance.
4. Read final published PR #28 directory via GitHub REST `contents/...?...ref=82eca...` and copy 92 source blobs by unchanged Git SHA1. **PASS for published source**: 89 PNGs + three metadata files, source blob identities retained, no resizing/regeneration. **FAIL for exact equivalence to original Actions archive** on **five** PNGs; names and both SHA-256 values retained in `MANIFEST.json`.
5. Read PR #29 exact workflow, Actions jobs, each artifact's metadata and download all **six** ZIPs. Inspect filenames/text, native dump indexes and event strings, test exit records and source revision metadata. **PASS**: all six jobs succeeded, original inner files re-packed byte-preservingly as `pr29/artifacts/qt-diagnostic-artifact-contents.tar.xz`, its SHA256 `79afc9c641a76dddded4a45236509ce57775e09f0ee6adb4792eae827e8ff3fb`. **No memory dumps present** in six downloaded artifacts. No reproduced native crash. Original failure remains confirmed separately by log `124615002999`.
6. Public-archive security review of the 40 diagnostic text files: bounded content scan for passwords, secrets, emails, database rows and raw native dump files. **PASS for inspected surface only**: no such sensitive contents found; transient runner filesystem paths present, not user database contents. No redactions applied to these 40 files. Unknown undiscovered sensitivity cannot be ruled out categorically.
7. Create a new Git tree based on `main` plus exact source Git blobs, then save PR #29 text artifact bundle as a Git blob with an independently compared SHA1. **PASS**: no changes under `app/`, `tests/`, `config/`, active `.github/workflows/` or `main`.
8. Read back archive HEAD via GitHub REST, and list archive directories on that independent ref; compare each `MANIFEST.json` record with remote archived file's Git SHA1 and byte size. **PASS**: **96/96** objects exist, original Git SHA1 and stored size match, **96/96** SHA-256 strings provided. This validates the Git object-copy identity and file indexing. It is **not** a fresh local Git checkout and does not independently rehash every remote archive byte.
9. Read `main` ref again after archive writes: **PASS**: SHA remained `91b765ca6bfb72da6012e4c119a8f3c4e08d9944`.
10. Direct `git clone` / fresh local checkout cannot execute in this environment because external github.com DNS/network access is unavailable to the container; live authenticated GitHub REST reads were used as the bounded alternative. **NOT VERIFIED**: full fresh-checkout local SHA-256 scan and Pillow verify on the five revised published PNGs.

## Original artifact SHA-256 and discrepancies

Original capture artifact ZIP SHA-256:
`1d1fbe489024ebd2be0b30d7fb5cbbacd439f7bdc6bb3148489d215a01df296c`.

The following **original captured file bytes are not in the separate Git archive**: `contact-operation.png`, `operation-dark-en-controlled-failure.png`, `operation-dark-fa-controlled-failure.png`, `operation-light-en-controlled-failure.png`, `operation-light-fa-controlled-failure.png`. Original zipped image digests, their sizes and distinct archived versions are identified in `MANIFEST.json`. Their original ZIP remains available as a GitHub Actions artifact only until retention expires (currently 2027-01-30), and as a conversation download, **neither alone is sufficient durable preservation** under this mission.

## Test semantics and outstanding claims

- Source immutable diagnostic replay Head: `3aa5e7266a35e56d9bf2dec6705d1fc1d3352812`; Base: `782d178f5dc539bc078e04a1e67a10ad6ea5baa4`.
- Crash observed in job `124615002999` (`Windows fatal exception: access violation`, process exit 1). Later targeted six-job replay success cannot establish crash absence or root cause.
- Physical Windows real display compositor, focus/keyboard, high-DPI 125–200%, font readability and final UI acceptance not tested/approved by this archival work.
- Historical PR #28 visual issues (FA/EN partial localization, History header/value truncation, Explain reason truncation, mixed-language diagnostic text, stored history dialog reachability) remain **unverified as corrected**. Idle progress was separately corrected through already merged PR #30 and is not claimed fixed here.

## Explicit closure gate

**DO NOT CLOSE PR #29 OR PR #28** until the five exact original Actions screenshot variants are copied into an appropriate durable archive with SHA-256 readback, the rest of the archived source/files pass fresh-checkout validation, and an OPEN Qt tracking issue exists. PR closure must remain separate from evidence-only Git branch creation; no merge, release, production rewrite or branch deletion is authorized.
