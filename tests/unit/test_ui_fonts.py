"""Unit tests for the C2/V2 application-font compatibility helpers."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "PySide6.QtWidgets",
    exc_type=ImportError,
    reason="PySide6 GUI stack requires the Qt runtime",
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.ui import fonts
from app.ui.fonts import create_app_font


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_ensure_vazir_local_fonts_creates_only_explicit_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fonts, "FONTS_DIR", tmp_path)
    result = fonts.ensure_vazir_local_fonts()
    assert result == tmp_path
    assert fonts.FONTS_DIR.exists()
    assert list(fonts.FONTS_DIR.glob("*.ttf")) == []


def test_create_app_font_generic_fallback_is_not_language_authority(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: None)
    monkeypatch.setattr(fonts, "_select_fallback_family", lambda preferred: "Segoe UI")

    font = create_app_font(
        fallback_family="Segoe UI",
        prefer_vazir=False,
    )

    assert font.family().casefold().startswith("segoe ui")
    assert font.pointSize() == fonts.DEFAULT_POINT_SIZE
    assert font.weight() == QFont.Weight.Normal


def test_get_app_font_semantic_size_preserves_active_application_family(
    qapp: QApplication,
) -> None:
    original = QFont(qapp.font())
    try:
        qapp.setFont(QFont("Segoe UI", fonts.DEFAULT_POINT_SIZE))
        font = fonts.get_app_font(point_size=12)
        assert font.family() == qapp.font().family()
        assert font.pointSize() == 12
    finally:
        qapp.setFont(original)
