from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTabWidget, QTextBrowser, QWidget

from app.infra.config_flags import UserSettings
from app.ui.app_preferences import AppPreferences
from app.ui.preferences.diagnostics_catalog import CAPABILITIES, CAPABILITY_BY_KEY
from app.ui.preferences.settings_dialog import DiagnosticsGuideDialog, UnifiedSettingsDialog
from app.ui.texts import UiTranslator

EXPECTED_KEYS = (
    "enable_trace_debug_sheets",
    "enable_mentor_trace_debug",
    "enable_pool_governance_trace",
    "enable_bucket_trace",
    "enable_trace_export",
    "enable_history_metrics",
    "enable_qa_pool_coverage_rules",
    "use_join_buckets",
)


def test_catalog_preserves_all_eight_capabilities_and_semantic_groups() -> None:
    assert tuple(item.setting_key for item in CAPABILITIES) == EXPECTED_KEYS
    assert len(CAPABILITY_BY_KEY) == 8
    grouped = {item.setting_key: item.category for item in CAPABILITIES}
    assert grouped["enable_history_metrics"] == "analysis"
    for key in EXPECTED_KEYS[:5]:
        assert grouped[key] == "diagnostics"
    assert grouped["enable_qa_pool_coverage_rules"] == "advanced"
    assert grouped["use_join_buckets"] == "advanced"


def test_each_capability_has_description_impact_and_full_guide(qapp) -> None:
    prefs = AppPreferences()
    dialog = UnifiedSettingsDialog(prefs, UserSettings(), UiTranslator("en"))

    for key in EXPECTED_KEYS:
        assert dialog.findChild(QWidget, f"settings_{key}") is not None
        description = dialog.findChild(QLabel, f"diagnosticDescription_{key}")
        impact = dialog.findChild(QLabel, f"diagnosticImpact_{key}")
        guide = dialog.findChild(QPushButton, f"diagnosticGuide_{key}")
        assert description is not None and description.text().strip()
        assert impact is not None and impact.text().strip()
        assert guide is not None and guide.text() == "Full Guide / راهنمای کامل"

    assert dialog.findChild(QWidget, "diagnosticsCategory_diagnostics") is not None
    assert dialog.findChild(QWidget, "diagnosticsCategory_analysis") is not None
    assert dialog.findChild(QWidget, "diagnosticsCategory_advanced") is not None
    dialog.close()


def test_critical_impacts_are_visible_and_not_diagnostic_only(qapp) -> None:
    prefs = AppPreferences()
    dialog = UnifiedSettingsDialog(prefs, UserSettings(), UiTranslator("en"))

    qa = dialog.findChild(QLabel, "diagnosticImpact_enable_qa_pool_coverage_rules")
    buckets = dialog.findChild(QLabel, "diagnosticImpact_use_join_buckets")
    assert qa is not None and "MAY AFFECT VALIDATION PASS/FAIL" in qa.text()
    assert qa.property("impactKind") == "validation"
    assert buckets is not None and "ALGORITHMIC / PERFORMANCE" in buckets.text()
    assert buckets.property("impactKind") == "algorithmic"
    dialog.close()


def test_guide_reader_exposes_both_languages_with_independent_direction(qapp) -> None:
    guide = DiagnosticsGuideDialog(CAPABILITY_BY_KEY["enable_qa_pool_coverage_rules"])
    tabs = guide.findChild(QTabWidget, "diagnosticsGuideLanguages")
    fa = guide.findChild(QTextBrowser, "diagnosticsGuideFa")
    en = guide.findChild(QTextBrowser, "diagnosticsGuideEn")
    assert tabs is not None and tabs.count() == 2
    assert tabs.tabText(0) == "فارسی"
    assert tabs.tabText(1) == "English"
    assert fa is not None and fa.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert en is not None and en.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert fa.toPlainText().strip()
    assert en.toPlainText().strip()
    guide.close()


def test_settings_roundtrip_keeps_existing_user_settings_contract(qapp) -> None:
    prefs = AppPreferences()
    original = UserSettings(
        enable_history_metrics=True,
        enable_trace_debug_sheets=False,
        enable_trace_export=True,
        enable_mentor_trace_debug=True,
        enable_bucket_trace=False,
        enable_pool_governance_trace=True,
        enable_qa_pool_coverage_rules=False,
        use_join_buckets=True,
    )
    dialog = UnifiedSettingsDialog(prefs, original, UiTranslator("fa"))
    assert dialog.result_user_settings == original
    dialog.close()
