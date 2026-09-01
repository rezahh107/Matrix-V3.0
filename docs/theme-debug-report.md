# Theme stylesheet crash analysis (str.format KeyError)

> **Status: HISTORICAL / RESOLVED.** This report records a prior `str.format`-based stylesheet failure. The current `app/ui/theme.py` uses targeted token replacement rather than `str.format`, so the crash mechanism described below is not the current runtime state. For current Qt visual-ownership boundaries, use `docs/UI_PRESENTATION_AUTHORITY.md`.

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
## Crash surface
- Entry path: `MainWindow.__init__` calls `apply_theme(app, self._theme)`, which loads `styles.qss` and runs `qss.format(**_token_mapping(theme))`. This explodes with `KeyError: '\n    background-color'` when raw CSS braces are fed to `str.format`.

## Root cause (exact location)
- The first selector block in `app/ui/styles.qss` begins with `QWidget {` followed by a newline and `background-color: {background};`. Because the opening `{` after `QWidget` is not escaped, Python sees it as the start of a format field whose name becomes the newline+indent+`background-color` up to the first `}` it encounters. That field name is not in `_token_mapping`, so `str.format` raises `KeyError`. (Lines 2–7).

## Token inventory vs mapping
- Placeholders found in QSS: `background`, `text`, `font_fa`, `body_size`, `font_en`, `card`, `border`, `radius_md`, `spacing_sm`, `spacing_xs`, `spacing_md`, `primary_soft`, `primary`, `surface_alt`, `text_muted`, `card_title_size`, `radius_sm`, `log_background`.
- `_token_mapping` provides: `background`, `card`, `surface_alt`, `text`, `text_muted`, `primary`, `primary_soft`, `success`, `warning`, `error`, `log_background`, `border`, `font_fa`, `font_en`, `title_size`, `card_title_size`, `body_size`, `spacing_xs`, `spacing_sm`, `spacing_md`, `spacing_lg`, `radius_sm`, `radius_md`, `radius_lg`.
- Coverage: every placeholder used in QSS exists in `_token_mapping`; additional mapping keys are currently unused.

## Design risks identified
- Any CSS block brace (`selector { ... }`) is parsed by `str.format` unless escaped as `{{`/`}}`. Every block in `styles.qss` currently uses raw braces, so the first one triggers the crash before token replacement occurs.
- The templating strategy mixes structural braces with format tokens, so a single missing escape causes runtime failure. Future dark/light variants or resource QSS files would be equally fragile.

## Remediation options (no code applied yet)
- Option A: Keep `str.format` but escape every structural brace to `{{`/`}}`; keep `{TOKEN}` for theme placeholders. Requires auditing all QSS files and ensuring new blocks follow the rule.
- Option B: Swap to a placeholder syntax that does not collide with CSS braces, e.g., `string.Template` with `$TOKEN`, or a targeted replace of `{TOKEN}` tokens only, leaving structural braces untouched.
- Option C: Preprocess QSS to escape braces automatically (e.g., replace `{`→`{{` and `}`→`}}` before formatting) and then reintroduce tokens, or run a safer per-token substitution routine.

