# Performance Risk Register — Join Bucketing

## Scenario
- Dataset / scenario: `tests/data/golden_perf/v1/`
- Entry point: `scripts/performance/run_perf_suite.py`
- Expected artifacts: `decisions.csv`, `metrics.json` (includes runtime, stage timings, peak memory)

## Risks
- Potential drift vs. golden parity (baseline decisions).
- Non-determinism between repeated runs with join bucketing enabled.
- Peak memory regression beyond prior observation.
- Silent behavioral drift when school/center wildcard paths bypass buckets.

## Mitigations
- Re-run determinism + golden parity pytest targets locally with `use_join_buckets=True`.
- Inspect `metrics.json` for runtime/memory and compare to previous PRs.
- Keep output directories isolated per run (avoid cross-run contamination).
- Default flag OFF and rollback via `SMARTALLOC_OPT_JOIN_BUCKETS=0`.
