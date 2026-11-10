"""Year-scoped local Roster metadata, never an official or student-data store."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

from app.ui.helpers.academic_year import counter_accepts_year

_VERSION = 1
_MAX_PATH_LENGTH = 4096
_SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")


def reference_key(academic_year: int) -> str:
    if type(academic_year) is not int or not counter_accepts_year(academic_year):
        raise ValueError("Invalid Allocate academic-year context")
    return f"allocation/prior_roster/v1/{academic_year}"


@dataclass(frozen=True)
class PriorRosterReference:
    """A local file identity; not Roster semantic validation or official freshness."""

    version: int
    academic_year: int
    path: str
    size: int
    mtime_ns: int
    sha256: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> PriorRosterReference:
        data = json.loads(raw)
        fields = {"version", "academic_year", "path", "size", "mtime_ns", "sha256"}
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError("Malformed prior Roster descriptor")
        if type(data["version"]) is not int or data["version"] != _VERSION:
            raise ValueError("Unsupported prior Roster descriptor version")
        reference_key(data["academic_year"])
        path = data["path"]
        if (
            not isinstance(path, str)
            or not path
            or len(path) > _MAX_PATH_LENGTH
            or not Path(path).is_absolute()
        ):
            raise ValueError("Invalid prior Roster path")
        for name in ("size", "mtime_ns"):
            if type(data[name]) is not int or data[name] < 0:
                raise ValueError(f"Invalid prior Roster {name}")
        digest = data["sha256"]
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise ValueError("Invalid prior Roster digest")
        return cls(**data)


def capture_prior_roster(academic_year: int, raw_path: str) -> PriorRosterReference:
    """Stream a stable local regular file without parsing or retaining rows."""
    reference_key(academic_year)
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("Prior Roster path must be nonempty")
    path = Path(raw_path.strip()).expanduser()
    if not path.is_absolute():
        raise ValueError("Prior Roster path must be absolute")
    path = path.resolve(strict=True)
    if len(str(path)) > _MAX_PATH_LENGTH:
        raise ValueError("Prior Roster path too long")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Prior Roster reference is not a regular file")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    pathname_stat = path.stat()
    def identity(s: os.stat_result) -> tuple[int, int, int, int]:
        return s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino
    if identity(before) != identity(after) or identity(after) != identity(pathname_stat):
        raise OSError("Prior Roster changed during fingerprint capture")
    return PriorRosterReference(
        _VERSION, academic_year, str(path), after.st_size, after.st_mtime_ns, digest.hexdigest()
    )


def probe_prior_roster(reference: PriorRosterReference) -> str:
    """Return unchanged/changed/missing/inaccessible, without reading Roster rows."""
    try:
        current = capture_prior_roster(reference.academic_year, reference.path)
    except FileNotFoundError:
        return "missing"
    except (PermissionError, OSError):
        return "inaccessible"
    except ValueError:
        return "changed"
    return "unchanged" if current == reference else "changed"
