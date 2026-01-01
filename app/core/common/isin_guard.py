from __future__ import annotations

from collections.abc import KeysView
from typing import NoReturn

import numpy as np
import pandas as pd
from numpy.typing import NDArray


def _raise_isin_error(name: str, values: object) -> NoReturn:
    raise TypeError(
        "isin values for "
        f"{name} must be list-like; got {values!r} (type {type(values)!r}). "
        "Hint: wrap single value as [x] in policy."
    )


def require_isin_values(name: str, values: object) -> object:
    if values is None:
        _raise_isin_error(name, values)
    if isinstance(values, (str, bytes)):
        _raise_isin_error(name, values)
    if isinstance(values, dict):
        _raise_isin_error(name, values)
    if isinstance(values, np.ndarray):
        if values.ndim != 1:
            _raise_isin_error(name, values)
        return values
    if isinstance(values, (pd.Index, pd.Series, list, tuple, set, frozenset, range, KeysView)):
        return values
    _raise_isin_error(name, values)


def isin_mask(
    obj: pd.Series | pd.Index,
    values: object,
    *,
    name: str,
) -> pd.Series | NDArray[np.bool_]:
    return obj.isin(require_isin_values(name, values))
