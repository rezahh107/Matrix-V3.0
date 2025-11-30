from __future__ import annotations

import pandas as pd

from app.core.common.phone_rules import normalize_digits

__all__ = ["canonical_national_code"]


def canonical_national_code(value: object) -> str | None:
    """Return a canonical 10-digit national code or ``None``.

    The function keeps only numeric characters (supporting Unicode digits via
    :func:`normalize_digits`), takes the last ten digits, and zero-fills to ensure
    a fixed length. Inputs with no digits (including ``None``/``NaN``) return
    ``None``.
    """

    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        # Objects without ``isna`` support (e.g., custom classes) should fall back
        # to digit extraction.
        pass

    digits_only = normalize_digits(value)
    if digits_only is None:
        return None

    trimmed = digits_only[-10:]
    return trimmed.zfill(10)
