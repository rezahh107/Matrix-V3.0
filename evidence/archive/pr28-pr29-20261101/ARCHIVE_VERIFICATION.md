# Fresh-checkout archive verification — 2026-11-01

**VERIFIED: archival evidence is present and intact.** Verification was executed in a fresh isolated GitHub Actions checkout of archive branch commit \`324633f3a7b71a237dcd3d1496ca8a2628bb248d\`.

## Evidence inventory and checks

- **102/102** archived file records: existence, size, SHA-256 and Git blob SHA-1 all matched.
- PR #28: **84 original scenario PNGs** and **5 contact sheets** (89 published PNGs) passed Pillow decoding.
- The exact original GitHub Actions capture ZIP, artifact **13073348210**, run **41281584739**, passed archive SHA-256, ZIP member CRC and manifest checks; all **89 original-run PNGs** passed Pillow verification.
- Exactly **five** original Actions PNGs differ bytewise from published branch snapshots; all five originals are independently archived and read back bit-for-bit; no source images were resized or regenerated. This is a historical provenance distinction, not a test failure.
- PR #28 Python capture script and PR #28 + PR #29 original workflows were verified as inert source material (not active workflows).
- PR #29: **6** diagnostic artifact datasets with **40/40** inner files matched sizes and SHA-256 and inventory membership; no raw Windows memory dump is in those saved six datasets.
- All relative changes from baseline \`91b765ca6bfb72da6012e4c119a8f3c4e08d9944\` were restricted to the dedicated evidence archive path plus this one-shot workflow (which removes itself in the publishing commit).
- Security: previously reviewed text artifacts include GitHub runner paths but no detected sensitive dumps, credentials, customer data, or database exports; bounded review only.
- Verified source identities: PR #28 Head \`82eca13347414024a23b49534b2bad465c232db1\`; capture source-run SHA \`bcdfb6464f0f843c1ee51c9d2b3b2310635708e1\`; PR #29 Head \`867c31125623c3588b1446fd43448cf90690eb68\`; diagnostic job tested Head \`3aa5e7266a35e56d9bf2dec6705d1fc1d3352812\` and Base \`782d178f5dc539bc078e04a1e67a10ad6ea5baa4\`.
- GitHub Actions run 41229347383: six historical SUCCESS diagnostic jobs, **without** reproducing the native failure. The crash remains **UNKNOWN/UNRESOLVED**.
- Original failing job 124615002999 remains valid historical evidence; replay does not establish a fix.
- Latest PR #28 Head \`action_required\` checks are not confused with the earlier successful capture run.
- UI/UX issues from PR #28 remain **unconfirmed as fixed**: History header/cell truncation and empty-state localization, Persian buttons, Explain reason truncation, mixed-language text, stored-history reachability, real Windows font/focus/scroll/high-DPI acceptance. PR #30 separately corrected operational progress/status on main, which was not retested as part of this archive job.

## Important boundaries

This is **evidence preservation and integrity validation**, not app runtime testing, real interactive Windows acceptance, crash root-cause proof, product fix, release, deployment, or UI/UX sign-off. No changes to main, production paths or existing source branches were requested from this workflow.

## Reproduction

From a fresh checkout of the archive branch, read \`MANIFEST.json\`; run SHA-256 and \`git hash-object\` on all indexed files; Pillow-verify all 89 published captures plus 89 original Actions PNGs and five distinct original variants; compare original ZIP members against published variants; recheck tar.xz inventory (40 inner records) with SHA-256. This GitHub Actions execution exercised those validations using Python 3.12 and Pillow 11.3.0.

## Earlier partial validation history

The first archive commit lacked the five byte-distinct original Actions captures. An authorized branch-specific, self-removing archival GitHub Actions workflow run 41305711305 copied the exact historic ZIP and five variants and matched their checksums. Subsequent fresh-checkout verification above establishes their presence at the checked-out revision. The old provisional claim of unpreserved files no longer applies.
