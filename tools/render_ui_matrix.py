"""Deterministic Matrix C2/V2 render-evidence harness (PySide6 only)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme, build_theme

THEMES = ("light", "dark")
LANGUAGES = (Language.FA, Language.EN)
# The contract anchors are 1200x800 and 960x640. The wide anchor is deliberate
# render evidence for the shared working column: over-wide field stretches and a
# CTA drifting to the window edge only become visible well past the anchors.
SIZES = ((1200, 800), (960, 640), (1680, 900))
SURFACE_IDS = ("build", "allocate", "explain", "database")


def _head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _configure_isolated_settings(path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(path))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(path))


def _rect(widget: QWidget | None) -> dict[str, int] | None:
    if widget is None:
        return None
    rect = widget.geometry()
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def _rect_record(rect: QRect) -> dict[str, int]:
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def _rect_in(widget: QWidget | None, ancestor: QWidget) -> QRect | None:
    if widget is None:
        return None
    point: QPoint = widget.mapTo(ancestor, widget.rect().topLeft())
    return QRect(point, widget.size())


def _contained(widget: QWidget | None, ancestor: QWidget) -> bool:
    rect = _rect_in(widget, ancestor)
    return bool(rect is not None and rect.width() > 0 and rect.height() > 0 and ancestor.rect().contains(rect))


def _current_viewport(window: MainWindow) -> QWidget | None:
    current = window._workspace_surfaces.get(window.current_surface_id() or "")
    if current is None:
        return None
    if isinstance(current, QScrollArea):
        return current.viewport()
    scroll = current.findChild(QScrollArea)
    return scroll.viewport() if scroll is not None else current


def _primary_cta(window: MainWindow, surface_id: str) -> QWidget | None:
    return {
        "build": window._btn_build,
        "allocate": window._btn_allocate,
    }.get(surface_id)


def _save_capture(window: MainWindow, image_path: Path, width: int, height: int) -> None:
    pixmap = window.grab()
    if pixmap.width() != width or pixmap.height() != height:
        raise AssertionError(
            f"capture dimension mismatch for {image_path.name}: "
            f"{pixmap.width()}x{pixmap.height()}"
        )
    if not pixmap.save(str(image_path), "PNG"):
        raise RuntimeError(f"unable to save {image_path}")
    if image_path.stat().st_size <= 0:
        raise AssertionError(f"empty render artifact: {image_path}")


def _surface_record(
    window: MainWindow,
    *,
    exact_head: str,
    theme_name: str,
    language: Language,
    width: int,
    height: int,
    surface_id: str,
    image_name: str,
) -> dict[str, object]:
    current = window.current_surface_id()
    if current != surface_id:
        raise AssertionError(f"surface activation mismatch: requested={surface_id} current={current}")
    surface = window._workspace_surfaces[surface_id]
    cta = _primary_cta(window, surface_id)
    viewport = _current_viewport(window)
    navigation = window._workspace_navigation
    toggle = window._diagnostics_toggle

    if navigation is None or toggle is None:
        raise AssertionError("C2 navigation/diagnostics controls are required")
    if not _contained(navigation, window) or not _contained(toggle, window):
        raise AssertionError(f"C2 shell control clipped on {surface_id}")
    if cta is not None and (not cta.isVisibleTo(surface) or not _contained(cta, surface)):
        raise AssertionError(f"primary CTA clipped on {surface_id}")
    if window.diagnostics_expanded():
        raise AssertionError("routine surface capture must keep diagnostics collapsed")

    return {
        "head": exact_head,
        "theme": theme_name,
        "language": language.code,
        "direction": (
            "rtl"
            if QApplication.instance().layoutDirection() == Qt.LayoutDirection.RightToLeft
            else "ltr"
        ),
        "window_size": [width, height],
        "surface_id": surface_id,
        "current_surface_id": current,
        "image": image_name,
        "navigation_geometry": _rect(navigation),
        "navigation_contained": _contained(navigation, window),
        "diagnostics_toggle_geometry": _rect(toggle),
        "diagnostics_toggle_contained": _contained(toggle, window),
        "diagnostics_expanded": window.diagnostics_expanded(),
        "primary_cta_visible": bool(cta is not None and cta.isVisibleTo(surface)),
        "primary_cta_geometry": _rect(cta),
        "primary_cta_contained": bool(cta is None or _contained(cta, surface)),
        "viewport_geometry": _rect(viewport),
        "surface_geometry": _rect(surface),
        "working_column": _working_column_record(window, surface_id, cta),
    }


def _working_column_record(
    window: MainWindow, surface_id: str, cta: QWidget | None
) -> dict[str, object] | None:
    """Record shared-working-column evidence for a primary workflow surface.

    A screenshot alone cannot falsify CTA detachment, so the manifest carries the
    content column, the footer column and the measured CTA drift from the
    column's own logical trailing edge.
    """

    content = window.findChild(QWidget, f"page{surface_id.capitalize()}Content")
    if content is None or cta is None or content.layout() is None:
        return None
    column = cta.parentWidget()
    if column is None or column.objectName() != "pageActionFooterColumn":
        raise AssertionError(f"primary CTA is outside the working column on {surface_id}")

    content_rect = _rect_in(content, window)
    column_rect = _rect_in(column, window)
    cta_rect = _rect_in(cta, window)
    margins = content.layout().contentsMargins()
    inner_left = content_rect.left() + margins.left()
    inner_right = content_rect.right() - margins.right()
    rtl = QApplication.instance().layoutDirection() == Qt.LayoutDirection.RightToLeft
    drift = abs(cta_rect.left() - inner_left) if rtl else abs(cta_rect.right() - inner_right)

    theme = window._theme
    tolerance = theme.scrollbar_thickness + theme.micro
    if drift > tolerance:
        raise AssertionError(
            f"primary CTA detached from the working column on {surface_id}: "
            f"drift={drift}px tolerance={tolerance}px"
        )
    if content.width() > theme.working_measure or column.width() > theme.working_measure:
        raise AssertionError(f"working column exceeds its measure on {surface_id}")

    return {
        "working_measure": theme.working_measure,
        "content_column_geometry": _rect_record(content_rect),
        "footer_column_geometry": _rect_record(column_rect),
        "cta_geometry": _rect_record(cta_rect),
        "cta_edge_drift_px": int(drift),
        "cta_edge_tolerance_px": int(tolerance),
        "logical_edge": "leading" if rtl else "trailing",
    }


def _diagnostics_evidence(
    window: MainWindow,
    app: QApplication,
    output_dir: Path,
    exact_head: str,
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    pane = window._diagnostics_pane
    toggle = window._diagnostics_toggle
    if pane is None or toggle is None:
        raise AssertionError("diagnostics controls unavailable")

    def record(case: str) -> None:
        image_name = f"diagnostics-{case}.png"
        image_path = output_dir / image_name
        _save_capture(window, image_path, window.width(), window.height())
        evidence.append(
            {
                "head": exact_head,
                "case": case,
                "image": image_name,
                "expanded": window.diagnostics_expanded(),
                "pane_hidden": pane.isHidden(),
                "pane_visible": pane.isVisibleTo(window),
                "toggle_checked": toggle.isChecked(),
                "pane_geometry": _rect(pane),
                "toggle_geometry": _rect(toggle),
            }
        )

    if window.diagnostics_expanded() or not pane.isHidden() or toggle.isChecked():
        raise AssertionError("diagnostics startup must be collapsed")
    record("startup-collapsed")

    window.set_diagnostics_expanded(True)
    app.processEvents()
    if not window.diagnostics_expanded() or not pane.isVisibleTo(window) or not toggle.isChecked():
        raise AssertionError("manual diagnostics expansion failed")
    record("manual-expanded")

    window.set_diagnostics_expanded(False)
    app.processEvents()
    window._show_async_message = lambda *_args, **_kwargs: None
    window._on_finished(False, RuntimeError("render-evidence-error"))
    app.processEvents()
    if not window.diagnostics_expanded() or not pane.isVisibleTo(window) or not toggle.isChecked():
        raise AssertionError("error path did not auto-reveal diagnostics")
    record("error-auto-reveal")
    return evidence


def render_matrix(output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("AllocationApp")
    app.setOrganizationName("MatrixRenderEvidence")
    exact_head = _head()
    captures: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="matrix-ui-settings-") as settings_dir:
        _configure_isolated_settings(Path(settings_dir))
        for theme_name in THEMES:
            for language in LANGUAGES:
                for width, height in SIZES:
                    QSettings().clear()
                    QSettings().sync()
                    window = MainWindow()
                    window._theme = build_theme(theme_name)
                    apply_theme(app, window._theme)
                    window._apply_theme_styles()
                    window._apply_language(language)
                    window.resize(width, height)
                    window.show()
                    app.processEvents()

                    if window.workspace_surface_ids() != SURFACE_IDS:
                        raise AssertionError(
                            f"surface registry changed: {window.workspace_surface_ids()}"
                        )
                    for surface_id in SURFACE_IDS:
                        if not window.activate_surface(surface_id):
                            raise AssertionError(f"surface not available: {surface_id}")
                        app.processEvents()
                        image_name = (
                            f"{theme_name}-{language.code}-{width}x{height}-{surface_id}.png"
                        )
                        image_path = output_dir / image_name
                        _save_capture(window, image_path, width, height)
                        captures.append(
                            _surface_record(
                                window,
                                exact_head=exact_head,
                                theme_name=theme_name,
                                language=language,
                                width=width,
                                height=height,
                                surface_id=surface_id,
                                image_name=image_name,
                            )
                        )
                    window.close()
                    window.deleteLater()
                    app.processEvents()

        expected_captures = len(THEMES) * len(LANGUAGES) * len(SIZES) * len(SURFACE_IDS)
        if len(captures) != expected_captures:
            raise AssertionError(
                f"expected {expected_captures} surface captures, got {len(captures)}"
            )

        QSettings().clear()
        QSettings().sync()
        diagnostic_window = MainWindow()
        diagnostic_window._apply_language(Language.EN)
        diagnostic_window.resize(1200, 800)
        diagnostic_window.show()
        app.processEvents()
        diagnostics = _diagnostics_evidence(
            diagnostic_window, app, output_dir, exact_head
        )
        diagnostic_window.close()
        diagnostic_window.deleteLater()
        app.processEvents()

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "head": exact_head,
                "surface_ids": list(SURFACE_IDS),
                "surface_capture_count": len(captures),
                "diagnostics_case_count": len(diagnostics),
                "captures": captures,
                "diagnostics_cases": diagnostics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return captures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/ui-render-matrix")
    )
    args = parser.parse_args()
    render_matrix(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())