# Matrix UI Design Contract

## 1. Scope and precedence

This document is the closed workspace/visual contract for the Matrix PySide6 presentation layer. It does not define domain behavior and is subordinate to LAW / Technical SSoT and `AGENTS.md`.

Presentation responsibilities are split deliberately:

- `docs/UI_PRESENTATION_AUTHORITY.md` answers **who owns** each Qt control/subcontrol visual surface (`STYLED`, `NATIVE`, `HYBRID`).
- This document answers **how** the owned Matrix presentation is composed under C2 + V2.

Neither document may change allocation, join, ranking, capacity, trace, persistence, CLI, Core, or Infra semantics.

## 2. C2 workspace architecture

Matrix uses `PRIMARY_WORKSPACE_WITH_UTILITY_SEPARATION`.

- Primary destinations are registered workflow capabilities. Current normal end-user set: `build`, `allocate`.
- **Rule Engine is retired from the normal GUI workspace.** Its backend and CLI remain intentionally available; GUI absence is not backend-dead-code evidence.
- Primary navigation is generated from the registered capabilities and must not assume a fixed count.
- `explain` and `database` are direct one-step secondary destinations. They must not read as peer workflow stages.
- Destination identity is a stable surface ID, never a hard-coded tab index.
- Primary workflow pages retain scrollable work content plus a fixed, always-reachable primary CTA footer.
- Existing Build/Allocate command shortcuts remain command semantics; navigation must not repurpose them. No public Rule Engine QAction/shortcut is part of the current GUI contract.

## 3. Operational status and diagnostics

Routine work has one compact persistent summary containing the current operation/state, meaningful stage/progress, database health/severity, and language.

Deep diagnostics use the existing `QSplitter` capability and are **collapsed by default**.

- Routine/idle: collapsed.
- Running: progress remains visible in the compact status; diagnostics do not auto-dominate.
- Warning: severity remains visible; diagnostics remain one-step accessible.
- Error/failure: diagnostics reveal automatically.
- Manual: the user may expand/collapse diagnostics directly.
- Splitter persistence uses the versioned key `ui/main_splitter_v2`; legacy splitter state must not reopen the old permanent panel.
- Settings and History Metrics are support/global commands, not permanent lower-shell controls. Developer/demo material may remain inside diagnostics.

The unified Settings surface also owns **Diagnostics & Advanced Tools / ابزارهای خطایابی و پیشرفته** presentation for the eight intentionally retained `UserSettings` capabilities. It must use three semantic groups rather than an unexplained flat checkbox list:

1. Diagnostics / Observability: Trace Debug Sheets, Mentor Pipeline Trace, Pool Governance Trace, Bucket Trace, Trace Sheet Export.
2. Analysis: History Metrics.
3. Advanced Validation / Execution Behavior: QA Pool Coverage Rules, Use Join Buckets.

Each capability row must expose a title, ON/OFF control, short plain-language explanation, visible behavioral-impact label, and `Full Guide / راهنمای کامل`. Critical distinctions must remain visible: QA Pool Coverage **may affect validation**; Use Join Buckets is an **algorithmic/performance execution-path option**, not diagnostic-only. Full guides must expose both Persian RTL and English LTR regardless of current application language. Canonical technical guidance is `docs/DEVELOPER_DIAGNOSTICS.md`.

## 4. V2 visual direction

Matrix uses `SOLID_LAYERED_PRODUCTIVITY`: opaque, neutral, flat-first, desktop-dense, low-noise and high-legibility.

Hierarchy priority:

1. typography;
2. proximity and spacing;
3. limited surface contrast;
4. borders/radius only when they communicate a role;
5. semantic color only for actual meaning.

Glassmorphism, backdrop blur, Mica/Acrylic imitation, frosted/translucent workflow surfaces, routine same-plane shadows, glow and decorative motion are forbidden.

## 5. Canonical semantic palette

### Light

| role | value |
| --- | --- |
| `background` | `#F4F6F8` |
| `surface_primary` | `#FFFFFF` |
| `surface_secondary` | `#E6EBF1` |
| `control_surface` | `#FFFFFF` |
| `control_hover` | `#F2F5F9` |
| `boundary_subtle` | `#D5DCE5` |
| `boundary_control` | `#7A8798` |
| `text_primary` | `#182230` |
| `text_secondary` | `#526174` |
| `accent` | `#1F5FBF` |
| `accent_hover` | `#184F9F` |
| `accent_pressed` | `#123D7D` |
| `focus` | `#0B57D0` |
| `selection` | `#D9E8FF` |
| `success` | `#146C43` |
| `warning` | `#8A4B08` |
| `error` | `#B42318` |
| `disabled_text` | `#7A8796` |
| `disabled_surface` | `#E9EDF2` |
| `diagnostic_background` | `#EEF2F6` |
| `diagnostic_text` | `#253347` |

### Dark

