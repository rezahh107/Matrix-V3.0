"""Bounded isolated-process High-DPI conformance harness for Matrix C2/V2."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCALES = (1.25, 1.5, 1.75, 2.0)
CASES = (
    ("fa", "build", "light", 960, 640),
    ("en", "database", "dark", 1200, 800),
)


def _rect(widget: Any) -> dict[str, int] | None:
    if widget is None:
        return None
    rect = widget.geometry()
    return {"x": rect.x(), "y": rect.y(), "width": rect.width(), "height": rect.height()}


def _visible_child(window: Any, cls: type[Any]) -> Any | None:
    for widget in window.findChildren(cls):
        if widget.isVisibleTo(window):
            return widget
    return None


def _child(args: argparse.Namespace) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication, QComboBox, QWidget

    from app.ui.i18n import Language
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme, build_theme
    from app.ui.widgets.file_picker import FilePicker

    settings_dir = Path(args.settings_dir)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(settings_dir))
    QSettings().clear()

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("MatrixDpiEvidence")
    app.setOrganizationName("MatrixDpiEvidence")
    window = MainWindow()
    theme = build_theme(args.theme)
    window._theme = theme
    apply_theme(app, theme)
    window._apply_theme_styles()
    language = Language.FA if args.language == "fa" else Language.EN
    window._apply_language(language)
    window.resize(args.width, args.height)
    window.show()
    app.processEvents()
    if not window.activate_surface(args.surface):
        raise AssertionError(f"surface not available: {args.surface}")
    app.processEvents()

    combo = _visible_child(window, QComboBox)
    picker = _visible_child(window, FilePicker)
    if args.surface == "build" and (combo is None or picker is None):
        raise AssertionError("build DPI case must expose both QComboBox and FilePicker")

    target_widgets: dict[str, QWidget | None] = {
        "navigation": window._workspace_navigation,
        "combo": combo,
        "file_picker": picker,
        "diagnostics_toggle": window._diagnostics_toggle,
        "primary_cta": window._btn_build if args.surface == "build" else None,
    }
    critical: dict[str, object] = {}
    for name, widget in target_widgets.items():
        critical[name] = {
            "visible": bool(widget is not None and widget.isVisibleTo(window)),
            "geometry": _rect(widget),
        }

    record = {
        "scale_factor": float(args.scale),
        "logical_window_size": [window.width(), window.height()],
        "device_pixel_ratio": float(window.devicePixelRatioF()),
        "language": args.language,
        "direction": "rtl"
        if app.layoutDirection() == Qt.LayoutDirection.RightToLeft
        else "ltr",
        "surface": args.surface,
        "theme": args.theme,
        "diagnostics_expanded": window.diagnostics_expanded(),
        "critical_widgets": critical,
    }
    Path(args.output).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    window.close()
    app.processEvents()
    return 0


def _parent(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="matrix-dpi-settings-") as settings_dir:
        for scale in SCALES:
            for language, surface, theme, width, height in CASES:
                output = output_dir / f"dpi-{scale}-{language}-{surface}.json"
                env = os.environ.copy()
                env["QT_QPA_PLATFORM"] = "offscreen"
                env["QT_SCALE_FACTOR"] = str(scale)
                env["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
                command = [
                    sys.executable,
                    str(script),
                    "--child",
                    "--scale",
                    str(scale),
                    "--language",
                    language,
                    "--surface",
                    surface,
                    "--theme",
                    theme,
                    "--width",
                    str(width),
                    "--height",
                    str(height),
                    "--settings-dir",
                    settings_dir,
                    "--output",
                    str(output),
                ]
                subprocess.run(command, env=env, check=True)
                record = json.loads(output.read_text(encoding="utf-8"))
                if record["logical_window_size"] != [width, height]:
                    raise AssertionError(f"logical size changed at scale {scale}: {record}")
                if float(record["device_pixel_ratio"]) <= 0:
                    raise AssertionError(f"invalid DPR at scale {scale}: {record}")
                if bool(record["diagnostics_expanded"]):
                    raise AssertionError("routine DPI case must start with diagnostics collapsed")
                records.append(record)

    expected = len(SCALES) * len(CASES)
    if len(records) != expected:
        raise AssertionError(f"expected {expected} DPI records, got {len(records)}")
    manifest = {"scales": list(SCALES), "case_count": len(records), "cases": records}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ui-dpi"))
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--language", default="fa")
    parser.add_argument("--surface", default="build")
    parser.add_argument("--theme", default="light")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--settings-dir", default=".")
    parser.add_argument("--output", type=Path, default=Path("dpi.json"))
    args = parser.parse_args()
    return _child(args) if args.child else _parent(args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
