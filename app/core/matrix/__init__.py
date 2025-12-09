"""ابزارهای دیباگ و گروهبندی ماتریس اهلیت."""

from .build_matrix_core import build_matrix_core
from .capacity_gates import evaluate_capacity
from .coverage import compute_group_coverage_debug
from .eligibility_rules import evaluate_eligibility
from .grouping import build_candidate_group_keys
from .matrix_schema import MatrixSchema

__all__ = [
    "build_matrix_core",
    "build_candidate_group_keys",
    "compute_group_coverage_debug",
    "evaluate_capacity",
    "evaluate_eligibility",
    "MatrixSchema",
]
