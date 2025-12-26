# Performance Risk Template

Use this template for P1+ performance work to document risk and mitigations.

## Scenario
- Dataset / scenario: `tests/data/golden_perf/v1/`
- Entry point: `scripts/performance/run_perf_suite.py`
- Expected artifacts: `decisions.csv`, `metrics.json` (includes runtime, stage timings, peak memory)

## Risks
- Potential drift vs. golden parity (baseline decisions).
- Non-determinism between repeated runs.
- Peak memory regression beyond prior observation.
- Windows path handling for artifact writes.

## Mitigations
- Re-run determinism + golden parity pytest targets locally.
- Inspect `metrics.json` for runtime/memory and compare to previous PRs.
- Keep output directories isolated per run (avoid cross-run contamination).
- Document any intentional deviations and link to approvals.
