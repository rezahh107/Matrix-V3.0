from __future__ import annotations

import pandas as pd

from app.core.allocation.dedupe import _normalize_national_code
from app.core.common.national_id import canonical_national_code
from app.core.qa.invariants import _canonicalize_national_code


def test_all_helpers_align_on_various_inputs() -> None:
    samples = [
        "0012345678",
        "12345678901",
        "۰۰۱۲۳۴۵۶۷۸۹۰",
        "abc",
        None,
        pd.NA,
    ]

    for sample in samples:
        shared = canonical_national_code(sample)
        assert _canonicalize_national_code(sample) == shared
        normalized = _normalize_national_code(sample)
        expected_normalized = shared or ""
        assert normalized == expected_normalized
