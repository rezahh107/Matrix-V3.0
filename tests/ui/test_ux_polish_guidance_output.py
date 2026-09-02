from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolBar, QWidget

from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.preferences.settings_dialog import UnifiedSettingsDialog

ROOT = Path(__file__).resolve().parents[2]


def test_toolbar_exposes_global_support_not_duplicate_workflow_execution(qapp) -> None:
    window = MainWindow()
    toolbar = window.findChild(QToolBar, "mainToolbar")
    assert toolbar is not None
    visible_names = {action.objectName() for action in toolbar.actions() if action.isVisible()}

    assert "actionPresentationSettings" in visible_names
    assert "actionHistoryMetrics" in visible_names
    for key in ("build", "allocate", "mentor_pool", "rule_engine", "database"):
        action = window._toolbar_actions[key]
        assert action not in toolbar.actions()
    assert window._toolbar_actions["build"].shortcut().toString()
    assert window._toolbar_actions["allocate"].shortcut().toString()
    assert window._toolbar_actions["rule_engine"].shortcut().toString()
    window.close()


def test_one_settings_surface_reaches_both_persistence_authorities(qapp) -> None:
    window = MainWindow()
    dialog = UnifiedSettingsDialog(window._prefs, window._user_settings, window._translator, window)

    assert dialog.objectName() == "unifiedSettingsDialog"
    assert dialog.findChild(QWidget, "settingsLanguage") is not None
    assert dialog.findChild(QWidget, "settingsTheme") is not None
    assert dialog.findChild(QWidget, "settingsOutputRoot") is not None
    for key in (
        "enable_history_metrics",
        "enable_trace_debug_sheets",
        "enable_mentor_trace_debug",
        "enable_pool_governance_trace",
        "enable_bucket_trace",
        "enable_qa_pool_coverage_rules",
        "enable_trace_export",
        "use_join_buckets",
    ):
        assert dialog.findChild(QWidget, f"settings_{key}") is not None
    assert window._btn_settings.isHidden()
    dialog.close()
    window.close()


def test_database_references_are_presented_as_database_managed_rows(qapp) -> None:
    window = MainWindow()
    assert window.findChild(QWidget, "databaseReference_schools") is not None
    assert window.findChild(QWidget, "databaseReference_groupcodes") is not None
    assert window.findChild(QWidget, "openDatabase_schools") is not None
    assert window.findChild(QWidget, "openDatabase_groupcodes") is not None
    assert window._picker_schools.isHidden()
    assert window._picker_crosswalk.isHidden()
    window.close()


def test_primary_pages_have_visible_guidance_and_automatic_output_summary(qapp) -> None:
    window = MainWindow()
    for object_name in (
        "pageGuidance_pageBuildContent",
        "pageGuidance_pageAllocateContent",
        "pageGuidance_pageRuleEngineContent",
        "fieldHelp_build_inspactor",
        "fieldHelp_allocate_students",
        "fieldHelp_rule_matrix",
    ):
        label = window.findChild(QLabel, object_name)
        assert label is not None
        assert label.text().strip()
        assert label.property("guidanceLevel") in {"page", "field"}

    for run_type in ("build", "allocate", "rule-engine"):
        label = window.findChild(QLabel, f"outputWorkspaceSummary_{run_type}")
        assert label is not None
        assert window._prefs.output_root_dir in label.text()
    assert window._picker_output_matrix.isHidden()
    assert window._picker_alloc_out.isHidden()
    assert window._picker_rule_output.isHidden()
    window.close()


def test_language_refresh_keeps_guidance_bilingual_and_direction_safe(qapp) -> None:
    window = MainWindow()
    label = window.findChild(QLabel, "pageGuidance_pageBuildContent")
    assert label is not None

    window._apply_language(Language.FA)
    fa_text = label.text()
    assert window.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert "Inputs" not in " ".join(
        item.text() for item in window.findChildren(QLabel) if item.isVisible()
    )

    window._apply_language(Language.EN)
    en_text = label.text()
    assert window.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert fa_text != en_text
    assert "ماتریس اهلیت" not in en_text
    window.close()


def test_new_guidance_and_output_keys_exist_in_both_catalogues() -> None:
    payload = json.loads((ROOT / "resources/translations/ui_texts.json").read_text(encoding="utf-8"))
    keys = {
        "diagnostics.label",
        "action.open_database",
        "settings.state.on",
        "settings.state.off",
        "guidance.build.page",
        "guidance.build.inspactor",
        "guidance.build.policy",
        "guidance.allocate.page",
        "guidance.allocate.students",
        "guidance.allocate.pool",
        "guidance.rosters",
        "guidance.rule.page",
        "guidance.rule.matrix",
        "guidance.rule.students",
        "output.automatic",
        "output.root",
        "output.run_created",
        "output.saved_to",
    }
    assert keys <= set(payload["fa"])
    assert keys <= set(payload["en"])
    assert set(payload["fa"]) == set(payload["en"])


def test_combobox_authority_uses_vector_overlay_not_qss_border_triangle() -> None:
    qss = (ROOT / "app/ui/styles.qss").read_text(encoding="utf-8")
    source = (ROOT / "app/ui/widgets/combo_chevron.py").read_text(encoding="utf-8")
    assert "QComboBox::down-arrow" in qss
    assert "QComboBox::drop-down:right-to-left" in qss
    assert "border-top: 5px" not in qss
    assert "QPainter" in source
    assert "drawLine" in source


def test_c2_destination_ids_remain_closed(qapp) -> None:
    window = MainWindow()
    assert window.primary_surface_ids() == ("build", "allocate", "rule-engine")
    assert window.secondary_surface_ids() == ("explain", "database")
    window.close()
