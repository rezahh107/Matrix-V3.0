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
- Primary workflow pages are one scrollable work column containing the whole workflow, primary action included. See §4a for the composition grammar.
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

Tonal direction (Fluent-2 neutral):

- Dark workflow surfaces are a genuinely neutral charcoal/gray family. `background`, `surface_primary`, `surface_secondary`, `control_surface` and `control_hover` must read as neutral rather than blue/navy: no surface role may carry a channel spread or a blue-over-red bias wide enough to tint the page.
- Light keeps a neutral light page with clearly distinguishable white primary surfaces. Depth comes from a visible page/surface/control separation plus subtle structural boundaries, never from dark heavy outlines.
- Routine controls do not glow against the page: ordinary buttons, tab panes, popups and list/table shells use `boundary_subtle`; `boundary_control` is reserved for essential authored affordances such as text-entry shells, header rules and the scrollbar handle.
- Accent is one controlled cool blue/teal-blue family. It is used for the primary CTA, focus, selection, active primary navigation and meaningful interactive states, and is never spread as a fill across ordinary controls.

## 4a. Primary workflow composition

A primary workflow page (`build`, `allocate`) composes, in order, inside one scrollable working column:

1. hero / workflow header;
2. page guidance;
3. one or more **Major Section Regions**;
4. a content-contained **Action Region**.

### Major Section Regions

A Major Section is one meaningful semantic group of the workflow, and it must read as a single Common Region:

- solid opaque `surface_primary` surface;
- `boundary_subtle` structural boundary at `container_radius`;
- deliberate inner padding (`major_section_padding`);
- an explicit section title, visibly distinct from ordinary field labels;
- a macro gap (`major_section_gap`) to the next Major Section.

Grouping is carried by the combination of region boundary, surface distinction, title typography, internal proximity and inter-section spacing. Title font size alone is never the grouping mechanism.

Section identity is **structural and semantic**: a Major Section is a `QGroupBox` owned directly by the page's own top-level layout, and it is marked with the presentation role `sectionRole="major"`, which the central QSS governs. Titles, translated copy and child indexes are not identity. The default `QGroupBox` presentation stays flat, so only these groups become regions.

Major Section Regions are **not** permission for card soup. The region is the grouping level; inside a region, normal form composition applies. Individual fields, help lines, rows and buttons never get their own region. Heading + spacing/proximity remains the correct tool for smaller local groupings, including nested ones.

### Action Region

The primary action of a workflow page belongs to the page content flow:

- it follows the final meaningful Major Section, inside the same scrollable content;
- it shares the page's working column and keeps logical trailing alignment in both directions;
- it is reachable by ordinary page scrolling; there is **no** requirement for, and no active use of, a fixed window-bottom CTA footer;
- it preserves the primary button's semantic variant, wiring, validation, execution behavior and keyboard accessibility;
- it carries no footer-bar material of its own.

### Large windows

Unused application canvas after the completed page content is acceptable and expected. Content stays top-aligned: Major Sections are never vertically stretched, and content is never distributed over the available window height, to fill a large or maximized window. A semantic gap between the form and its own action is a defect; empty canvas below the finished content is not.

## 5. Canonical semantic palette

### Light

| role | value |
| --- | --- |
| `background` | `#EDEFF1` |
| `surface_primary` | `#FFFFFF` |
| `surface_secondary` | `#E1E4E7` |
| `control_surface` | `#FFFFFF` |
| `control_hover` | `#F2F4F6` |
| `boundary_subtle` | `#D3D7DB` |
| `boundary_control` | `#7B7F83` |
| `text_primary` | `#1A1D21` |
| `text_secondary` | `#4C5257` |
| `accent` | `#1A6079` |
| `accent_hover` | `#155569` |
| `accent_pressed` | `#11475A` |
| `focus` | `#175A73` |
| `selection` | `#D5E7EE` |
| `success` | `#146C43` |
| `warning` | `#8A4B08` |
| `error` | `#B42318` |
| `disabled_text` | `#7C8288` |
| `disabled_surface` | `#E7E9EB` |
| `diagnostic_background` | `#F1F3F5` |
| `diagnostic_text` | `#23282D` |

### Dark

| role | value |
| --- | --- |
| `background` | `#191B1D` |
| `surface_primary` | `#212427` |
| `surface_secondary` | `#2B2F32` |
| `control_surface` | `#262A2D` |
| `control_hover` | `#313538` |
| `boundary_subtle` | `#3A3E42` |
| `boundary_control` | `#7B7F83` |
| `text_primary` | `#E8EAEC` |
| `text_secondary` | `#AFB5BA` |
| `accent` | `#2A7391` |
| `accent_hover` | `#2E7A99` |
| `accent_pressed` | `#24657F` |
| `focus` | `#7CC6E0` |
| `selection` | `#26414C` |
| `success` | `#5CC08E` |
| `warning` | `#E7BB59` |
| `error` | `#F08079` |
| `disabled_text` | `#7F868C` |
| `disabled_surface` | `#26292C` |
| `diagnostic_background` | `#141618` |
| `diagnostic_text` | `#D8DCE0` |

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

