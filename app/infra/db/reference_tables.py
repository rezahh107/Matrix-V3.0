from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.infra.reference_repository import ReferenceRefreshMeta


@dataclass(frozen=True)
class ReferenceTableStatus:
    """خلاصهٔ وضعیت جدول مرجع برای نمایش در UI."""

    table_name: str
    row_count: int
    version_tag: str | None = None
    source_filename: str | None = None
    imported_at: datetime | None = None


def status_from_meta(table_name: str, meta: ReferenceRefreshMeta | None) -> ReferenceTableStatus:
    if meta is None:
        return ReferenceTableStatus(table_name=table_name, row_count=0)
    return ReferenceTableStatus(
        table_name=table_name,
        row_count=meta.row_count,
        version_tag=meta.version_tag,
        source_filename=meta.source_filename,
        imported_at=meta.imported_at,
    )


__all__ = ["ReferenceTableStatus", "status_from_meta"]
