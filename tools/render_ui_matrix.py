"""Deterministic Matrix UI render-evidence harness (PySide6 only)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme, build_theme

THEMES = ("light", "dark")
LANGUAGES = (Language.FA, Language.EN)
SIZES = ((1200, 800), (960, 640))
TABS = (
    (0, "build"),
    (1, "allocate"),
    (2, "rule-engine"),
    (3, "explain"),
    (4, "database"),
)


def _rect(widget: QWidget | None) -> dict[str, int] | None:
    if widget is None:
        return None
    rect = widget.geometry()
    return {"x": rect.x(), "y": rect.y(), "width": rect.width(), "height": rect.height()}


def _head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _configure_isolated_settings(path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(path))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(path))


def render_matrix(output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("AllocationApp")
    app.setOrganizationName("MatrixRenderEvidence")
    exact_head = _head()
    manifest: list[dict[str, object]] = []

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

                    for index, tab_name in TABS:
                        window._tabs.setCurrentIndex(index)
                        app.processEvents()
                        image_name = f"{theme_name}-{language.code}-{width}x{height}-{tab_name}.png"
                        image_path = output_dir / image_name
                        pixmap = window.grab()
                        if pixmap.width() != width or pixmap.height() != height:
                            raise AssertionError(
                                f"capture dimension mismatch for {image_name}: "
                                f"{pixmap.width()}x{pixmap.height()}"
                            )
                        if not pixmap.save(str(image_path), "PNG"):
                            raise RuntimeError(f"unable to save {image_path}")
                        if image_path.stat().st_size <= 0:
                            raise AssertionError(f"empty render artifact: {image_path}")

                        current = window._tabs.currentWidget()
                        viewport = None
                        if isinstance(current, QScrollArea):
                            viewport = current.viewport()
                        elif current is not None:
                            scroll = current.findChild(QScrollArea)
                            viewport = scroll.viewport() if scroll is not None else current

                        cta = None
                        if tab_name == "build":
                            cta = window._btn_build
                        elif tab_name == "allocate":
                            cta = window._btn_allocate
                        elif tab_name == "rule-engine":
                            cta = window._btn_rule_engine

                        manifest.append(
                            {
                                "head": exact_head,
                                "theme": theme_name,
                                "language": language.code,
                                "direction": "rtl"
                                if app.layoutDirection() == Qt.LayoutDirection.RightToLeft
                                else "ltr",
                                "window_size": [width, height],
                                "tab": tab_name,
                                "image": image_name,
                                "primary_cta_visible": bool(cta is not None and cta.isVisibleTo(window)),
                                "primary_cta_geometry": _rect(cta),
                                "splitter_sizes": window._splitter.sizes(),
                                "splitter_geometry": _rect(window._splitter),
                                "viewport_geometry": _rect(viewport),
                            }
                        )
                    window.close()
                    window.deleteLater()
                    app.processEvents()

    if len(manifest) != 40:
        raise AssertionError(f"expected 40 captures, got {len(manifest)}")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"head": exact_head, "captures": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ui-render-matrix"))
    args = parser.parse_args()
    render_matrix(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
