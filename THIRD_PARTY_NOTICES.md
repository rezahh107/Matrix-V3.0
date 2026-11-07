# Matrix source distribution — third-party notices

**Scope:** Matrix-V3.0 source-only GitHub archives and the selected Git+uv
source candidate. This document is a factual notice, **not** a license for
Matrix-owned or contributed source, an authorization to publish, or a
certification that the full public repository snapshot is privacy-cleared.

## Vazirmatn — font included in Matrix source

Matrix embeds the Vazirmatn font software as Base64 data in
`app/ui/assets/font_data_vazirmatn.py`. Its documented version is 33.003.

- Copyright 2015 The Vazirmatn Project Authors.
- License: **SIL Open Font License 1.1** (not MIT).
- The existing complete copyright and license notice is
  [app/ui/assets/fonts/LICENSE.md](app/ui/assets/fonts/LICENSE.md).
- The asset provenance, version and decoded SHA-256 are recorded in
  [app/ui/assets/fonts/README.md](app/ui/assets/fonts/README.md).

The font license and attribution must accompany source distributions containing
the embedded font. Do not infer that Matrix's declared package metadata
relicenses the font.

## Qt for Python / PySide6 — runtime installed separately

`uv.lock` pins `pyside6`, `pyside6-essentials`, `pyside6-addons`
and `shiboken6` to **6.11.2**. Matrix imports Qt for Python APIs. These
dependencies are resolved separately when the Owner runs `uv sync --locked`;
the selected Matrix source archive does not bundle the corresponding wheels
or compiled Qt libraries.

Qt for Python has open-source **LGPLv3/GPLv3** and separately licensed
commercial offerings, subject to the applicable component licenses and
distribution method. For licensing and third-party component information,
consult the [Qt for Python documentation](https://doc.qt.io/qtforpython-6.11/licenses.html)
and [Qt open-source obligations](https://www.qt.io/development/open-source-lgpl-obligations).

If a future Matrix artifact **does** convey PySide6 wheels, Qt libraries,
an executable bundle or other binaries, its exact contents and license
obligations must be reviewed separately. This source-only notice is not a
substitute for license texts or other required materials in a binary distribution.

## Matrix project source — rights remain unverified

`pyproject.toml` currently declares `license = { text = "MIT" }` and
`Smart Allocation Team` as the author. The reviewed repository has no root
Matrix `LICENSE` file or established evidence that all relevant source
owners and contributors authorized publication under those terms. Neither
this notice nor the metadata establishes those rights; do not invent a
copyright holder, issue a project license or assert rights clearance.

The public GitHub Release workflow creates GitHub `git archive` ZIP/TAR
snapshots of the tagged commit. Reviewed exact-path `export-ignore` entries
omit designated fixture data from these archives while retaining it in Git
checkouts for regression tests. The selective uv candidate is separate. This notice does not change the existing full-tree privacy gate,
authorize the disclosure of student or organizational data, or select an
official application version. Publication requires separate Owner approval
and source-appropriate privacy/rights review.
