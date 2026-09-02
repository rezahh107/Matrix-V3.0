"""C2 workspace composition over the preserved Matrix execution/presentation base.

This module changes only presentation ownership and composition. Runtime/domain
slots remain implemented by ``main_window_base`` through the preserved prior
presentation layer in ``main_window_presentation_base``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QByteArray, QEvent, QObject, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from app.infra.config_flags import save_user_settings

from . import main_window_presentation_base as _v1
from .preferences.settings_dialog import UnifiedSettingsDialog
from .run_output import RunOutputWorkspace, create_run_workspace
from .widgets.combo_chevron import install_combo_chevrons
from .widgets.file_picker import FilePicker

UnknownsPreflightResult = _v1.UnknownsPreflightResult
AccentSplitter = _v1.AccentSplitter
get_cached_policy = _v1.get_cached_policy
load_policy = _v1.load_policy

_DIAGNOSTICS_STATE_KEY: Final[str] = "ui/main_splitter_v2"
_COMPACT_WORKSPACE_WIDTH: Final[int] = 1000
_MAX_WORKING_MEASURE: Final[int] = 1280
# Geometry-specific exception: enough width for translated row utility commands
# without forcing the file picker column to jump between rows.
_ROW_UTILITY_WIDTH: Final[int] = 124


@dataclass(frozen=True)
class _WorkspaceDestinationSpec:
    surface_id: str
    primary: bool
    text_key: str
    fallback: str
    marker_object_name: str | None = None


_DESTINATION_SPECS: Final[tuple[_WorkspaceDestinationSpec, ...]] = (
    _WorkspaceDestinationSpec("build", True, "tabs.build", "Build Matrix", "pageBuild"),
    _WorkspaceDestinationSpec("allocate", True, "tabs.allocate", "Allocate", "pageAllocate"),
    _WorkspaceDestinationSpec(
        "rule-engine", True, "tabs.rule_engine", "Rule Engine", "pageRuleEngine"
    ),
    _WorkspaceDestinationSpec("explain", False, "tabs.explain", "Explain", "pageExplain"),
    _WorkspaceDestinationSpec("database", False, "tabs.database", "Database"),
)


class MainWindow(_v1.MainWindow):
    """C2 primary-workspace shell with V2 presentation behavior."""

    def __init__(self) -> None:
        self._workspace_surfaces: dict[str, QWidget] = {}
        self._workspace_nav_buttons: dict[str, QToolButton] = {}
        self._workspace_specs: dict[str, _WorkspaceDestinationSpec] = {}
        self._workspace_navigation: QFrame | None = None
        self._diagnostics_pane: QWidget | None = None
        self._diagnostics_toggle: QToolButton | None = None
        self._diagnostics_expanded = False
        self._support_toolbar_actions: dict[str, QAction] = {}
        self._polish_text_labels: dict[str, QLabel] = {}
        self._output_summary_labels: dict[str, QLabel] = {}
        self._active_run_workspace: RunOutputWorkspace | None = None
        self._auto_output_paths: dict[str, str] = {}
        super().__init__()
        self._splitter.installEventFilter(self)
        # The prior presentation layer used a delayed 25% default. C2 always
        # starts collapsed, so any pending legacy callback becomes a no-op.
        self._default_splitter_ratio_pending = False
        self._install_workspace_navigation()
        self._install_compact_operational_status()
        self._install_contextual_diagnostics()
        self._install_product_polish_surfaces()
        self._remove_decorative_motion()
        self._apply_adaptive_workspace_geometry()
        self._refresh_settings_indicators()
        self._refresh_support_action_texts()
        self._refresh_output_summaries()
        install_combo_chevrons(self)

    # ------------------------------------------------------------ C2 surfaces
    def _resolve_tab_container(self, marker: QWidget) -> QWidget | None:
        for index in range(self._tabs.count()):
            page = self._tabs.widget(index)
            if page is not None and (marker is page or page.isAncestorOf(marker)):
                return page
        return None

    def _discover_workspace_surfaces(self) -> dict[str, QWidget]:
        discovered: dict[str, QWidget] = {}
        for spec in _DESTINATION_SPECS:
            container: QWidget | None = None
            if spec.surface_id == "database":
                container = self._database_tab_container
            elif spec.marker_object_name:
                marker = self.findChild(QWidget, spec.marker_object_name)
                if marker is not None:
                    container = self._resolve_tab_container(marker)
            if container is not None and self._tabs.indexOf(container) >= 0:
                discovered[spec.surface_id] = container
        return discovered

    def _install_workspace_navigation(self) -> None:
        self._workspace_surfaces = self._discover_workspace_surfaces()
        self._workspace_specs = {
            spec.surface_id: spec
            for spec in _DESTINATION_SPECS
            if spec.surface_id in self._workspace_surfaces
        }
        self._tabs.setObjectName("workspaceStack")
        self._tabs.tabBar().hide()

        host = QFrame(self)
        host.setObjectName("workspaceNavigation")
        nav = QHBoxLayout(host)
        nav.setContentsMargins(
            self._theme.page_margin_normal,
            self._theme.micro,
            self._theme.page_margin_normal,
            self._theme.micro,
        )
        nav.setSpacing(self._theme.micro)

        for spec in self._workspace_specs.values():
            if not spec.primary:
                continue
            nav.addWidget(self._make_navigation_button(spec))
        nav.addStretch(1)
        for spec in self._workspace_specs.values():
            if spec.primary:
                continue
            nav.addWidget(self._make_navigation_button(spec))

        parent = self._tabs.parentWidget()
        layout = parent.layout() if parent is not None else None
        if isinstance(layout, QBoxLayout):
            index = layout.indexOf(self._tabs)
            layout.insertWidget(max(0, index), host, 0)
        self._workspace_navigation = host
        self._tabs.currentChanged.connect(self._sync_navigation_selection)
        self._sync_navigation_selection(self._tabs.currentIndex())

    def _make_navigation_button(self, spec: _WorkspaceDestinationSpec) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(f"workspaceNav_{spec.surface_id}")
        button.setProperty("navRole", "primary" if spec.primary else "secondary")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setText(self._t(spec.text_key, spec.fallback))
        button.setAccessibleName(button.text())
        button.clicked.connect(
            lambda _checked=False, sid=spec.surface_id: self.activate_surface(sid)
        )
        self._workspace_nav_buttons[spec.surface_id] = button
        return button

    def workspace_surface_ids(self) -> tuple[str, ...]:
        return tuple(self._workspace_surfaces)

    def primary_surface_ids(self) -> tuple[str, ...]:
        return tuple(sid for sid, spec in self._workspace_specs.items() if spec.primary)

    def secondary_surface_ids(self) -> tuple[str, ...]:
        return tuple(sid for sid, spec in self._workspace_specs.items() if not spec.primary)

    def activate_surface(self, surface_id: str) -> bool:
        target = self._workspace_surfaces.get(surface_id)
        if target is None:
            return False
        index = self._tabs.indexOf(target)
        if index < 0:
            return False
        self._tabs.setCurrentIndex(index)
        self._sync_navigation_selection(index)
        return True

    def current_surface_id(self) -> str | None:
        current = self._tabs.currentWidget()
        for surface_id, widget in self._workspace_surfaces.items():
            if widget is current:
                return surface_id
        return None

    def _sync_navigation_selection(self, _index: int) -> None:
        active = self.current_surface_id()
        for surface_id, button in self._workspace_nav_buttons.items():
            checked = surface_id == active
            if button.isChecked() != checked:
                button.blockSignals(True)
                button.setChecked(checked)
                button.blockSignals(False)

    def _refresh_workspace_navigation_texts(self) -> None:
        for surface_id, button in self._workspace_nav_buttons.items():
            spec = self._workspace_specs[surface_id]
            button.setText(self._t(spec.text_key, spec.fallback))
            button.setAccessibleName(button.text())

    # ------------------------------------------------------- compact status C2
    def _install_compact_operational_status(self) -> None:
        if self._status_bar is None:
            return
        self._stage_badge.setObjectName("stageBadge")
        self._stage_badge.setMaximumWidth(170)
        self._progress.setMaximumWidth(120)
        self._progress_caption.setObjectName("progressCaption")
        self._progress_caption.setMaximumWidth(220)
        self._status_bar.insertWidget(0, self._stage_badge, 0)
        self._status_bar.insertWidget(1, self._progress, 0)
        self._status_bar.insertWidget(2, self._progress_caption, 1)
        if self._database_status is not None:
            self._database_status.setMaximumWidth(260)

    # ------------------------------------------------------- diagnostics C2
    def _install_contextual_diagnostics(self) -> None:
        pane = self._splitter.widget(1)
        if pane is None:
            return
        pane.setObjectName("diagnosticsPane")
        self._diagnostics_pane = pane
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)
        self._btn_settings.hide()
        self._btn_history_metrics.hide()

        toggle = QToolButton(self)
        toggle.setObjectName("diagnosticsToggle")
        toggle.setProperty("variant", "secondary")
        toggle.setCheckable(True)
        toggle.setChecked(False)
        toggle.setAccessibleName(self._diagnostics_label())
        toggle.setText(self._diagnostics_label())
        toggle.toggled.connect(self.set_diagnostics_expanded)
        self._diagnostics_toggle = toggle
        if self._status_bar is not None:
            self._status_bar.addPermanentWidget(toggle)

        pane.hide()
        self._diagnostics_expanded = False
        self.set_diagnostics_expanded(False)

    def _diagnostics_label(self) -> str:
        return self._t("diagnostics.label", "Diagnostics")

    def set_diagnostics_expanded(self, expanded: bool) -> None:
        pane = self._diagnostics_pane
        if pane is None:
            return
        expanded = bool(expanded)
        if expanded:
            saved = QSettings().value(_DIAGNOSTICS_STATE_KEY)
            restored = (
                isinstance(saved, QByteArray)
                and not saved.isEmpty()
                and self._splitter.restoreState(saved)
            )
            pane.show()
            if not restored:
                total = max(2, sum(self._splitter.sizes()))
                diagnostics = max(160, round(total * 0.28))
                self._splitter.setSizes([max(1, total - diagnostics), diagnostics])
        else:
            if self._diagnostics_expanded and not pane.isHidden():
                QSettings().setValue(_DIAGNOSTICS_STATE_KEY, self._splitter.saveState())
            pane.hide()
        self._diagnostics_expanded = expanded
        if self._diagnostics_toggle is not None and self._diagnostics_toggle.isChecked() != expanded:
            self._diagnostics_toggle.blockSignals(True)
            self._diagnostics_toggle.setChecked(expanded)
            self._diagnostics_toggle.blockSignals(False)

    def diagnostics_expanded(self) -> bool:
        return self._diagnostics_expanded

    def _on_finished(self, success: bool, error: object | None) -> None:
        super()._on_finished(success, error)
        if error is not None:
            self.set_diagnostics_expanded(True)

    # ----------------------------------------------------------- support tools
    def _build_ribbon(self) -> None:
        super()._build_ribbon()
        if self._toolbar is None or self._support_toolbar_actions:
            return

        # Keep workflow QAction objects and shortcuts on the window, but remove
        # their duplicate first-class toolbar presentation. Execution remains in
        # the fixed CTA footer; these shortcuts still execute rather than navigate.
        for key in ("build", "allocate", "mentor_pool", "rule_engine", "prefs", "database"):
            action = self._toolbar_actions.get(key)
            if action is not None and action in self._toolbar.actions():
                self._toolbar.removeAction(action)
                self.addAction(action)
        for action in list(self._toolbar.actions()):
            if isinstance(action, QWidgetAction):
                default_widget = action.defaultWidget()
                if default_widget is not None and self._theme_selector is not None and (
                    default_widget is self._theme_selector
                    or default_widget.isAncestorOf(self._theme_selector)
                ):
                    self._toolbar.removeAction(action)
            elif action.isSeparator():
                self._toolbar.removeAction(action)

        settings_action = QAction(self)
        settings_action.setObjectName("actionPresentationSettings")
        settings_action.triggered.connect(self._open_settings_dialog)
        history_action = QAction(self)
        history_action.setObjectName("actionHistoryMetrics")
        history_action.triggered.connect(self._show_history_metrics)
        self._toolbar.addSeparator()
        self._toolbar.addAction(settings_action)
        self._toolbar.addAction(history_action)
        self._support_toolbar_actions = {
            "settings": settings_action,
            "history": history_action,
        }
        self._refresh_support_action_texts()

    def _refresh_support_action_texts(self) -> None:
        settings_action = self._support_toolbar_actions.get("settings")
        if settings_action is not None:
            settings_action.setText(self._t("settings.title", "Settings"))
            settings_action.setToolTip(
                self._t("tooltip.preferences", "Change appearance and language")
            )
        history_action = self._support_toolbar_actions.get("history")
        if history_action is not None:
            history_action.setText(self._t("settings.history_metrics", "History Metrics"))

    def _open_settings_dialog(self) -> None:
        dialog = UnifiedSettingsDialog(self._prefs, self._user_settings, self._translator, self)
        dialog.connect_open_last_run(self._open_last_output_folder)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_language = dialog.selected_language
        selected_theme = dialog.selected_theme
        selected_root = dialog.selected_output_root
        self._user_settings = dialog.result_user_settings
        save_user_settings(self._user_settings)
        if selected_root:
            self._prefs.output_root_dir = selected_root
        if selected_theme != self._prefs.theme:
            self._set_theme_mode(selected_theme)
        if selected_language != self._prefs.language:
            self._apply_language(selected_language)
        self._refresh_settings_indicators()
        if not self._user_settings.enable_history_metrics:
            self._reset_history_metrics()
        self._refresh_output_summaries()
        install_combo_chevrons(self)

    # ------------------------------------------------ semantic configuration
    def _refresh_settings_indicators(self) -> None:
        if not hasattr(self, "_settings_indicators") or not hasattr(self, "_user_settings"):
            return
        values = self._user_settings.to_dict()
        labels = self._settings_label_map()
        on_text = self._t("settings.state.on", "On")
        off_text = self._t("settings.state.off", "Off")
        for key, indicator in self._settings_indicators.items():
            enabled = bool(values.get(key, False))
            indicator.setText(f"{labels.get(key, key)}: {on_text if enabled else off_text}")
            indicator.setProperty("settingEnabled", enabled)
            indicator.style().unpolish(indicator)
            indicator.style().polish(indicator)

    # -------------------------------------------------------- product polish
    def _install_product_polish_surfaces(self) -> None:
        self._replace_reference_picker(
            self._picker_schools,
            "reference.schools.placeholder",
            "School reference is managed in Database.",
            "schools",
        )
        self._replace_reference_picker(
            self._picker_crosswalk,
            "reference.groupcodes.placeholder",
            "GroupCode reference is managed in Database.",
            "groupcodes",
        )
        self._replace_primary_output_picker(self._picker_output_matrix, "build")
        self._replace_primary_output_picker(self._picker_alloc_out, "allocate")
        self._replace_primary_output_picker(self._picker_rule_output, "rule-engine")
        self._install_page_guidance()

    def _find_form_row(self, target: QWidget) -> tuple[QFormLayout, int, QWidget] | None:
        for form in self.findChildren(QFormLayout):
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                field = item.widget() if item is not None else None
                if field is not None and (field is target or field.isAncestorOf(target)):
                    return form, row, field
        return None

    def _replace_reference_picker(
        self, picker: FilePicker, text_key: str, fallback: str, suffix: str
    ) -> None:
        located = self._find_form_row(picker)
        if located is None:
            return
        form, row, old_field = located
        label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        label_widget = label_item.widget() if label_item is not None else None
        replacement = QWidget(form.parentWidget())
        replacement.setObjectName(f"databaseReference_{suffix}")
        layout = QHBoxLayout(replacement)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._theme.control_to_control)
        state = QLabel(replacement)
        state.setWordWrap(True)
        state.setAccessibleName(self._t(text_key, fallback))
        self._bind(state, text_key, fallback)
        button = QPushButton(replacement)
        button.setObjectName(f"openDatabase_{suffix}")
        button.setProperty("variant", "secondary")
        button.clicked.connect(lambda _checked=False: self.activate_surface("database"))
        self._bind(button, "action.open_database", "Open Database")
        layout.addWidget(state, 1)
        layout.addWidget(button)
        old_field.hide()
        taken = form.takeRow(row)
        if taken.fieldItem is not None:
            if label_widget is not None:
                form.insertRow(row, label_widget, replacement)
            else:
                form.insertRow(row, replacement)

    def _replace_primary_output_picker(self, picker: FilePicker, run_type: str) -> None:
        located = self._find_form_row(picker)
        if located is None:
            return
        form, row, old_field = located
        label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        label_widget = label_item.widget() if label_item is not None else None
        summary = QLabel(form.parentWidget())
        summary.setObjectName(f"outputWorkspaceSummary_{run_type}")
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.setAccessibleName(self._t("output.automatic", "Automatic output"))
        self._output_summary_labels[run_type] = summary
        # Historic QSettings may contain an arbitrary filename. Routine GUI use
        # intentionally starts in automatic mode; tests/integrators can still
        # inject an explicit path after construction and that path is preserved.
        picker.setText("")
        old_field.hide()
        taken = form.takeRow(row)
        if taken.fieldItem is not None:
            if label_widget is not None:
                form.insertRow(row, label_widget, summary)
            else:
                form.insertRow(row, summary)

    def _add_page_guidance(self, page_name: str, key: str, fallback: str) -> None:
        content = self.findChild(QWidget, page_name)
        if content is None or not isinstance(content.layout(), QBoxLayout):
            return
        label = QLabel(content)
        label.setObjectName(f"pageGuidance_{page_name}")
        label.setProperty("guidanceLevel", "page")
        label.setWordWrap(True)
        label.setAccessibleName(self._t(key, fallback))
        self._bind(label, key, fallback)
        content.layout().insertWidget(1, label)
        self._polish_text_labels[key] = label

    def _add_field_help(self, picker: FilePicker, key: str, fallback: str, object_name: str) -> None:
        located = self._find_form_row(picker)
        if located is None:
            return
        form, row, _field = located
        helper = QLabel(form.parentWidget())
        helper.setObjectName(object_name)
        helper.setProperty("guidanceLevel", "field")
        helper.setWordWrap(True)
        helper.setAccessibleName(self._t(key, fallback))
        self._bind(helper, key, fallback)
        form.insertRow(row + 1, helper)
        self._polish_text_labels[key] = helper

    def _install_page_guidance(self) -> None:
        self._add_page_guidance(
            "pageBuildContent",
            "guidance.build.page",
            "Build the eligibility matrix from the required Inspactor report, database-managed references, and Policy.",
        )
        self._add_field_help(
            self._picker_inspactor,
            "guidance.build.inspactor",
            "Required mentor input for the V3 build pipeline. Select the supported Inspactor workbook before running.",
            "fieldHelp_build_inspactor",
        )
        self._add_field_help(
            self._picker_policy_build,
            "guidance.build.policy",
            "Policy controls the build rules; the configured default is used when you do not select another approved policy file.",
            "fieldHelp_build_policy",
        )
        self._add_page_guidance(
            "pageAllocateContent",
            "guidance.allocate.page",
            "Allocate students to the selected mentor pool after database School/GroupCode references are ready.",
        )
        self._add_field_help(
            self._picker_students,
            "guidance.allocate.students",
            "Required student input. The current GUI accepts Excel or CSV input.",
            "fieldHelp_allocate_students",
        )
        self._add_field_help(
            self._picker_pool,
            "guidance.allocate.pool",
            "Required mentor-pool workbook used by the matrix allocation path.",
            "fieldHelp_allocate_pool",
        )
        self._add_field_help(
            self._picker_current_roster,
            "guidance.rosters",
            "Prior/current rosters are optional inputs for continuity and counters; use them only when that history is available.",
            "fieldHelp_allocate_rosters",
        )
        self._add_page_guidance(
            "pageRuleEngineContent",
            "guidance.rule.page",
            "Run Rule Engine with an existing eligibility matrix and student input; academic year is required.",
        )
        self._add_field_help(
            self._picker_rule_matrix,
            "guidance.rule.matrix",
            "Required eligibility-matrix workbook produced by the supported Matrix build path.",
            "fieldHelp_rule_matrix",
        )
        self._add_field_help(
            self._picker_rule_students,
            "guidance.rule.students",
            "Required student input for Rule Engine; use the input formats accepted by the current file picker.",
            "fieldHelp_rule_students",
        )
        self._add_field_help(
            self._picker_rule_current_roster,
            "guidance.rosters",
            "Prior/current rosters are optional inputs for continuity and counters; use them only when that history is available.",
            "fieldHelp_rule_rosters",
        )

    def _refresh_output_summaries(self) -> None:
        if not hasattr(self, "_prefs"):
            return
        root = self._prefs.output_root_dir
        for label in self._output_summary_labels.values():
            automatic = self._t("output.automatic", "Automatic")
            root_template = self._t("output.root", "Root: {path}")
            detail = self._t(
                "output.run_created",
                "A dated run folder will be created when execution starts.",
            )
            label.setText(f"{automatic}\n{root_template.format(path=root)}\n{detail}")

    # ---------------------------------------------------------- run workspace
    def _prepare_run_workspace(
        self,
        run_type: str,
        primary_picker: FilePicker,
        sabt_picker: FilePicker | None = None,
    ) -> RunOutputWorkspace | None:
        current_output = primary_picker.text().strip()
        prior_auto_output = self._auto_output_paths.get(run_type)
        if current_output and current_output != prior_auto_output:
            # Compatibility seam for tests/integrators that still inject an
            # explicit GUI path. CLI/non-GUI explicit paths are untouched too.
            self._active_run_workspace = None
            self._prefs.last_output_dir = ""
            return None

        workspace = create_run_workspace(self._prefs.output_root_dir, run_type)
        primary_output = str(workspace.primary_output_path)
        primary_picker.setText(primary_output)
        self._auto_output_paths[run_type] = primary_output
        if sabt_picker is not None and sabt_picker.text().strip():
            sabt_picker.setText(str(workspace.artifact_path("sabt")))
        self._prefs.last_output_dir = str(workspace.run_dir)
        self._active_run_workspace = workspace
        self._update_output_folder_button_state()
        return workspace

    def _start_build(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return super()._start_build()
        self._prepare_run_workspace("build", self._picker_output_matrix)
        super()._start_build()

    def _start_allocate(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return super()._start_allocate()
        self._prepare_run_workspace("allocate", self._picker_alloc_out, self._picker_sabt_output_alloc)
        super()._start_allocate()

    def _start_rule_engine(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return super()._start_rule_engine()
        self._prepare_run_workspace("rule-engine", self._picker_rule_output, self._picker_sabt_output_rule)
        super()._start_rule_engine()

    def _determine_last_output_path(self) -> str:
        return self._prefs.last_output_dir or super()._determine_last_output_path()

    def _refresh_last_run_badge(self) -> None:
        super()._refresh_last_run_badge()
        workspace = getattr(self, "_active_run_workspace", None)
        if workspace is None or self._prefs.last_run_type != workspace.run_type:
            return
        if self._prefs.last_output_dir != str(workspace.run_dir):
            return
        if self._stage_detail is not None:
            template = self._t("output.saved_to", "Saved to: {folder}")
            self._stage_detail.setText(template.format(folder=workspace.run_dir.name))

    # ------------------------------------------------------- geometry / bidi
    def _fixed_action_page(self, content: QWidget, button: QPushButton, page_id: str) -> QWidget:
        shell = super()._fixed_action_page(content, button, page_id)
        content.setProperty("workspaceContent", True)
        content.setMaximumWidth(_MAX_WORKING_MEASURE)
        if content.layout() is not None:
            margin = self._theme.page_margin_normal
            content.layout().setContentsMargins(margin, margin, margin, margin)
        scroll = shell.findChild(QScrollArea)
        if scroll is not None:
            scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        footer = shell.findChild(QFrame, "pageActionFooter")
        if footer is not None and footer.layout() is not None:
            footer.layout().setContentsMargins(
                self._theme.page_margin_normal,
                self._theme.label_to_control,
                self._theme.page_margin_normal,
                self._theme.within_group,
            )
        return shell

    def _normalize_file_columns(
        self,
        form: QFormLayout,
        utilities: dict[FilePicker, QPushButton],
    ) -> None:
        rows: list[tuple[int, QWidget, FilePicker, QPushButton | None]] = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            field = item.widget() if item is not None else None
            if field is None:
                continue
            picker = field if isinstance(field, FilePicker) else field.findChild(FilePicker)
            if picker is not None:
                rows.append((row, field, picker, utilities.get(picker)))
        if not rows or not any(utility is not None for _, _, _, utility in rows):
            return
        for row, old_field, picker, utility in reversed(rows):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            label_widget = label_item.widget() if label_item is not None else None
            taken = form.takeRow(row)
            if taken.fieldItem is None:
                continue
            row_widget = QWidget(form.parentWidget())
            row_widget.setProperty("normalizedFileRow", True)
            grid = QGridLayout(row_widget)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(self._theme.control_to_control)
            picker.setParent(row_widget)
            grid.addWidget(picker, 0, 0)
            grid.setColumnStretch(0, 1)
            if utility is not None:
                utility.setParent(row_widget)
                utility.setProperty("rowUtility", True)
                utility.setMinimumWidth(_ROW_UTILITY_WIDTH)
                grid.addWidget(utility, 0, 1)
            else:
                grid.addItem(
                    QSpacerItem(
                        _ROW_UTILITY_WIDTH,
                        1,
                        QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Minimum,
                    ),
                    0,
                    1,
                )
            if old_field is not picker and old_field.parent() is not None:
                old_field.deleteLater()
            if label_widget is not None:
                form.insertRow(row, label_widget, row_widget)
            else:
                form.insertRow(row, row_widget)

    def _apply_adaptive_workspace_geometry(self) -> None:
        margin = (
            self._theme.page_margin_compact
            if self.width() <= _COMPACT_WORKSPACE_WIDTH
            else self._theme.page_margin_normal
        )
        for name in ("pageBuildContent", "pageAllocateContent", "pageRuleEngineContent", "pageExplain"):
            widget = self.findChild(QWidget, name)
            if widget is not None and widget.layout() is not None:
                widget.layout().setContentsMargins(margin, margin, margin, margin)
        for footer in self.findChildren(QFrame, "pageActionFooter"):
            if footer.layout() is not None:
                footer.layout().setContentsMargins(
                    margin,
                    self._theme.label_to_control,
                    margin,
                    self._theme.within_group,
                )
        if self._workspace_navigation is not None:
            layout = self._workspace_navigation.layout()
            if layout is not None:
                layout.setContentsMargins(margin, self._theme.micro, margin, self._theme.micro)
        compact = self.width() <= _COMPACT_WORKSPACE_WIDTH
        self._progress_caption.setVisible(not compact)

    def _remove_decorative_motion(self) -> None:
        pulse = getattr(self, "_progress_pulse", None)
        if pulse is not None:
            pulse.stop()
            pulse.deleteLater()
        self._progress_pulse = None
        if self._progress_caption.graphicsEffect() is not None:
            self._progress_caption.setGraphicsEffect(None)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._splitter and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._update_overlay_geometry()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_theme"):
            self._apply_adaptive_workspace_geometry()

    def _apply_language(self, language: object) -> None:
        super()._apply_language(language)
        if self._workspace_nav_buttons:
            self._refresh_workspace_navigation_texts()
        if self._diagnostics_toggle is not None:
            label = self._diagnostics_label()
            self._diagnostics_toggle.setText(label)
            self._diagnostics_toggle.setAccessibleName(label)
        self._refresh_support_action_texts()
        self._refresh_settings_indicators()
        self._refresh_output_summaries()
        install_combo_chevrons(self)

    def _create_center_management_section(self):
        _v1.get_cached_policy = get_cached_policy
        section = super()._create_center_management_section()
        install_combo_chevrons(section)
        return section

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._diagnostics_expanded and self._splitter is not None:
            QSettings().setValue(_DIAGNOSTICS_STATE_KEY, self._splitter.saveState())
        super().closeEvent(event)


def run_demo() -> None:  # pragma: no cover - manual public C2 demo
    """Run the current public C2 MainWindow rather than the preserved base seam."""

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


def __getattr__(name: str) -> object:
    return getattr(_v1, name)
