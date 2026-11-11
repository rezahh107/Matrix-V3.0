from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime

from app.infra.local_database import LocalDatabase, _table_exists
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


def observed_reference_status(*, db: LocalDatabase, table_name: str) -> ReferenceTableStatus:
    """Observe actual rows and existing provenance without creating or repairing DB.

    Metadata can be trusted for provenance only when its stored row count
    matches the actual reference table count. Missing metadata is not a
    reason to synthesize a built-in or imported source.
    """
    if table_name not in {"schools", "groupcodes"}:
        raise ValueError(f"Unsupported reference table: {table_name}")
    if not db.path.exists():
        return ReferenceTableStatus(table_name=table_name, row_count=0)

    with closing(db.connect_readonly()) as conn:
        if not _table_exists(conn, table_name):
            return ReferenceTableStatus(table_name=table_name, row_count=0)
        row_count = int(conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])
        meta = None
        if _table_exists(conn, "reference_meta"):
            meta = conn.execute(
                "SELECT row_count, version_tag, source_filename, imported_at "
                "FROM reference_meta WHERE table_name = ?",
                (table_name,),
            ).fetchone()

    if meta is None or meta[0] is None or int(meta[0]) != row_count:
        return ReferenceTableStatus(table_name=table_name, row_count=row_count)

    imported_at = (
        datetime.fromisoformat(str(meta[3]).replace("Z", "+00:00"))
        if meta[3]
        else None
    )
    return ReferenceTableStatus(
        table_name=table_name,
        row_count=row_count,
        version_tag=meta[1],
        source_filename=meta[2],
        imported_at=imported_at,
    )


__all__ = ["ReferenceTableStatus", "status_from_meta", "observed_reference_status"]
