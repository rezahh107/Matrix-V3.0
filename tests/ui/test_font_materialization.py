"""Tests for in-memory Vazirmatn loading and explicit development materialization."""

from __future__ import annotations

import os

import pytest

pytest.importorskip(
    "PySide6.QtGui",
    exc_type=ImportError,
    reason="PySide6 not available in test environment",
)

from PySide6.QtGui import QFont

from app.ui import fonts


def test_ensure_vazir_local_fonts_does_not_materialize_production_font(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fonts_dir = tmp_path / "fonts"
    monkeypatch.setattr(fonts, "FONTS_DIR", fonts_dir)

    result = fonts.ensure_vazir_local_fonts()

    assert result == fonts_dir
    assert fonts_dir.is_dir()
    assert list(fonts_dir.glob("*.ttf")) == []


def test_explicit_embedded_font_materialization_is_idempotent(tmp_path) -> None:
    fonts_dir = tmp_path / "development-fonts"

    first = fonts._materialize_embedded_font(fonts_dir)
    second = fonts._materialize_embedded_font(fonts_dir)

    assert first is not None
    assert second == first
    assert first.name == "Vazirmatn-Regular.ttf"
    assert first.stat().st_size > 0
    assert list(fonts_dir.glob("*.ttf")) == [first]


def test_embedded_vazirmatn_registers_in_memory_without_disk_write(
    qapp, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fonts_dir = tmp_path / "empty-fonts"
    fonts_dir.mkdir()
    monkeypatch.setattr(fonts, "FONTS_DIR", fonts_dir)
    monkeypatch.setattr(fonts, "_EMBEDDED_FAMILIES", None)

    families = fonts._register_embedded_vazirmatn()

    assert families
    assert any("vazir" in family.casefold() or "وزیر" in family for family in families)
    assert list(fonts_dir.iterdir()) == []
    assert qapp is not None


def test_windows_candidates_use_only_explicit_development_paths(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VAZIR_FONT_PATHS", raising=False)
    assert fonts._windows_candidates() == []

    first = tmp_path / "one"
    second = tmp_path / "two"
    monkeypatch.setenv("VAZIR_FONT_PATHS", os.pathsep.join((str(first), str(second))))
    assert fonts._windows_candidates() == [first, second]


def test_create_app_font_defaults_to_antialias_and_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: None)

    font = fonts.create_app_font()

    assert font.pointSize() == fonts.DEFAULT_POINT_SIZE
    assert font.styleStrategy() & QFont.StyleStrategy.PreferAntialias
    assert font.styleStrategy() & QFont.StyleStrategy.PreferQuality
    if hasattr(QFont, "HintingPreference") and hasattr(
        QFont.HintingPreference, "PreferFullHinting"
    ):
        assert font.hintingPreference() == QFont.HintingPreference.PreferFullHinting
