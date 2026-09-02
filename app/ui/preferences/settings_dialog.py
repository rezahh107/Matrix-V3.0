"""Unified user-facing Settings dialog over the two existing persistence authorities."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.infra.config_flags import UserSettings
from app.ui.app_preferences import AppPreferences
from app.ui.i18n import Language
from app.ui.run_output import default_output_root
from app.ui.texts import UiTranslator
from app.ui.widgets.combo_chevron import install_combo_chevrons

from .diagnostics_catalog import (
    CAPABILITIES,
    CAPABILITY_BY_KEY,
    CATEGORY_ORDER,
    CATEGORY_TITLES,
    CapabilityPresentation,
    LocalizedText,
)


class DiagnosticsGuideDialog(QDialog):
    """Bilingual reader for one retained diagnostic/advanced capability."""

    def __init__(
        self,
        capability: CapabilityPresentation,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"diagnosticsGuideDialog_{capability.setting_key}")
        self.setWindowTitle(f"{capability.title.fa} | {capability.title.en}")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        warning = QLabel(f"{capability.impact.fa}\n{capability.impact.en}", self)
        warning.setObjectName(f"diagnosticsGuideImpact_{capability.setting_key}")
        warning.setProperty("impactKind", capability.impact_kind)
        warning.setWordWrap(True)
        warning.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(warning)

        tabs = QTabWidget(self)
        tabs.setObjectName("diagnosticsGuideLanguages")
        fa_reader = self._reader(
            capability.guide_intro.fa,
            Qt.LayoutDirection.RightToLeft,
            "diagnosticsGuideFa",
        )
        en_reader = self._reader(
            capability.guide_intro.en,
            Qt.LayoutDirection.LeftToRight,
            "diagnosticsGuideEn",
        )
        tabs.addTab(fa_reader, "فارسی")
        tabs.addTab(en_reader, "English")
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _reader(text: str, direction: Qt.LayoutDirection, object_name: str) -> QTextBrowser:
        reader = QTextBrowser()
        reader.setObjectName(object_name)
        reader.setLayoutDirection(direction)
        reader.setOpenExternalLinks(False)
        reader.setPlainText(text)
        return reader


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
        self._guide_dialog: DiagnosticsGuideDialog | None = None
        self.setObjectName("unifiedSettingsDialog")
        self.setWindowTitle(self._t("settings.title", "Settings"))
        self.resize(720, 760)
        self.setMinimumSize(620, 560)
        self.setMaximumWidth(860)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        scroll = QScrollArea(self)
        scroll.setObjectName("settingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        body.setObjectName("settingsScrollBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 2, 4, 2)
        body_layout.setSpacing(16)

        general = QGroupBox(self._t("ribbon.preferences", "Preferences"), body)
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
        body_layout.addWidget(general)

        output = QGroupBox(self._t("group.output", "Output"), body)
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
        self._open_last = QPushButton(
            self._t("action.open_output", "Open output folder"), output_actions
        )
        self._open_last.setObjectName("settingsOpenLastRun")
        self._open_last.setEnabled(bool(preferences.last_output_dir))
        output_actions_layout.addWidget(reset)
        output_actions_layout.addWidget(self._open_last)
        output_actions_layout.addStretch(1)
        output_form.addRow(output_actions)
        body_layout.addWidget(output)

        diagnostics = QGroupBox(
            self._localized(
                LocalizedText("ابزارهای خطایابی و پیشرفته", "Diagnostics & Advanced Tools")
            ),
            body,
        )
        diagnostics.setObjectName("diagnosticsAdvancedTools")
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.setSpacing(14)
        self._checks: dict[str, QCheckBox] = {}
        values = user_settings.to_dict()

        for category_id in CATEGORY_ORDER:
            category = QGroupBox(
                self._localized(CATEGORY_TITLES[category_id]), diagnostics
            )
            category.setObjectName(f"diagnosticsCategory_{category_id}")
            category_layout = QVBoxLayout(category)
            category_layout.setSpacing(10)
            for capability in CAPABILITIES:
                if capability.category == category_id:
                    category_layout.addWidget(
                        self._capability_row(capability, values, category)
                    )
            diagnostics_layout.addWidget(category)
        body_layout.addWidget(diagnostics)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        install_combo_chevrons(self)

    def _capability_row(
        self,
        capability: CapabilityPresentation,
        values: dict[str, object],
        parent: QWidget,
    ) -> QWidget:
        row = QWidget(parent)
        row.setObjectName(f"diagnosticCapability_{capability.setting_key}")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 6)
        layout.setSpacing(5)

        header = QWidget(row)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        checkbox = QCheckBox(self._localized(capability.title), header)
        checkbox.setObjectName(f"settings_{capability.setting_key}")
        checkbox.setChecked(bool(values.get(capability.setting_key, False)))
        self._checks[capability.setting_key] = checkbox
        guide = QPushButton("Full Guide / راهنمای کامل", header)
        guide.setObjectName(f"diagnosticGuide_{capability.setting_key}")
        guide.setProperty("variant", "secondary")
        guide.clicked.connect(
            lambda _checked=False, item=capability: self._open_capability_guide(item)
        )
        header_layout.addWidget(checkbox, 1)
        header_layout.addWidget(guide, 0)
        layout.addWidget(header)

        description = QLabel(self._localized(capability.summary), row)
        description.setObjectName(f"diagnosticDescription_{capability.setting_key}")
        description.setWordWrap(True)
        description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(description)

        impact = QLabel(self._localized(capability.impact), row)
        impact.setObjectName(f"diagnosticImpact_{capability.setting_key}")
        impact.setProperty("impactKind", capability.impact_kind)
        impact.setWordWrap(True)
        impact.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(impact)
        return row

    def _open_capability_guide(self, capability: CapabilityPresentation) -> None:
        dialog = DiagnosticsGuideDialog(capability, self)
        self._guide_dialog = dialog
        dialog.exec()

    def _localized(self, text: LocalizedText) -> str:
        return text.for_language(str(self._translator.language))

    def _choose_output_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._t("files.output_folder", "Output folder"),
            self._output_root.text(),
        )
        if selected:
            self._output_root.setText(str(Path(selected)))

    def connect_open_last_run(self, callback: Callable[[], None]) -> None:
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


__all__ = [
    "CAPABILITIES",
    "CAPABILITY_BY_KEY",
    "DiagnosticsGuideDialog",
    "UnifiedSettingsDialog",
]
