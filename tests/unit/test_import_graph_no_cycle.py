from __future__ import annotations


def test_import_graph_no_cycle() -> None:
    import app.core.common.eligibility_channel  # noqa: F401
    import app.core.common.filters  # noqa: F401
    import app.core.common.join_resolver  # noqa: F401
