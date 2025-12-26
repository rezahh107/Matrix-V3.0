# Performance PR Checklist (Correctness-First)

Use this checklist before merging any performance-focused PRs.

- [ ] Golden dataset path respected: `tests/data/golden_perf/v1/`.
- [ ] `python scripts/performance/run_perf_suite.py` executed (or called from tests) and artifacts captured.
- [ ] Decisions CSV compared against committed baseline (golden parity == 0 drift).
- [ ] Determinism validated: two consecutive runs on the same inputs produce identical decisions.
- [ ] Peak memory observed via tracemalloc noted in PR description (no hard ceiling enforced in P0).
- [ ] Stage timing fields captured or stubbed in metrics.json with clear labels.
- [ ] Windows-safe paths verified for generated artifacts.
