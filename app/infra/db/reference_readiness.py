from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.infra.db.reference_tables import ReferenceTableStatus

if TYPE_CHECKING:
    from app.infra.groupcode.groupcode_repository import GroupCodeRepository
    from app.infra.schools.school_repository import SchoolRepository

__all__ = [
    "ReferenceReadiness",
    "compute_reference_readiness",
]


@dataclass(frozen=True)
class ReferenceReadiness:
    """Aggregated readiness flags for DB-backed reference data."""

    schools: ReferenceTableStatus
    groupcodes: ReferenceTableStatus

    @property
    def schools_ready(self) -> bool:
        return self.schools.row_count > 0

    @property
    def groupcodes_ready(self) -> bool:
        return self.groupcodes.row_count > 0

    @property
    def is_ready_for_run(self) -> bool:
        return self.schools_ready and self.groupcodes_ready


def compute_reference_readiness(
    *, school_repo: SchoolRepository, groupcode_repo: GroupCodeRepository
) -> ReferenceReadiness:
    """Compute reference readiness without mutating any state."""

    school_status = school_repo.status()
    groupcode_status = groupcode_repo.status()
    return ReferenceReadiness(schools=school_status, groupcodes=groupcode_status)
