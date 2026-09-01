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
    ("fa", "allocate", "light", 960, 640),
    ("en", "build", "dark", 1200, 800),
)
_SCALE_TOLERANCE = 0.06


def _head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _rect(widget: Any) -> dict[str, int] | None:
    if widget is None:
        return None
    rect = widget.geometry()
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def _mapped_rect(widget: Any, ancestor: Any) -> Any:
    from PySide6.QtCore import QRect

    return QRect(widget.mapTo(ancestor, widget.rect().topLeft()), widget.size())


def _contained(widget: Any, ancestor: Any) -> bool:
    if widget is None or ancestor is None:
        return False
    rect = _mapped_rect(widget, ancestor)
    return bool(
        rect.width() > 0
        and rect.height() > 0
        and ancestor.rect().contains(rect)
    )


def _visible_descendant(root: Any, cls: type[Any]) -> Any | None:
    for widget in root.findChildren(cls):
        if widget.isVisibleTo(root):
            return widget
    return None


def _critical_record(widget: Any, container: Any) -> dict[str, object]:
    return {
        "visible": bool(widget is not None and widget.isVisibleTo(container)),
        "geometry": _rect(widget),
        "container_geometry": _rect(container),
        "contained": _contained(widget, container),
    }


def _assert_no_nav_overlap(window: Any) -> None:
    navigation = window._workspace_navigation
    if navigation is None:
        raise AssertionError("workspace navigation missing")
    buttons = [
        button
        for button in window._workspace_nav_buttons.values()
        if button.isVisibleTo(navigation)
    ]
    for button in buttons:
        if not _contained(button, navigation):
            raise AssertionError(f"navigation button clipped: {button.objectName()}")
    rects = [_mapped_rect(button, navigation) for button in buttons]
    for index, rect in enumerate(rects):
        for other in rects[index + 1 :]:
            if rect.intersects(other):
                raise AssertionError("workspace navigation buttons overlap")


def _child(args: argparse.Namespace) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication, QComboBox

    from app.ui.i18n import Language
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme, build_theme
    from app.ui.widgets.file_picker import FilePicker

    settings_dir = Path(args.settings_dir)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir)
    )
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(settings_dir)
    )
    QSettings().clear()
    QSettings().sync()

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
    if window.current_surface_id() != args.surface:
        raise AssertionError("surface identity mismatch")

    surface = window._workspace_surfaces[args.surface]
    combo = _visible_descendant(surface, QComboBox)
    if combo is None:
        combo = window._theme_selector
    picker = _visible_descendant(surface, FilePicker)
    navigation = window._workspace_navigation
    diagnostics_toggle = window._diagnostics_toggle
    cta = {
        "build": window._btn_build,
        "allocate": window._btn_allocate,
        "rule-engine": window._btn_rule_engine,
    }.get(args.surface)

    if navigation is None or diagnostics_toggle is None:
        raise AssertionError("C2 shell controls unavailable")
    if combo is None or picker is None or cta is None:
        raise AssertionError(
            f"DPI workflow case must expose ComboBox, FilePicker and CTA: {args.surface}"
        )
    if window.diagnostics_expanded():
        raise AssertionError("routine DPI case must start with diagnostics collapsed")
    if window._diagnostics_pane is None or not window._diagnostics_pane.isHidden():
        raise AssertionError("diagnostics pane is not explicitly hidden")

    _assert_no_nav_overlap(window)

    status_bar = window._status_bar
    if status_bar is None:
        raise AssertionError("status bar missing")
    critical = {
        "navigation": _critical_record(navigation, window),
        "combo": _critical_record(combo, surface if surface.isAncestorOf(combo) else window),
        "file_picker": _critical_record(picker, surface),
        "diagnostics_toggle": _critical_record(diagnostics_toggle, status_bar),
        "primary_cta": _critical_record(cta, surface),
    }
    failures = [
        name
        for name, record in critical.items()
        if not bool(record["visible"])
        or not bool(record["contained"])
        or not record["geometry"]
        or int(record["geometry"]["width"]) <= 0
        or int(record["geometry"]["height"]) <= 0
    ]
    if failures:
        raise AssertionError(f"critical DPI controls unusable: {failures}")

    screen = window.screen() or app.primaryScreen()
    window_dpr = float(window.devicePixelRatioF())
    screen_dpr = float(screen.devicePixelRatio()) if screen is not None else None
    logical_dpi = float(screen.logicalDotsPerInch()) if screen is not None else None
    logical_dpi_scale = logical_dpi / 96.0 if logical_dpi is not None else None
    requested_scale = float(args.scale)
    observed_candidates = [window_dpr]
    if screen_dpr is not None:
        observed_candidates.append(screen_dpr)
    scale_demonstrated = any(
        abs(observed - requested_scale) <= _SCALE_TOLERANCE
        for observed in observed_candidates
    )
    if not scale_demonstrated:
        raise AssertionError(
            "requested scale not demonstrated: "
            f"requested={requested_scale} window_dpr={window_dpr} "
            f"screen_dpr={screen_dpr} logical_dpi_scale={logical_dpi_scale}"
        )

    record = {
        "head": _head(),
        "requested_scale": requested_scale,
        "scale_demonstrated": scale_demonstrated,
        "observed_window_dpr": window_dpr,
        "observed_screen_dpr": screen_dpr,
        "observed_logical_dpi": logical_dpi,
        "observed_logical_dpi_scale": logical_dpi_scale,
        "logical_window_size": [window.width(), window.height()],
        "window_geometry": _rect(window),
        "language": args.language,
        "direction": (
            "rtl"
            if app.layoutDirection() == Qt.LayoutDirection.RightToLeft
            else "ltr"
        ),
        "surface_id": args.surface,
        "theme": args.theme,
        "diagnostics_expanded": window.diagnostics_expanded(),
        "critical_widgets": critical,
        "clipping_or_containment_failures": failures,
    }
    Path(args.output).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    window.close()
    app.processEvents()
    return 0


def _parent(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    exact_head = _head()
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
                if record["head"] != exact_head:
                    raise AssertionError(f"DPI evidence Head mismatch: {record}")
                if record["logical_window_size"] != [width, height]:
                    raise AssertionError(f"logical size changed at scale {scale}: {record}")
                if not bool(record["scale_demonstrated"]):
                    raise AssertionError(f"scale not demonstrated: {record}")
                if bool(record["diagnostics_expanded"]):
                    raise AssertionError(
                        "routine DPI case must start with diagnostics collapsed"
                    )
                if record["clipping_or_containment_failures"]:
                    raise AssertionError(f"DPI containment failure: {record}")
                records.append(record)

    expected = len(SCALES) * len(CASES)
    if len(records) != expected:
        raise AssertionError(f"expected {expected} DPI records, got {len(records)}")
    manifest = {
        "head": exact_head,
        "requested_scales": list(SCALES),
        "case_count": len(records),
        "cases": records,
    }
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
    parser.add_argument("--surface", default="allocate")
    parser.add_argument("--theme", default="light")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--settings-dir", default=".")
    parser.add_argument("--output", type=Path, default=Path("dpi.json"))
    args = parser.parse_args()
    return _child(args) if args.child else _parent(args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
