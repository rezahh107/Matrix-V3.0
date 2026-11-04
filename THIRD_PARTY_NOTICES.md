# Source distribution licensing and third-party notices

**Scope:** Matrix-V3.0's **source + uv** review candidate, not a binary installer or an authorized publication. This inventory does not license the Matrix application, certify all code ownership, authorize a release, or alter its existing domain/Policy obligations.

## Project-owned or contributed Matrix source — rights not yet established

`pyproject.toml` currently declares `license = { text = "MIT" }` and `authors = [{ name = "Smart Allocation Team" }]`. The MIT metadata was added in commit `16408249972e64f617d0865c4bc1b46127d1d7fe` (2025-11-24). The reviewed repository has **no project-root LICENSE file** and no independently verified record of the rightsholder(s), contributors' copyright permissions, or permissions for all reused source. A public Git repository and a package metadata string do not independently establish those rights.

**Publication prerequisite:** the Owner/rightsholder must confirm that the project code can be licensed under the already declared MIT terms, including all relevant contributors/reused code, and provide the correct copyright attribution/holder (or specify a rights-cleared alternative). Only then add a project `LICENSE` and reconcile metadata as needed. The third-party texts below **are not** the Matrix application's license.

## Qt for Python / PySide6 — installed by uv, not carried in this source ZIP

`uv.lock` currently pins each of `PySide6`, `PySide6-Essentials`, `PySide6-Addons`, and `shiboken6` to **6.11.2**. Matrix source directly imports `PySide6.QtCore`, `PySide6.QtGui`, and `PySide6.QtWidgets`. Qt for Python's Community Edition offers LGPLv3/GPL licensing options; Qt also offers separately licensed commercial packages. The relevant Qt module licenses, bundled Qt third-party components, and the selected licensing option must be honored.

**Notice:** Matrix uses Qt for Python (PySide6) by The Qt Company / Qt Project and other contributors. For reference, the complete GNU LGPL version 3 terms, **including the incorporated GNU GPL version 3 text**, are reproduced verbatim in [licenses/LGPL-3.0-only.txt](licenses/LGPL-3.0-only.txt). This copy is for the covered libraries; it does not relicense Matrix source.

The candidate contains `uv.lock` and Python application code, **not** PySide6 wheels or Qt native libraries (`.whl`, `.dll`, `.pyd`, `.so`). On a fresh Windows setup, `uv sync --locked` obtains those external packages separately from their configured registry. The Qt for Python Essentials/Addons wheels themselves carry compiled Qt components. The mere listing of these dependencies does not mean the source ZIP physically redistributes their binaries.

For an application distributed under the open-source **LGPLv3** option, end-user freedoms must be preserved, including the ability to use a modified/replaced LGPL-covered library, and prominent use/license notices. **If Matrix or its publisher later redistributes Qt/PySide6 binary wheels, bundled Qt DLLs, frozen builds, or devices**, it must separately assess and satisfy the corresponding license-text, third-party-attribution, corresponding-library-source (or controlled written offer), relinking/installation-information and other applicable obligations for the exact delivered components. An upstream URL alone is not necessarily a sufficient substitute for a source offer when the publisher conveys covered binaries. No such redistribution is part of the current source ZIP.

Authoritative versioned references:
- [Qt for Python 6.11 overview](https://doc.qt.io/qtforpython-6.11/)
- [Qt for Python 6.11 package details (wheel contents)](https://doc.qt.io/qtforpython-6.11/package_details.html)
- [Qt for Python 6.11 third-party licenses](https://doc.qt.io/qtforpython-6.11/licenses.html)
- [PySide6 6.11.2 metadata](https://pypi.org/project/PySide6/6.11.2/)
- [Qt's LGPL/GPL obligations](https://www.qt.io/development/open-source-lgpl-obligations)
- [SPDX text source for LGPL-3.0-only](https://github.com/spdx/license-list-data/blob/main/text/LGPL-3.0-only.txt)

## Vazirmatn — actually embedded in this source distribution

Matrix includes Base64-encoded Vazirmatn font software in `app/ui/assets/font_data_vazirmatn.py`. The pinned decoded font is Version 33.003, SHA-256 `696249a2c74b39ffdef55de4df2809c5b639d3ff80d618d8160a095d2fd49dca`. Attribution: **Copyright 2015 The Vazirmatn Project Authors**. It remains governed by the **SIL Open Font License 1.1**, not MIT or Qt LGPL. The font's existing full copyright/license text is [app/ui/assets/fonts/LICENSE.md](app/ui/assets/fonts/LICENSE.md) and its provenance is [app/ui/assets/fonts/README.md](app/ui/assets/fonts/README.md).

## Other Python libraries

Other packages resolved through `uv.lock` (such as pandas, NumPy, openpyxl, PyYAML, and Pandera) are runtime dependencies fetched into the user's own uv environment; they are **not bundled as wheel/native code** in this source ZIP. Each remains under its own license. This notice is deliberately bounded to source-distribution material; it is not a certification of all transitive licenses or future binary redistribution.

## Release boundary

The center-manager names already present in the approved three Policy files have explicit Owner approval for public disclosure; that decision is unchanged. It does not authorize disclosure of other private data. A technical preview is limited to synthetic data, and it does not prove physical Windows operator acceptance or compatibility with actual organizational Sabt profiles. **No official application version or publication has been authorized.**
