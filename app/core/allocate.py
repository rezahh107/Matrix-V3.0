"""Output gateway for core allocation results."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from app.core.common.contracts import validate_allocation_output_contracts
from app.core.policy_loader import PolicyConfig

__all__ = ["AllocationBatchResultProtocol", "enforce_allocation_output_contracts"]


class AllocationBatchResultProtocol(Protocol):
    """Structural protocol for allocation batch outputs."""

    allocations_df: pd.DataFrame
    pool_output: pd.DataFrame
    logs_df: pd.DataFrame
    trace_df: pd.DataFrame


def enforce_allocation_output_contracts(
    result: AllocationBatchResultProtocol,
    *,
    pool_internal: pd.DataFrame,
    pool_with_ids: pd.DataFrame,
    policy: PolicyConfig,
) -> AllocationBatchResultProtocol:
    """Non-bypassable gateway that validates contracts before returning."""
    validate_allocation_output_contracts(
        allocations_df=result.allocations_df,
        pool_output=result.pool_output,
        logs_df=result.logs_df,
        trace_df=result.trace_df,
        pool_internal=pool_internal,
        pool_with_ids=pool_with_ids,
        policy=policy,
    )
    return result