| role | value |
| --- | --- |
| `background` | `#0F141A` |
| `surface_primary` | `#171E26` |
| `surface_secondary` | `#202A35` |
| `control_surface` | `#1B2632` |
| `control_hover` | `#243342` |
| `boundary_subtle` | `#33404D` |
| `boundary_control` | `#7A8A9D` |
| `text_primary` | `#E7EDF4` |
| `text_secondary` | `#A9B6C4` |
| `accent` | `#2F67CA` |
| `accent_hover` | `#356FD3` |
| `accent_pressed` | `#2E65C7` |
| `focus` | `#73A9FF` |
| `selection` | `#233B5B` |
| `success` | `#4FC38A` |
| `warning` | `#F0C04A` |
| `error` | `#FF7A73` |
| `disabled_text` | `#7E8B99` |
| `disabled_surface` | `#202832` |
| `diagnostic_background` | `#111820` |
| `diagnostic_text` | `#D7E0EA` |

`ThemeColors` is the single semantic source. Compatibility names, where temporarily retained, must resolve to these roles and must not define separate hex values.

## 6. Spacing, density and geometry

Semantic spacing:

- `micro=4`
- `icon_to_text=6`
- `label_to_control=8`
- `control_to_control=8`
- `field_to_field=8`
- `within_group=12`
- `between_groups=16`
- `section_spacing=20`
- `page_margin_normal=20`
- `page_margin_compact=16`
- `panel_padding=12`
- `cta_separation=16`

Normal structural rhythm is `4 / 8 / 12 / 16 / 20`; `6` is an allowed icon/text optical spacing. Geometry-specific exceptions must be named and justified.

Density targets:

- ordinary text control: minimum `32px`;
- compact utility control: minimum `28px`;
- primary CTA: minimum `34px`;
- table/list rows: `28–32px` target;
- routine horizontal control padding: `10px`;
- compact horizontal padding: `8px`.

Use flexible minimums rather than rigid fixed heights where translation/font metrics need growth.

## 7. Typography

There is one application base-font authority in `app/ui/theme.py` / `app/ui/fonts.py`.

- FA/RTL prefers embedded `Vazirmatn`/`Vazir`, with a safe Persian fallback.
- EN/LTR prefers `Segoe UI`, with the existing safe fallback chain.
- Embedded Vazirmatn is registered in memory with Qt; production startup must not require writing into the application install/source directory or scanning arbitrary Downloads folders.

Roles:

| role | size | weight |
| --- | ---: | ---: |
| Caption | 9pt | 400 |
| Body | 10pt | 400 |
| BodyStrong | 10pt | 600 |
| Subtitle | 11pt | 600 |
| Title | 13pt | 600 |

Routine `700`/display-size typography is not part of V2. Primary CTA uses BodyStrong.

## 8. Borders, radii, shadows and motion

- Essential styled controls use `boundary_control`; structural separators use `boundary_subtle` only when useful.
- Primary grouping normally uses heading + spacing/proximity before any container outline.
- Routine radii: `control_radius=6px`, `container_radius=8px`.
- No routine `14px` radius tier.
- No routine same-plane shadows.
- Hover/pressed/focus are color/border state changes, not opacity or scale animation.
- No indefinite progress-caption pulse.

## 9. Interaction and color semantics

Materially STYLED controls provide applicable `rest`, `hover`, `pressed`, `focus`, `disabled`, and selected/checked states.

- Accent is reserved for primary CTA, active primary navigation marker, focus/selection and important interaction emphasis.
- `success`, `warning`, `error` are used only for actual semantic states.
- Configuration `Off` is neutral, not an error color.
- Selected navigation uses structure in addition to fill (accent edge + stronger text).
- Critical state always has wording/shape or another explicit cue; color alone is insufficient.

Contrast tests use WCAG relative luminance. Active normal text targets `>=4.5:1`; essential authored boundaries and focus target `>=3:1`. Passing palette checks is not a claim of full WCAG compliance.

## 10. Bidi, resize and DPI

- Both FA/RTL and EN/LTR are first-class.
- Prefer Qt logical layout direction and leading/trailing semantics over hard-coded left/right geometry.
- Anchor sizes are `960×640` and `1200×800`; layouts must also tolerate continuous resizing around them.
- Page margins use approximately `16px` at compact `960×640` width and `20px` at normal/larger width.
- Qt device-independent geometry remains authoritative; do not multiply widget geometry by scale factor.
- Bounded High-DPI validation covers `1.25`, `1.5`, `1.75`, `2.0` in isolated processes and records logical geometry, DPR, scale and critical visibility/clipping evidence.
- High Contrast support is **NOT_IMPLEMENTED / NOT_VALIDATED** by this contract.

## 11. Component authority relationship

Before visual work on a Qt family, consult `docs/UI_PRESENTATION_AUTHORITY.md`.

- `STYLED`: Matrix owns every relevant geometry-sharing visible subcontrol while Qt keeps behavior.
- `NATIVE`: do not introduce targeted partial geometry styling.
- `HYBRID`: stay inside the explicitly partitioned Matrix-owned surface.

In particular, `QComboBox` is `STYLED`: outer shell, content, drop-down surface, arrow, governed popup and direction-safe presentation have one Matrix visual owner. `QScrollBar` remains native and `QCheckBox::indicator` remains Qt-owned under the existing HYBRID boundary.
