"""Unified user-facing Settings dialog over the two existing persistence authorities."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.infra.config_flags import UserSettings
from app.ui.app_preferences import AppPreferences
from app.ui.i18n import Language
from app.ui.run_output import default_output_root
from app.ui.texts import UiTranslator
from app.ui.widgets.combo_chevron import install_combo_chevrons


class UnifiedSettingsDialog(QDialog):
    """One first-class Settings surface; storage remains intentionally split."""

    def __init__(
        self,
        preferences: AppPreferences,
        user_settings: UserSettings,
        translator: UiTranslator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = preferences
        self._translator = translator
        self.setObjectName("unifiedSettingsDialog")
        self.setWindowTitle(self._t("settings.title", "Settings"))
        self.setMinimumWidth(560)
        self.setMaximumWidth(760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        general = QGroupBox(self._t("ribbon.preferences", "Preferences"), self)
        general_form = QFormLayout(general)
        self._language = QComboBox(general)
        self._language.setObjectName("settingsLanguage")
        self._language.addItem(self._t("language.fa", "Persian"), Language.FA)
        self._language.addItem(self._t("language.en", "English"), Language.EN)
        language_index = self._language.findData(preferences.language)
        if language_index >= 0:
            self._language.setCurrentIndex(language_index)
        self._theme = QComboBox(general)
        self._theme.setObjectName("settingsTheme")
        self._theme.addItem(self._t("theme.light", "Light"), "light")
        self._theme.addItem(self._t("theme.dark", "Dark"), "dark")
        theme_index = self._theme.findData(preferences.theme)
        if theme_index >= 0:
            self._theme.setCurrentIndex(theme_index)
        general_form.addRow(self._t("dialog.language.label", "Language"), self._language)
        general_form.addRow(self._t("theme.label", "Theme"), self._theme)
        layout.addWidget(general)

        output = QGroupBox(self._t("group.output", "Output"), self)
        output_form = QFormLayout(output)
        root_row = QWidget(output)
        root_layout = QHBoxLayout(root_row)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)
        self._output_root = QLineEdit(preferences.output_root_dir, root_row)
        self._output_root.setObjectName("settingsOutputRoot")
        self._output_root.setReadOnly(True)
        choose = QPushButton(self._t("action.browse", "Browse…"), root_row)
        choose.setObjectName("settingsChooseOutputRoot")
        choose.clicked.connect(self._choose_output_root)
        root_layout.addWidget(self._output_root, 1)
        root_layout.addWidget(choose)
        output_form.addRow(self._t("files.output_folder", "Output folder"), root_row)

        output_actions = QWidget(output)
        output_actions_layout = QHBoxLayout(output_actions)
        output_actions_layout.setContentsMargins(0, 0, 0, 0)
        reset = QPushButton(self._t("action.reset_default", "Reset to default"), output_actions)
        reset.setObjectName("settingsResetOutputRoot")
        reset.clicked.connect(lambda: self._output_root.setText(str(default_output_root())))
        self._open_last = QPushButton(self._t("action.open_output", "Open output folder"), output_actions)
        self._open_last.setObjectName("settingsOpenLastRun")
        self._open_last.setEnabled(bool(preferences.last_output_dir))
        output_actions_layout.addWidget(reset)
        output_actions_layout.addWidget(self._open_last)
        output_actions_layout.addStretch(1)
        output_form.addRow(output_actions)
        layout.addWidget(output)

        advanced = QGroupBox(self._t("group.advanced", "Advanced settings"), self)
        advanced_layout = QVBoxLayout(advanced)
        self._checks: dict[str, QCheckBox] = {}
        check_specs = (
            ("enable_history_metrics", "settings.history_metrics", "History Metrics"),
            ("enable_trace_debug_sheets", "settings.trace_debug_sheets", "Trace Debug Sheets"),
            ("enable_mentor_trace_debug", "settings.mentor_trace", "Mentor Pipeline Trace"),
            ("enable_pool_governance_trace", "settings.pool_trace", "Pool Governance Trace"),
            ("enable_bucket_trace", "settings.bucket_trace", "Bucket Trace"),
            ("enable_qa_pool_coverage_rules", "settings.qa_coverage", "QA Pool Coverage Rules"),
            ("enable_trace_export", "settings.trace_export", "Trace Sheet Export"),
            ("use_join_buckets", "settings.join_buckets", "Use Join Buckets"),
        )
        values = user_settings.to_dict()
        for attribute, key, fallback in check_specs:
            checkbox = QCheckBox(self._t(key, fallback), advanced)
            checkbox.setObjectName(f"settings_{attribute}")
            checkbox.setChecked(bool(values.get(attribute, False)))
            advanced_layout.addWidget(checkbox)
            self._checks[attribute] = checkbox
        layout.addWidget(advanced)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        install_combo_chevrons(self)

    def _choose_output_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._t("files.output_folder", "Output folder"),
            self._output_root.text(),
        )
        if selected:
            self._output_root.setText(str(Path(selected)))

    def connect_open_last_run(self, callback) -> None:
        self._open_last.clicked.connect(callback)

    @property
    def selected_language(self) -> Language:
        value = self._language.currentData()
        return value if isinstance(value, Language) else Language.from_code(str(value))

    @property
    def selected_theme(self) -> str:
        return str(self._theme.currentData())

    @property
    def selected_output_root(self) -> str:
        return self._output_root.text().strip()

    @property
    def result_user_settings(self) -> UserSettings:
        values = {key: checkbox.isChecked() for key, checkbox in self._checks.items()}
        return UserSettings(**values)

    def _t(self, key: str, fallback: str) -> str:
        return self._translator.text(key, fallback)