Macro (page-composition) spacing:

- `major_section_gap=24` — the gap between two Major Section Regions. This is the one named macro extension of the routine rhythm, justified because the inter-section gap must be perceptibly larger than any intra-section gap for the region grammar to read.
- `major_section_padding=16` — inner padding of a Major Section Region.
- `major_section_title_line=22` — one Subtitle line at the Qt logical 96dpi baseline, with headroom for the taller Persian ascender/descender band.
- `major_section_extra_gap` (derived, `major_section_gap - within_group`) — the extra margin a region adds on top of the page rhythm, so the macro gap has one source rather than a second competing literal.
- `major_section_title_band` (derived, `major_section_padding + major_section_title_line + within_group`) — top padding that clears the title painted inside the region, so the group's content never collides with its own title.

The locked spacing semantics for a primary workflow page:

| relationship | value |
| --- | --- |
| page rhythm (hero ↔ guidance, and the base gap between page items) | `within_group=12` |
| row ↔ row, and field ↔ field help, inside a section | `within_group=12` |
| section title ↔ section body | `within_group=12` (via `major_section_title_band`) |
| Major Section ↔ Major Section | `major_section_gap=24` |
| final Major Section ↔ Action Region | `section_spacing=20` |

**Inter-section gap must exceed the intra-section row gap.** That relationship is the locked invariant; the exact values above are the current reconciliation of it with the existing tokens. Field help uses the same `12` row rhythm rather than a tighter `4–8`, because a help label keeps the full content column: a `QFormLayout` inside a resizable `QScrollArea` does not propagate height-for-width, so narrowing wrapped copy reserves a single line and lets it collide with neighbouring rows.

Density targets:

- ordinary text control: minimum `32px`;
- compact utility control: minimum `28px`;
- primary CTA: minimum `34px`;
- table/list rows: `28–32px` target;
- routine horizontal control padding: `10px`;
- compact horizontal padding: `8px`.

Use flexible minimums rather than rigid fixed heights where translation/font metrics need growth.

Shared working-column geometry (semantic presentation tokens, not per-page literals):

- `working_measure=1120` — maximum measure of the centered primary working column. It governs the hero/content working width, the Major Section Region width, the field working width and the content-contained Action Region alignment. Because all of them share one measure, the action stays aligned with the form it submits instead of drifting to a distant window edge on wide desktops. It is **not** a mechanism for aligning a fixed window-bottom footer; there is no such footer.
- `field_measure=720` — maximum measure of a form field row inside that column, so inputs do not stretch to an uncontrolled desktop-wide line length. Wrapped explanatory copy deliberately keeps the full column (see §6 spacing note).
- Both are logical (leading/trailing) values: the column is centered and the action keeps its trailing position in LTR and RTL alike.

Shared Matrix-owned control geometry:

- `combo_dropdown_width=28` — the single source for the QSS `QComboBox::drop-down` surface, the combo content inset (`combo_dropdown_width + 2`) and the Python vector chevron overlay rectangle.
- `scrollbar_thickness=12`, `scrollbar_handle_min=36` — the reserved scrollbar extent and minimum handle length. The extent is identical in every state, so hover cannot reflow content.

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
- Local and nested grouping uses heading + spacing/proximity before any container outline. Primary-workflow **Major Section Regions** are the named exception: there, a subtle surface plus a `boundary_subtle` outline and padding are the intentional semantic grouping tools (§4a), because heading and spacing alone did not separate major groups from ordinary labels.
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

In particular, `QComboBox` is `STYLED`: outer shell, content, drop-down surface, arrow, governed popup and direction-safe presentation have one Matrix visual owner, with the drop-down region and the vector chevron overlay derived from the same `combo_dropdown_width` token rather than from a second `QStyle` geometry query.

`QScrollBar` is `STYLED` as of the Fluent-2 polish pass. Matrix owns the complete visible family in both orientations — groove/shell, handle with a minimum length and rest/hover/pressed/disabled states, `add-line`, `sub-line`, the directional arrow subcontrols, `add-page` and `sub-page` — while Qt keeps scrolling behavior, range/value, input and accessibility. Partial scrollbar styling, `QProxyStyle`, replacement scrollbar widgets and custom scrolling implementations remain forbidden.

The corner between two scrollbars belongs to the scroll area, not to the scrollbar: Qt defines `::corner` as a `QAbstractScrollArea` subcontrol. Matrix paints it as `QAbstractScrollArea::corner` in the same central QSS, keeping the quiet neutral material. `QScrollBar::corner` names no real subcontrol and must not be authored.

`QCheckBox::indicator` remains Qt-owned under the existing HYBRID boundary.
