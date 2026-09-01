"""Integration tests for C2/V2 theme, direction and application-font authority."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip(
    "PySide6.QtWidgets",
    exc_type=ImportError,
    reason="PySide6 not available in test environment",
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QLabel

from app.ui import fonts, theme
from app.ui.fonts import create_app_font, resolve_vazir_family_name
from app.ui.i18n import Language
from app.ui.log_panel import LogPanel
from app.ui.texts import UiTranslator
from app.ui.widgets.database_status_widget import DatabaseStatusWidget
from app.ui.widgets.status_bar import ThemedStatusBar

ROOT = Path(__file__).resolve().parents[2]


def _is_vazir_family(family: str) -> bool:
    normalized = family.casefold()
    return "vazirmatn" in normalized or normalized.startswith("vazir") or "وزیر" in family


def test_create_app_font_generic_fallback_does_not_define_en_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: None)
    monkeypatch.setattr(fonts, "_select_fallback_family", lambda preferred: "Segoe UI")
    font = create_app_font(fallback_family="Segoe UI", prefer_vazir=False)
    assert font.family().casefold().startswith("segoe ui")


def test_create_app_font_prefers_vazir_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = QFont("Vazir", 11)
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: fake)
    font = create_app_font(prefer_vazir=True)
    assert font.family().casefold().startswith("vazir")


def test_create_app_font_sets_regular_weight_for_vazir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = QFont("Vazir", 11)
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: fake)
    font = create_app_font(prefer_vazir=True)
    assert font.weight() == QFont.Weight.Normal


def test_create_app_font_sets_regular_weight_for_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: None)
    monkeypatch.setattr(fonts, "_select_fallback_family", lambda preferred: "Segoe UI")
    font = create_app_font(fallback_family="Segoe UI", prefer_vazir=False)
    assert font.weight() == QFont.Weight.Normal


def test_resolve_vazir_family_uses_first_registered_vazir_candidate() -> None:
    class _FakeDB:
        def __init__(self, families: list[str]):
            self._families = families

        def families(self) -> list[str]:
            return self._families

    db = _FakeDB(["Tahoma", "Vazir", "Vazirmatn", "Vazir Code"])
    family = resolve_vazir_family_name(db)
    assert family == "Vazir"


def test_apply_global_font_uses_fa_embedded_authority(qapp: QApplication) -> None:
    original_font = QFont(qapp.font())
    original_direction = qapp.layoutDirection()
    try:
        qapp.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        theme.apply_global_font(qapp)
        app_font = qapp.font()
        assert _is_vazir_family(app_font.family())
        assert app_font.pointSize() == theme.BASE_FONT_PT
        assert app_font.weight() == QFont.Weight.Normal
        assert app_font.styleStrategy() & QFont.StyleStrategy.PreferAntialias
        assert app_font.styleStrategy() & QFont.StyleStrategy.PreferQuality
        hint_pref = getattr(QFont.HintingPreference, "PreferFullHinting", None)
        if hint_pref is not None:
            assert app_font.hintingPreference() == hint_pref
    finally:
        qapp.setLayoutDirection(original_direction)
        qapp.setFont(original_font)


def test_fa_en_fa_updates_existing_widgets_without_reconstruction(
    qapp: QApplication,
) -> None:
    original_font = QFont(qapp.font())
    original_direction = qapp.layoutDirection()
    current_theme = theme.build_theme("light")

    status = ThemedStatusBar(current_theme)
    database = DatabaseStatusWidget(current_theme)
    log = LogPanel(UiTranslator("fa"), current_theme)
    legacy_label = QLabel("legacy neutral compatibility seam")
    legacy_label.setFont(fonts.get_app_font())
    representative = (
        status,
        database,
        database._icon_label,
        database._text_label,
        log,
        log._placeholder,
        log.text_edit,
        legacy_label,
    )

    try:
        expected_families: list[str] = []
        for language in (Language.FA, Language.EN, Language.FA):
            theme.apply_layout_direction(qapp, language)
            qapp.processEvents()
            app_family = qapp.font().family()
            expected_families.append(app_family)

            if language is Language.FA:
                assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
                assert _is_vazir_family(app_family)
            else:
                assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
                assert app_family.casefold().startswith("segoe ui")

            for widget in representative:
                assert widget.font().family() == app_family

        assert _is_vazir_family(expected_families[0])
        assert expected_families[1].casefold().startswith("segoe ui")
        assert _is_vazir_family(expected_families[2])
    finally:
        for widget in representative:
            widget.close()
        qapp.setLayoutDirection(original_direction)
        qapp.setFont(original_font)
        qapp.processEvents()


def test_runtime_family_rebind_preserves_semantic_font_properties(
    qapp: QApplication,
) -> None:
    original_font = QFont(qapp.font())
    original_direction = qapp.layoutDirection()
    label: QLabel | None = None

    try:
        theme.apply_layout_direction(qapp, Language.EN)
        label = QLabel("semantic existing widget")
        semantic_font = QFont(label.font())
        semantic_font.setPointSize(theme.BASE_FONT_PT + 3)
        semantic_font.setWeight(QFont.Weight.DemiBold)
        semantic_font.setItalic(True)
        label.setFont(semantic_font)

        widget_identity = id(label)
        point_size = label.font().pointSize()
        weight = label.font().weight()
        italic = label.font().italic()

        theme.apply_layout_direction(qapp, Language.FA)
        qapp.processEvents()
        assert id(label) == widget_identity
        assert label.font().family() == qapp.font().family()
        assert _is_vazir_family(label.font().family())
        assert label.font().pointSize() == point_size
        assert label.font().weight() == weight
        assert label.font().italic() == italic

        theme.apply_layout_direction(qapp, Language.EN)
        qapp.processEvents()
        assert id(label) == widget_identity
        assert label.font().family() == qapp.font().family()
        assert label.font().family().casefold().startswith("segoe ui")
        assert label.font().pointSize() == point_size
        assert label.font().weight() == weight
        assert label.font().italic() == italic
    finally:
        if label is not None:
            label.close()
        qapp.setLayoutDirection(original_direction)
        qapp.setFont(original_font)
        qapp.processEvents()


def test_font_consumer_inventory_has_no_independent_base_family_owners() -> None:
    production_files = sorted((ROOT / "app/ui").rglob("*.py"))
    get_app_font_consumers: list[str] = []
    forbidden_direct_family_assignments: list[str] = []

    for path in production_files:
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        if path.name != "fonts.py" and "get_app_font" in source:
            get_app_font_consumers.append(relative)
        if path.name not in {"fonts.py", "theme.py"}:
            for family in ("Vazir", "Vazirmatn", "Tahoma", "Segoe UI"):
                if f'QFont("{family}"' in source or f"QFont('{family}'" in source:
                    forbidden_direct_family_assignments.append(f"{relative}:{family}")

    # The preserved execution base retains two compatibility calls. Family
    # propagation is now enforced centrally from the QApplication widget inventory.
    assert get_app_font_consumers == ["app/ui/main_window_base.py"]
    base_source = (ROOT / "app/ui/main_window_base.py").read_text(encoding="utf-8")
    assert base_source.count("setFont(get_app_font())") == 2
    fonts_source = (ROOT / "app/ui/fonts.py").read_text(encoding="utf-8")
    assert "if point_size is None:\n        return QFont()" in fonts_source
    theme_source = (ROOT / "app/ui/theme.py").read_text(encoding="utf-8")
    assert "QApplication.allWidgets()" in theme_source
    assert "captured_font.family().casefold() != previous_key" in theme_source
    assert "rebound = QFont(captured_font)" in theme_source
    assert "rebound.setFamily(target_family)" in theme_source
    assert forbidden_direct_family_assignments == []


def test_vazir_font_pipeline_document_matches_current_authority() -> None:
    document = (ROOT / "docs/vazir-font-pipeline.md").read_text(encoding="utf-8")
    required_markers = (
        "docs/UI_DESIGN_CONTRACT.md",
        "QFontDatabase.addApplicationFontFromData()",
        "QApplication.allWidgets()",
        "setFamily()",
        "captured QFont",
        "FA / RTL",
        "EN / LTR",
        "Segoe UI",
        "10pt",
        "_materialize_embedded_font(target_dir)",
        "VAZIR_FONT_PATHS",
        "production startup برای این کار **هیچ TTFای داخل source/install directory نمی‌نویسد**",
        "production مسیرهای `Downloads` یا `LocalAppData` را به‌طور خودکار scan یا copy نمی‌کند",
    )
    assert all(marker in document for marker in required_markers)
    assert "Matrix2" not in document
    assert "ensure_vazir_local_fonts()` پوشهٔ `app/ui/fonts/` را می‌سازد، اگر TTFی" not in document
    assert "به‌تنهایی تضمین نمی‌کند" in document


def test_widgets_created_without_local_font_inherit_application_font(
    qapp: QApplication,
) -> None:
    original_font = QFont(qapp.font())
    try:
        theme.apply_layout_direction(qapp, Language.EN)
        label = QLabel("sample")
        assert label.font().family() == qapp.font().family()
        assert label.font().pointSize() == theme.BASE_FONT_PT
        assert label.font().weight() == QFont.Weight.Normal
        label.close()
    finally:
        qapp.setFont(original_font)


def test_layout_direction_for_languages(qapp: QApplication) -> None:
    original_font = QFont(qapp.font())
    original_direction = qapp.layoutDirection()
    try:
        theme.apply_layout_direction(qapp, Language.FA)
        assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert _is_vazir_family(qapp.font().family())
        theme.apply_layout_direction(qapp, Language.EN)
        assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
        assert qapp.font().family().casefold().startswith("segoe ui")
    finally:
        qapp.setLayoutDirection(original_direction)
        qapp.setFont(original_font)


def test_light_theme_log_background_is_light() -> None:
    light_theme = theme.build_theme("light")
    dark_theme = theme.build_theme("dark")
    light_luminance = QColor(light_theme.colors.log_background).lightness()
    dark_luminance = QColor(dark_theme.colors.log_background).lightness()
    assert light_luminance > 210
    assert dark_luminance < 80
    assert dark_luminance < light_luminance


def test_heading_font_preserves_active_family_and_adds_semantic_emphasis(
    qapp: QApplication,
) -> None:
    original_font = QFont(qapp.font())
    original_direction = qapp.layoutDirection()
    try:
        theme.apply_layout_direction(qapp, Language.EN)
        body_font = QFont(qapp.font())
        heading_font = fonts.get_heading_font()
        assert heading_font.family() == body_font.family()
        assert heading_font.pointSize() > body_font.pointSize()
        assert heading_font.weight() > body_font.weight()
    finally:
        qapp.setLayoutDirection(original_direction)
        qapp.setFont(original_font)