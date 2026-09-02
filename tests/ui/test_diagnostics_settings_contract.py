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


def test_all_eight_guides_are_complete_in_fa_and_en() -> None:
    fa_sections = tuple(f"{letter}." for letter in "ABCDEFGHIJKLM")
    en_required = (
        "A. Basic understanding",
        "B. Concept explanation",
        "C. When should I use it?",
        "D. Behavioral impact",
        "E. What actually happens internally?",
        "F. Output and interpretation",
        "G. Practical example",
        "H. Limitations and what it does not prove",
        "I. Performance and storage",
        "J. Configuration",
        "K. Related tools",
        "L. Maintainer map",
        "M. Evidence honesty",
    )
    for capability in CAPABILITIES:
        fa = capability.guide_intro.fa
        en = capability.guide_intro.en
        assert all(section in fa for section in fa_sections)
        assert all(section in en for section in en_required)
        assert capability.setting_key in fa
        assert capability.setting_key in en
        assert "OFF / False" in fa
        assert "OFF / False" in en
        assert "~/.smart_alloc/user_settings.json" in fa
        assert "~/.smart_alloc/user_settings.json" in en
        assert "NOT MEASURED" in fa
        assert "NOT MEASURED" in en
        assert "DIRECTLY_CONFIRMED" in fa
        assert "DIRECTLY_CONFIRMED" in en
        assert len(fa) > 2200
        assert len(en) > 2200


def test_special_case_guidance_is_explicit() -> None:
    history = CAPABILITY_BY_KEY["enable_history_metrics"]
    assert "history-aware allocation" in history.guide_intro.en
    assert "history-aware allocation" in history.guide_intro.fa

    bucket_trace = CAPABILITY_BY_KEY["enable_bucket_trace"]
    assert "disabled_by_setting" in bucket_trace.guide_intro.en
    assert "disabled_by_setting" in bucket_trace.guide_intro.fa
    assert "Use Join Buckets" in bucket_trace.guide_intro.en

    qa = CAPABILITY_BY_KEY["enable_qa_pool_coverage_rules"]
    assert "QA_RULE_POOL_COVERAGE_01" in qa.guide_intro.en
    assert "PoolCoverageFailures" in qa.guide_intro.en
    assert "PoolDiversityReport" in qa.guide_intro.en
    assert "QaReport.passed" in qa.guide_intro.en

    join_buckets = CAPABILITY_BY_KEY["use_join_buckets"]
    assert "ADVANCED ALGORITHMIC / PERFORMANCE OPTION" in join_buckets.guide_intro.en
    assert "test_join_bucketing_flag_parity.py" in join_buckets.guide_intro.en
    assert "NOT_PROVEN" in join_buckets.guide_intro.en


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
    assert "M. صداقت شواهد" in fa.toPlainText()
    assert "M. Evidence honesty" in en.toPlainText()
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
