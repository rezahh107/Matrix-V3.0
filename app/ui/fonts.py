"""Matrix application font authority.

Production startup registers the embedded Vazirmatn bytes directly with Qt.  It
never needs to write into the application source/install directory and it does
not scan user Downloads folders.  Filesystem helpers remain only as explicit
compatibility/development seams.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from app.ui.assets.font_data_vazirmatn import (
    VAZIRMATN_REGULAR_BASE64,
    VAZIRMATN_REGULAR_TTF_BASE64,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

LOGGER = logging.getLogger(__name__)
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FALLBACK_FAMILY = "Tahoma"
DEFAULT_POINT_SIZE = 10
DEFAULT_WEIGHT = "normal"
DEBUG_LOG_ENV = "MATRIX_FONT_DEBUG_LOG"

_EMBEDDED_FAMILIES: tuple[str, ...] | None = None


def _embedded_font_bytes() -> bytes:
    """Decode the bundled Vazirmatn payload without touching the filesystem."""

    payload = VAZIRMATN_REGULAR_TTF_BASE64 or VAZIRMATN_REGULAR_BASE64
    if not payload:
        return b""
    try:
        return base64.b64decode(payload)
    except (ValueError, TypeError):
        LOGGER.exception("Unable to decode embedded Vazirmatn payload")
        return b""


def _register_embedded_vazirmatn() -> tuple[str, ...]:
    """Register the embedded font in Qt and cache the resolved family names."""

    global _EMBEDDED_FAMILIES
    if _EMBEDDED_FAMILIES is not None:
        return _EMBEDDED_FAMILIES

    data = _embedded_font_bytes()
    if not data:
        _EMBEDDED_FAMILIES = ()
        return _EMBEDDED_FAMILIES

    try:
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QFontDatabase

        font_id = QFontDatabase.addApplicationFontFromData(QByteArray(data))
        if font_id < 0:
            LOGGER.warning("Qt rejected the embedded Vazirmatn font data")
            _EMBEDDED_FAMILIES = ()
            return _EMBEDDED_FAMILIES
        families = tuple(QFontDatabase.applicationFontFamilies(font_id))
        _EMBEDDED_FAMILIES = families
        LOGGER.debug("Embedded Vazirmatn registered: %s", families)
        return families
    except Exception:
        LOGGER.exception("Unable to register embedded Vazirmatn with Qt")
        _EMBEDDED_FAMILIES = ()
        return _EMBEDDED_FAMILIES


def _materialize_embedded_font(target_dir: Path) -> Path | None:
    """Explicit development/test helper; production startup never calls this."""

    data = _embedded_font_bytes()
    if not data:
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "Vazirmatn-Regular.ttf"
    if not target.exists() or target.stat().st_size != len(data):
        target.write_bytes(data)
    return target


def ensure_vazir_local_fonts() -> Path:
    """Compatibility helper that only ensures the explicitly requested directory exists.

    It intentionally does not materialize the bundled font.  Call
    ``_materialize_embedded_font`` with an explicit writable directory when a
    development/test file is actually required.
    """

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    return FONTS_DIR


def _windows_candidates() -> list[Path]:
    """Return only explicitly opted-in development font paths.

    Normal startup does not inspect Downloads, LocalAppData or globally installed
    font directories.  ``VAZIR_FONT_PATHS`` is an explicit development fallback.
    """

    raw = os.environ.get("VAZIR_FONT_PATHS", "")
    return [Path(item).expanduser() for item in raw.split(os.pathsep) if item.strip()]


def _install_fonts_from_directory(directory: Path) -> list[str]:
    """Register existing TTF files from an explicitly supplied directory."""

    try:
        from PySide6.QtGui import QFontDatabase
    except Exception:
        return []

    families: list[str] = []
    if not directory.exists():
        return families
    for ttf in sorted(directory.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(ttf))
        if font_id < 0:
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def _load_vazir_font_family_names() -> list[str]:
    """Load Vazirmatn from the embedded payload, with explicit dev paths as fallback."""

    families = list(_register_embedded_vazirmatn())
    if not families and FONTS_DIR.exists():
        families.extend(_install_fonts_from_directory(FONTS_DIR))
    if not families:
        for candidate in _windows_candidates():
            directory = candidate if candidate.is_dir() else candidate.parent
            families.extend(_install_fonts_from_directory(directory))
    return [name for name in families if "vazir" in name.casefold() or "وزیر" in name]


def resolve_vazir_family_name(
    font_database: object | None = None,
    *,
    candidates: list[str] | tuple[str, ...] | None = None,
) -> str | None:
    """Resolve the first registered Vazir/Vazirmatn family name."""

    if candidates is None:
        try:
            from PySide6.QtGui import QFontDatabase

            database = font_database or QFontDatabase
            candidates = list(database.families())  # type: ignore[attr-defined]
        except Exception:
            candidates = []
    for family in candidates:
        normalized = str(family).casefold()
        if "vazirmatn" in normalized or normalized.startswith("vazir") or "وزیر" in family:
            return str(family)
    return None


def load_vazir_font(point_size: int | None = None) -> QFont | None:
    """Return the embedded Vazirmatn application font when Qt accepts it."""

    from PySide6.QtGui import QFont, QFontDatabase

    families = _load_vazir_font_family_names()
    family = resolve_vazir_family_name(QFontDatabase, candidates=families)
    if not family:
        return None
    return QFont(family, point_size or DEFAULT_POINT_SIZE)


def create_app_font(
    point_size: int | None = None,
    *,
    fallback_family: str | None = None,
    prefer_vazir: bool = True,
) -> QFont:
    """Create the semantic base font without introducing a second UI authority."""

    from PySide6.QtGui import QFont

    size = point_size or DEFAULT_POINT_SIZE
    vazir_font = load_vazir_font(size) if prefer_vazir else None
    if vazir_font is not None:
        vazir_font.setPointSize(size)
        vazir_font.setWeight(_resolve_weight())
        return _with_antialias(vazir_font)

    family = _select_fallback_family(fallback_family)
    fallback = QFont(family, size)
    fallback.setWeight(_resolve_weight())
    return _with_antialias(fallback)


def _select_fallback_family(preferred: str | None) -> str:
    candidates = [name for name in (preferred, "Segoe UI", FALLBACK_FAMILY, "Arial") if name]
    try:
        from PySide6.QtGui import QFontDatabase

        installed = set(QFontDatabase.families())
        for name in candidates:
            if name in installed:
                return str(name)
    except Exception:
        pass
    return str(candidates[0] if candidates else FALLBACK_FAMILY)


def get_app_font(point_size: int | None = None) -> QFont:
    return create_app_font(point_size=point_size)


def get_heading_font() -> QFont:
    from PySide6.QtGui import QFont

    heading = create_app_font(point_size=11)
    heading.setWeight(QFont.Weight.DemiBold)
    return heading


def collect_font_diagnostics() -> dict[str, object]:
    """Return deterministic diagnostics without probing arbitrary user directories."""

    return {
        "embedded_bytes": len(_embedded_font_bytes()),
        "embedded_families": list(_register_embedded_vazirmatn()),
        "explicit_dev_paths": [str(path) for path in _windows_candidates()],
        "fonts_dir": str(FONTS_DIR),
        "fonts_dir_exists": FONTS_DIR.exists(),
        "debug_log_env": os.environ.get(DEBUG_LOG_ENV, ""),
    }


def prepare_default_font(*, point_size: int | None = None) -> QFont:
    return create_app_font(point_size=point_size)


def apply_default_font(
    app: QApplication,
    *,
    point_size: int | None = None,
    family_override: str | None = None,
) -> QFont:
    """Compatibility API; the application bootstrap uses theme.apply_global_font."""

    font = create_app_font(point_size=point_size, fallback_family=family_override)
    app.setFont(font)
    return font


def _with_antialias(font: QFont) -> QFont:
    from PySide6.QtGui import QFont

    strategy = QFont.StyleStrategy(font.styleStrategy())
    strategy |= QFont.StyleStrategy.PreferAntialias
    strategy |= QFont.StyleStrategy.PreferQuality
    font.setStyleStrategy(strategy)
    if has_prefer_full_hinting():
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setKerning(True)
    return font


def has_prefer_full_hinting() -> bool:
    try:
        from PySide6.QtGui import QFont
    except Exception:
        return False
    return hasattr(QFont, "HintingPreference") and hasattr(
        QFont.HintingPreference, "PreferFullHinting"
    )


def _resolve_weight() -> QFont.Weight:
    from PySide6.QtGui import QFont

    mapping = {
        "normal": QFont.Weight.Normal,
        "regular": QFont.Weight.Normal,
        "medium": QFont.Weight.Medium,
        "demibold": QFont.Weight.DemiBold,
        "bold": QFont.Weight.Bold,
    }
    return mapping.get(DEFAULT_WEIGHT.lower(), QFont.Weight.Normal)
