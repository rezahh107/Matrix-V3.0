# Matrix dialogs and operational state evidence

Base (production) commit: 782d178f5dc539bc078e04a1e67a10ad6ea5baa4
Captured branch commit: 9a756f3b8d1f05149c33f29cb1ae68b02a491d75
Captured PNGs: 84
Failed scenarios: 0

## Boundaries
Verification-only; no production UI/Core/Infra/persistence changes. All running/failure/completion scenarios use a synthetic Worker.
A captured PNG is evidence, not an automatic visual acceptance.

## Runtime cases
- settings-light-fa-720x760-top: settings-light-fa-720x760-top.png
- settings-light-fa-720x760-bottom: settings-light-fa-720x760-bottom.png
- settings-light-fa-720x760-guide-fa: settings-light-fa-720x760-guide-fa.png
- settings-light-fa-720x760-guide-en: settings-light-fa-720x760-guide-en.png
- settings-light-fa-620x560-top: settings-light-fa-620x560-top.png
- settings-light-fa-620x560-bottom: settings-light-fa-620x560-bottom.png
- settings-light-fa-620x560-synthetic-overflow: settings-light-fa-620x560-synthetic-overflow.png
- settings-light-fa-620x560-guide-fa: settings-light-fa-620x560-guide-fa.png
- settings-light-fa-620x560-guide-en: settings-light-fa-620x560-guide-en.png
- history-light-fa-empty: history-light-fa-empty.png
- history-light-fa-populated: history-light-fa-populated.png
- history-light-fa-rightmost: history-light-fa-rightmost.png
- history-light-fa-long-value-control: history-light-fa-long-value-control.png
- operation-light-fa-ready: operation-light-fa-ready.png
- operation-light-fa-missing-school-warning: operation-light-fa-missing-school-warning.png
- operation-light-fa-after-missing-school: operation-light-fa-after-missing-school.png
- operation-light-fa-indeterminate: operation-light-fa-indeterminate.png
- operation-light-fa-completed: operation-light-fa-completed.png
- operation-light-fa-controlled-failure: operation-light-fa-controlled-failure.png
- operation-light-fa-failure-modal: operation-light-fa-failure-modal.png
- explain-light-fa-sample: explain-light-fa-sample.png
- settings-light-en-720x760-top: settings-light-en-720x760-top.png
- settings-light-en-720x760-bottom: settings-light-en-720x760-bottom.png
- settings-light-en-720x760-guide-fa: settings-light-en-720x760-guide-fa.png
- settings-light-en-720x760-guide-en: settings-light-en-720x760-guide-en.png
- settings-light-en-620x560-top: settings-light-en-620x560-top.png
- settings-light-en-620x560-bottom: settings-light-en-620x560-bottom.png
- settings-light-en-620x560-synthetic-overflow: settings-light-en-620x560-synthetic-overflow.png
- settings-light-en-620x560-guide-fa: settings-light-en-620x560-guide-fa.png
- settings-light-en-620x560-guide-en: settings-light-en-620x560-guide-en.png
- history-light-en-empty: history-light-en-empty.png
- history-light-en-populated: history-light-en-populated.png
- history-light-en-rightmost: history-light-en-rightmost.png
- history-light-en-long-value-control: history-light-en-long-value-control.png
- operation-light-en-ready: operation-light-en-ready.png
- operation-light-en-missing-school-warning: operation-light-en-missing-school-warning.png
- operation-light-en-after-missing-school: operation-light-en-after-missing-school.png
- operation-light-en-indeterminate: operation-light-en-indeterminate.png
- operation-light-en-completed: operation-light-en-completed.png
- operation-light-en-controlled-failure: operation-light-en-controlled-failure.png
- operation-light-en-failure-modal: operation-light-en-failure-modal.png
- explain-light-en-sample: explain-light-en-sample.png
- settings-dark-fa-720x760-top: settings-dark-fa-720x760-top.png
- settings-dark-fa-720x760-bottom: settings-dark-fa-720x760-bottom.png
- settings-dark-fa-720x760-guide-fa: settings-dark-fa-720x760-guide-fa.png
- settings-dark-fa-720x760-guide-en: settings-dark-fa-720x760-guide-en.png
- settings-dark-fa-620x560-top: settings-dark-fa-620x560-top.png
- settings-dark-fa-620x560-bottom: settings-dark-fa-620x560-bottom.png
- settings-dark-fa-620x560-synthetic-overflow: settings-dark-fa-620x560-synthetic-overflow.png
- settings-dark-fa-620x560-guide-fa: settings-dark-fa-620x560-guide-fa.png
- settings-dark-fa-620x560-guide-en: settings-dark-fa-620x560-guide-en.png
- history-dark-fa-empty: history-dark-fa-empty.png
- history-dark-fa-populated: history-dark-fa-populated.png
- history-dark-fa-rightmost: history-dark-fa-rightmost.png
- history-dark-fa-long-value-control: history-dark-fa-long-value-control.png
- operation-dark-fa-ready: operation-dark-fa-ready.png
- operation-dark-fa-missing-school-warning: operation-dark-fa-missing-school-warning.png
- operation-dark-fa-after-missing-school: operation-dark-fa-after-missing-school.png
- operation-dark-fa-indeterminate: operation-dark-fa-indeterminate.png
- operation-dark-fa-completed: operation-dark-fa-completed.png
- operation-dark-fa-controlled-failure: operation-dark-fa-controlled-failure.png
- operation-dark-fa-failure-modal: operation-dark-fa-failure-modal.png
- explain-dark-fa-sample: explain-dark-fa-sample.png
- settings-dark-en-720x760-top: settings-dark-en-720x760-top.png
- settings-dark-en-720x760-bottom: settings-dark-en-720x760-bottom.png
- settings-dark-en-720x760-guide-fa: settings-dark-en-720x760-guide-fa.png
- settings-dark-en-720x760-guide-en: settings-dark-en-720x760-guide-en.png
- settings-dark-en-620x560-top: settings-dark-en-620x560-top.png
- settings-dark-en-620x560-bottom: settings-dark-en-620x560-bottom.png
- settings-dark-en-620x560-synthetic-overflow: settings-dark-en-620x560-synthetic-overflow.png
- settings-dark-en-620x560-guide-fa: settings-dark-en-620x560-guide-fa.png
- settings-dark-en-620x560-guide-en: settings-dark-en-620x560-guide-en.png
- history-dark-en-empty: history-dark-en-empty.png
- history-dark-en-populated: history-dark-en-populated.png
- history-dark-en-rightmost: history-dark-en-rightmost.png
- history-dark-en-long-value-control: history-dark-en-long-value-control.png
- operation-dark-en-ready: operation-dark-en-ready.png
- operation-dark-en-missing-school-warning: operation-dark-en-missing-school-warning.png
- operation-dark-en-after-missing-school: operation-dark-en-after-missing-school.png
- operation-dark-en-indeterminate: operation-dark-en-indeterminate.png
- operation-dark-en-completed: operation-dark-en-completed.png
- operation-dark-en-controlled-failure: operation-dark-en-controlled-failure.png
- operation-dark-en-failure-modal: operation-dark-en-failure-modal.png
- explain-dark-en-sample: explain-dark-en-sample.png

## Failures (not PASS)
- No harness exceptions; visual/interaction acceptance remains manual.

## Static inspection hypotheses to verify in PNG
- Main toolbar actionHistoryMetrics opens app.ui.history_metrics.HistoryMetricsDialog (current-run metrics), not app.ui.history_metrics_dialog.HistoryMetricsDialog (stored runs).
- HistoryMetricsPanel empty copy and METRIC_COLUMNS headers appear hard-coded in English.
- Settings has three nested diagnostic category groups; inspect visual density at 620x560.
- Indeterminate progress initially has a 0% caption; inspect whether this communicates uncertainty.
- Explain sample must be reviewed for clipped/ambiguous columns; no redesign authorized.

## Remaining acceptance
- Review full-resolution screenshots and negative-control crops; inspect keyboard navigation with real input.
- Repeat core focus, scroll, window-manager chrome, Windows font fallback and DPR on real Windows 10/11, not solely offscreen CI.
