"""Windows Qt offscreen evidence for the database-health locale change.

Uses real isolated SQLite health outcomes, not invented severity or allocation runs.
Images are full-resolution Qt captures; the contact sheet is only an index.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import PySide6
from PySide6.QtCore import QEvent, QRect, QSettings, Qt, qVersion
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.infra.local_database import DatabaseHealthReason, DatabaseHealthStatus, LocalDatabase
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme, build_theme

_THEMES = ("light", "dark")
_LANGUAGES = (Language.EN, Language.FA)
_SIZES = ((1200, 800), (960, 640))
_SCENARIOS = ("ready", "warning", "missing-file", "connection-error")
_EXPECTED = {
    "ready": (DatabaseHealthStatus.OK, DatabaseHealthReason.READY, "ok"),
    "warning": (DatabaseHealthStatus.DEGRADED, DatabaseHealthReason.NEEDS_REVIEW, "warning"),
    "missing-file": (DatabaseHealthStatus.UNAVAILABLE, DatabaseHealthReason.MISSING_FILE, "error"),
    "connection-error": (
        DatabaseHealthStatus.UNAVAILABLE, DatabaseHealthReason.CONNECTION_ERROR, "error"
    ),
}
_PERSIAN = re.compile(r"[\u0600-\u06ff]")


def _summaries(base: Path):
    result = {}
    for case in _SCENARIOS:
        db_path = base / (case + ".sqlite")
        if case == "ready":
            LocalDatabase(db_path).initialize()
        elif case == "warning":
            sqlite3.connect(db_path).close()
        elif case == "connection-error":
            db_path.write_bytes(b"invalid SQLite database")
        result[case] = LocalDatabase(db_path).get_database_health_summary()
        expected_status, expected_reason, _ = _EXPECTED[case]
        assert result[case].status is expected_status
        assert result[case].reason is expected_reason
    return result


def _make_contact_sheet(out: Path, cases: list[dict[str, object]]) -> None:
    columns = 4
    thumb_width, thumb_height = 600, 400
    label_height = 34
    rows = (len(cases) + columns - 1) // columns
    sheet = QImage(
        columns * thumb_width, rows * (thumb_height + label_height),
        QImage.Format.Format_RGB32
    )
    sheet.fill(QColor("#e3e6e8"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Segoe UI", 10))
    painter.setPen(QColor("#202327"))
    for i, entry in enumerate(cases):
        image = QImage(str(out / str(entry["image"])))
        if image.isNull():
            raise AssertionError(f"unreadable full-resolution image: {entry['image']}")
        x = (i % columns) * thumb_width
        y = (i // columns) * (thumb_height + label_height)
        painter.drawImage(QRect(x, y, thumb_width, thumb_height), image)
        painter.drawText(
            QRect(x + 8, y + thumb_height, thumb_width - 16, label_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(entry["name"]),
        )
    painter.end()
    if not sheet.save(str(out / "contact-sheet.png"), "PNG"):
        raise RuntimeError("contact sheet save failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("MatrixDatabaseLocaleEvidence")
    app.setApplicationName("MatrixDatabaseLocaleEvidence")
    results: list[dict[str, object]] = []
    clipping: list[str] = []
    with tempfile.TemporaryDirectory() as temp:
        settings_dir = Path(temp) / "settings"
        settings_dir.mkdir()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
            QSettings.setPath(QSettings.Format.IniFormat, scope, str(settings_dir))
        summaries = _summaries(Path(temp))
        for theme in _THEMES:
            for language in _LANGUAGES:
                for width, height in _SIZES:
                    QSettings().clear()
                    window = MainWindow()
                    try:
                        window._theme = build_theme(theme)
                        apply_theme(app, window._theme)
                        window._apply_theme_styles()
                        window._apply_language(language)
                        window.resize(width, height)
                        window.show()
                        window.activate_surface("allocate")
                        app.processEvents()
                        for scenario in _SCENARIOS:
                            summary = summaries[scenario]
                            widget = window._database_status
                            if widget is None:
                                raise AssertionError("database status widget not installed")
                            # Underlying health was generated by an isolated SQLite file.
                            # Only presentation input is injected into the live C2 shell.
                            widget.set_summary(summary)
                            app.processEvents()
                            status = widget._text_label.text()
                            tooltip = widget.toolTip()
                            a11y = widget.accessibleDescription()
                            expected_status, expected_reason, severity = _EXPECTED[scenario]
                            assert summary.status is expected_status
                            assert summary.reason is expected_reason
                            assert widget._icon_label.property("databaseHealth") == severity
                            assert widget._text_label.property("databaseHealth") == severity
                            assert status and a11y and tooltip.startswith(a11y)
                            if language is Language.EN:
                                assert not any(_PERSIAN.search(value) for value in (
                                    status, tooltip, a11y, widget.accessibleName()
                                )), "Persian UI-owned copy under English"
                            label = widget._text_label
                            fm = QFontMetrics(label.font())
                            text_width = fm.horizontalAdvance(status)
                            label_width = label.width()
                            if not widget.isVisibleTo(window) or text_width > label_width:
                                clipping.append(
                                    f"{theme}/{language.code}/{width}x{height}/{scenario}: "
                                    f"{status!r} required={text_width} available={label_width}"
                                )
                            stem = f"db-{theme}-{language.code}-{width}x{height}-{scenario}"
                            capture = out / (stem + ".png")
                            pix = window.grab()
                            if not pix.save(str(capture), "PNG") or not capture.stat().st_size:
                                raise RuntimeError(f"failed to write {capture}")
                            results.append({
                                "name": stem,
                                "image": capture.name,
                                "language": language.code,
                                "theme": theme,
                                "size_logical": [width, height],
                                "image_pixels": [pix.width(), pix.height()],
                                "device_pixel_ratio": pix.devicePixelRatio(),
                                "screen_dpr": window.devicePixelRatioF(),
                                "status": summary.status.value,
                                "reason": summary.reason.value,
                                "severity_qss_property": severity,
                                "status_text": status,
                                "tooltip": tooltip,
                                "accessible_name": widget.accessibleName(),
                                "accessible_description": a11y,
                                "text_width_px": text_width,
                                "label_width_px": label_width,
                                "font": label.font().family(),
                                "visible": widget.isVisibleTo(window),
                                "layout_direction": "rtl" if widget.layoutDirection() == Qt.LayoutDirection.RightToLeft else "ltr",
                            })
                    finally:
                        window.close()
                        window.deleteLater()
                        app.processEvents()
                        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                        app.processEvents()
    assert len(results) == 32
    _make_contact_sheet(out, results)
    manifest = {
        "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "capture_mode": "Windows Qt offscreen (not native desktop acceptance)",
        "os": platform.platform(),
        "python": platform.python_version(),
        "qt_version": qVersion(),
        "pyside6_version": PySide6.__version__,
        "qpa_platform": os.environ.get("QT_QPA_PLATFORM", ""),
        "style": app.style().objectName(),
        "application_font": app.font().family(),
        "screen_dpr": app.primaryScreen().devicePixelRatio() if app.primaryScreen() else None,
        "capture_count": len(results),
        "clipping_observations": clipping,
        "scenario_basis": "isolated actual SQLite health summaries; not production database",
        "cases": results,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Recorded {len(results)} full-size PNGs, contact sheet, and manifest")
    if clipping:
        raise AssertionError("Clipped status labels: " + "; ".join(clipping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
