"""Public MainWindow entrypoint with the bounded UI/UX composition pass.

The pre-existing execution implementation is retained verbatim in
``main_window_base``.  This module changes presentation composition only: layout,
localization bindings, shell geometry and semantic visual state.  All execution
slots and domain/Infra calls continue to resolve to the preserved base methods.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.infra.config_flags import UserSettings, save_user_settings
from app.ui.texts import SUPPORTED_LANGUAGES, UiTranslator
from app.ui.widgets.file_picker import FilePicker

from . import main_window_base as _base

UnknownsPreflightResult = _base.UnknownsPreflightResult
AccentSplitter = _base.AccentSplitter
run_demo = _base.run_demo
get_cached_policy = _base.get_cached_policy
load_policy = _base.load_policy

__all__ = ["MainWindow", "run_demo", "FilePicker", "UnknownsPreflightResult"]


@dataclass
class _TextBinding:
    target: object
    key: str
    fallback: str
    kind: str = "text"


# Existing literals are converted immediately into catalogue bindings.  The
# mapping is intentionally bounded to the reviewed active pages in this work unit.
_LITERAL_BINDINGS: dict[str, tuple[str, str]] = {
    "ورودی‌ها": ("group.inputs", "Inputs"),
    "ورودی‌های تخصیص": ("group.allocate_inputs", "Allocation inputs"),
    "سیاست": ("group.policy", "Policy"),
    "خروجی": ("group.outputs", "Output"),
    "تنظیمات پیشرفته": ("group.advanced", "Advanced settings"),
    "شناسهٔ ثبت‌نام": ("group.registration", "Registration ID"),
    "خروجی Sabt (ImportToSabt)": ("group.sabt_allocate", "Sabt output (ImportToSabt)"),
    "مدیریت مراکز": ("group.center_management", "Center management"),
    "گزارش Inspactor": ("files.inspactor", "Inspactor report"),
    "Schools (Database reference)": ("files.schools", "Schools (Database reference)"),
    "Crosswalk (Database reference)": ("files.crosswalk", "Crosswalk (Database reference)"),
    "خروجی ماتریس": ("files.matrix_output", "Matrix output"),
    "فایل دانش‌آموزان": ("files.students", "Students file"),
    "استخر منتورها": ("files.pool", "Mentor pool"),
    "ستون ظرفیت": ("files.capacity_column", "Capacity column"),
    "سال تحصیلی": ("files.registration_year", "Academic year"),
    "روستر سال قبل": ("files.prior_roster", "Prior roster"),
    "روستر سال جاری": ("files.current_roster", "Current roster"),
    "خروجی تخصیص": ("files.alloc_output", "Allocation output"),
    "فایل خروجی": ("files.sabt_output", "Output file"),
    "فایل تنظیمات": ("files.sabt_config", "Configuration file"),
    "فایل قالب": ("files.sabt_template", "Template file"),
    "فایل ماتریس": ("files.rule_matrix", "Matrix file"),
    "پیشنهاد خودکار": ("action.autodetect", "Auto-detect"),
    "بازنشانی به پیش‌فرض": ("action.reset_default", "Reset to default"),
    "بارگذاری مجدد مدیران": ("action.refresh", "Reload managers"),
    "حاکمیت استخر": ("action.pool_governance", "Pool governance"),
    "ساخت ماتریس": ("action.build", "Build Matrix"),
    "تخصیص": ("action.allocate", "Allocate"),
    "اجرای موتور قواعد": ("action.rule_engine", "Run Rule Engine"),
    "گزارش Explain": ("hero.explain.title", "Explain Report"),
    "ضمیمه": ("hero.explain.badge", "Appendix"),
    "Inspactor report": ("files.inspactor", "Inspactor report"),
    "Policy": ("group.policy", "Policy"),
    "Output": ("group.outputs", "Output"),
    "Allocate": ("action.allocate", "Allocate"),
    "Build Matrix": ("action.build", "Build Matrix"),
    "Rule Engine": ("hero.rule.title", "Rule Engine"),
}


class SettingsDialog(QDialog):
    """Localized presentation for the unchanged UserSettings contract."""

    def __init__(
        self,
        settings: UserSettings,
        translator: UiTranslator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self.setWindowTitle(self._t("settings.title", "Settings"))
        self._history_checkbox = self._check(
            "settings.history_metrics", "History Metrics", settings.enable_history_metrics
        )
        self._debug_checkbox = self._check(
            "settings.trace_debug_sheets", "Trace Debug Sheets", settings.enable_trace_debug_sheets
        )
        self._mentor_trace_checkbox = self._check(
            "settings.mentor_trace", "Mentor Pipeline Trace", settings.enable_mentor_trace_debug
        )
        self._pool_governance_checkbox = self._check(
            "settings.pool_trace", "Pool Governance Trace", settings.enable_pool_governance_trace
        )
        self._bucket_trace_checkbox = self._check(
            "settings.bucket_trace", "Bucket Trace", settings.enable_bucket_trace
        )
        self._qa_pool_coverage_checkbox = self._check(
            "settings.qa_coverage", "QA Pool Coverage Rules", settings.enable_qa_pool_coverage_rules
        )
        self._join_bucket_checkbox = self._check(
            "settings.join_buckets", "Use Join Buckets", settings.use_join_buckets
        )
        self._trace_checkbox = self._check(
            "settings.trace_export", "Trace Sheet Export", settings.enable_trace_export
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._t("settings.description", "Toggle optional diagnostics and exports"), self))
        for checkbox in (
            self._history_checkbox,
            self._debug_checkbox,
            self._mentor_trace_checkbox,
            self._pool_governance_checkbox,
            self._bucket_trace_checkbox,
            self._qa_pool_coverage_checkbox,
            self._join_bucket_checkbox,
            self._trace_checkbox,
        ):
            layout.addWidget(checkbox)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _check(self, key: str, fallback: str, checked: bool) -> QCheckBox:
        widget = QCheckBox(self._t(key, fallback), self)
        widget.setChecked(checked)
        return widget

    @property
    def result_settings(self) -> UserSettings:
        return UserSettings(
            enable_history_metrics=self._history_checkbox.isChecked(),
            enable_trace_debug_sheets=self._debug_checkbox.isChecked(),
            enable_trace_export=self._trace_checkbox.isChecked(),
            enable_mentor_trace_debug=self._mentor_trace_checkbox.isChecked(),
            enable_bucket_trace=self._bucket_trace_checkbox.isChecked(),
            enable_pool_governance_trace=self._pool_governance_checkbox.isChecked(),
            enable_qa_pool_coverage_rules=self._qa_pool_coverage_checkbox.isChecked(),
            use_join_buckets=self._join_bucket_checkbox.isChecked(),
        )

    def _t(self, key: str, fallback: str) -> str:
        return self._translator.text(key, fallback)


class MainWindow(_base.MainWindow):
    """Presentation-only composition over the preserved execution MainWindow."""

    def __init__(self) -> None:
        self._ui_text_bindings: list[_TextBinding] = []
        self._literal_binding_index: dict[str, tuple[str, str]] | None = None
        self._formatted_center_labels: list[tuple[QLabel, str]] = []
        stored_splitter = QSettings().value("ui/main_splitter")
        self._had_saved_splitter_state = isinstance(stored_splitter, QByteArray) and not stored_splitter.isEmpty()
        self._default_splitter_ratio_pending = not self._had_saved_splitter_state
        self._default_splitter_ratio_scheduled = False
        super().__init__()
        self._register_shell_bindings()
        self._refresh_reviewed_surface_texts()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt signature
        super().showEvent(event)
        if self._default_splitter_ratio_pending and not self._default_splitter_ratio_scheduled:
            self._default_splitter_ratio_scheduled = True
            QTimer.singleShot(0, self._apply_default_splitter_ratio_once)

    def _apply_default_splitter_ratio_once(self) -> None:
        if not self._default_splitter_ratio_pending:
            return
        self._default_splitter_ratio_pending = False
        splitter = self._splitter
        if splitter is None or splitter.count() != 2:
            return
        sizes = splitter.sizes()
        available = sum(sizes)
        if available <= 1:
            return
        bottom = max(1, round(available * 0.25))
        splitter.setSizes([available - bottom, bottom])

    # ---------------------------------------------------------- page composition
    def _build_build_page(self) -> QWidget:
        content = super()._build_build_page()
        self._bind_hero(content, "build")
        self._bind_existing_literals(content)
        self._bind_picker(self._picker_inspactor, "files.inspactor", "Inspactor report")
        self._bind_picker(
            self._picker_schools,
            "reference.schools.placeholder",
            "School reference is managed in the Database tab.",
        )
        self._bind(self._picker_schools, "reference.schools.tooltip", "School reference is database-backed; update it from the Database tab.", "tooltip")
        self._bind_picker(
            self._picker_crosswalk,
            "reference.groupcodes.placeholder",
            "GroupCode reference is managed in the Database tab.",
        )
        self._bind(self._picker_crosswalk, "reference.groupcodes.tooltip", "GroupCode reference is database-backed; update it from the Database tab.", "tooltip")
        self._bind_picker(self._picker_policy_build, "placeholder.policy", "Default: config/policy.json")
        self._bind_picker(self._picker_output_matrix, "placeholder.matrix_output", "Matrix output (*.xlsx)")
        self._bind(self._btn_matrix_mentor_pool, "action.pool_governance", "Pool governance")
        self._prepare_form_geometry(
            content,
            {self._picker_inspactor: self._btn_matrix_mentor_pool},
        )
        return self._workflow_page(content, self._btn_build, "Build")

    def _build_allocate_page(self) -> QWidget:
        content = super()._build_allocate_page()
        self._bind_hero(content, "allocate")
        self._bind_existing_literals(content)
        self._bind_picker(self._picker_students, "placeholder.students", "Students (*.xlsx or *.csv)")
        self._bind_picker(self._picker_pool, "placeholder.pool", "Mentor pool (*.xlsx)")
        self._bind_picker(self._picker_policy_allocate, "placeholder.policy", "Default: config/policy.json")
        self._bind_picker(self._picker_alloc_out, "placeholder.alloc_output", "Allocation output (*.xlsx)")
        self._bind_picker(self._picker_prior_roster, "placeholder.prior_roster", "Prior roster (optional)")
        self._bind_picker(self._picker_current_roster, "placeholder.current_roster", "Current roster / counters")
        self._bind_picker(self._picker_sabt_output_alloc, "placeholder.sabt_output", "Sabt output (*.xlsx)")
        self._bind_picker(self._picker_sabt_config_alloc, "placeholder.sabt_config", "SmartAlloc_Exporter_Config_v1.json")
        self._bind_picker(self._picker_sabt_template_alloc, "placeholder.sabt_template", "Optional ImportToSabt template")
        self._bind(self._btn_mentor_pool, "action.pool_governance", "Pool governance")
        self._bind(self._btn_update_schools, "reference.update.schools", "Update schools")
        self._bind(self._btn_update_groupcodes, "reference.update.groupcodes", "Update group codes")
        self._bind(self._btn_autodetect, "action.autodetect", "Auto-detect")
        self._bind_line_placeholder(self._combo_academic_year.lineEdit(), "placeholder.year", "e.g. 1404")
        self._bind_semantic_label(
            content,
            "allocateReferenceHint",
            "reference.allocate.hint",
            "Allocation uses database-backed references; update them from Excel only when needed.",
        )
        self._bind(
            self._edit_capacity,
            "files.capacity_column.tooltip",
            "Input column identifier for remaining mentor capacity. Default: remaining_capacity",
            "tooltip",
        )
        self._prepare_form_geometry(
            content,
            {self._picker_pool: self._btn_mentor_pool},
        )
        return self._workflow_page(content, self._btn_allocate, "Allocate")

    def _build_rule_engine_page(self) -> QWidget:
        content = super()._build_rule_engine_page()
        self._bind_hero(content, "rule")
        self._bind_existing_literals(content)
        self._bind_picker(self._picker_rule_matrix, "placeholder.rule_matrix", "Eligibility matrix (*.xlsx)")
        self._bind_picker(self._picker_rule_students, "placeholder.rule_students", "Students for Rule Engine")
        self._bind_picker(self._picker_policy_rule, "placeholder.policy", "Default: config/policy.json")
        self._bind_picker(self._picker_rule_output, "placeholder.rule_output", "Rule Engine output (*.xlsx)")
        self._bind_picker(self._picker_rule_prior_roster, "placeholder.prior_roster", "Prior roster (optional)")
        self._bind_picker(self._picker_rule_current_roster, "placeholder.current_roster", "Current roster / counters")
        self._bind_picker(self._picker_sabt_output_rule, "placeholder.sabt_output", "Sabt output (*.xlsx)")
        self._bind_picker(self._picker_sabt_config_rule, "placeholder.sabt_config", "SmartAlloc_Exporter_Config_v1.json")
        self._bind_picker(self._picker_sabt_template_rule, "placeholder.sabt_template", "Optional ImportToSabt template")
        self._bind(self._btn_rule_autodetect, "action.autodetect", "Auto-detect")
        self._bind_line_placeholder(self._combo_rule_academic_year.lineEdit(), "placeholder.year", "e.g. 1404")
        self._prepare_form_geometry(content, {})
        return self._workflow_page(content, self._btn_rule_engine, "RuleEngine")

    def _build_explain_page(self) -> QWidget:
        page = super()._build_explain_page()
        self._bind_hero(page, "explain")
        self._bind_existing_literals(page)
        direct_labels = [
            label
            for label in page.findChildren(QLabel, options=Qt.FindChildOption.FindDirectChildrenOnly)
            if label.objectName() not in {"heroTitle", "heroSubtitle", "heroBadge"}
        ]
        if direct_labels:
            self._bind(direct_labels[0], "explain.summary", "Explain rows are stored in a separate Excel sheet so each decision remains traceable.")
        if len(direct_labels) > 1:
            self._bind(direct_labels[1], "explain.columns_hint", "Each Explain row contains student, selected mentor, active rule and the corresponding reason.")
        return page

    def _wrap_page(self, page: QWidget) -> QWidget:
        if bool(page.property("workflowPage")):
            return page
        return super()._wrap_page(page)

    def _workflow_page(self, content: QWidget, button: QPushButton, page_id: str) -> QWidget:
        """Compose one primary workflow page as sections plus a contained action.

        The page reads hero → guidance → Major Section Regions → Action Region,
        all inside the same scrollable content. There is no window-bottom CTA
        footer: the primary action belongs to the content flow, directly after
        the final Major Section, so it stays attached to the form it submits
        however tall the desktop window becomes.
        """

        content.setObjectName(f"page{page_id}Content")
        self._promote_major_sections(content)
        self._install_action_region(content, button)

        shell = QWidget(self)
        shell.setObjectName(f"page{page_id}")
        shell.setProperty("workflowPage", True)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea(shell)
        scroll.setObjectName(f"scroll{page_id}")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return shell

    # ------------------------------------------------------- spatial hierarchy
    def _promote_major_sections(self, content: QWidget) -> tuple[QGroupBox, ...]:
        """Give the page's own workflow groups the Major Section Region role.

        Section identity is structural: a Major Section is a ``QGroupBox`` owned
        directly by the page's top-level layout. That addresses the real semantic
        groups without matching title strings, Persian/English copy or child
        indexes, and it cannot leak the region treatment into nested groups or
        into unrelated dialogs that reuse ``QGroupBox``.
        """

        outer = content.layout()
        if not isinstance(outer, QBoxLayout):
            return ()

        theme = self._theme
        sections: list[QGroupBox] = []
        for index in range(outer.count()):
            group = outer.itemAt(index).widget()
            if not isinstance(group, QGroupBox):
                continue
            group.setProperty("sectionRole", "major")
            group.style().unpolish(group)
            group.style().polish(group)
            inner = group.layout()
            if inner is not None:
                # The region's own QSS padding is the only inset; a second layout
                # margin would double it and push content off the field measure.
                inner.setContentsMargins(0, 0, 0, 0)
                if isinstance(inner, QFormLayout):
                    inner.setHorizontalSpacing(theme.label_to_control)
                    inner.setVerticalSpacing(theme.within_group)
                elif isinstance(inner, QBoxLayout):
                    inner.setSpacing(theme.within_group)
            sections.append(group)

        # The page rhythm is the intra-section row gap; each Major Section adds
        # `major_section_extra_gap` on top of it through the central QSS, so the
        # macro gap between two sections stays perceptibly larger than the gap
        # between two rows inside one section.
        outer.setSpacing(theme.within_group)
        self.mark_section_row_hosts(content)
        return tuple(sections)

    def mark_section_row_hosts(self, root: QWidget) -> int:
        """Flag the pure layout hosts that must not repaint the page background.

        A row wrapper is a bare ``QWidget`` that exists only to hold a layout. It
        has no surface of its own, but the global ``QWidget`` rule paints the page
        background, which used to be invisible while every group was transparent.
        On a Major Section Region's opaque surface the same fill reads as a hole
        punched through the region, so these hosts are marked for the central QSS
        to keep transparent. Re-running this is safe: later composition passes add
        more row hosts, and marking is idempotent.
        """

        marked = 0
        for child in root.findChildren(QWidget):
            # Exactly ``QWidget`` - a subclass paints its own authored surface.
            if type(child) is not QWidget or child.layout() is None:
                continue
            if bool(child.property("sectionRowHost")):
                continue
            child.setProperty("sectionRowHost", True)
            child.style().unpolish(child)
            child.style().polish(child)
            marked += 1
        return marked

    def _install_action_region(self, content: QWidget, button: QPushButton) -> QFrame | None:
        """Move the primary CTA into a semantic region inside the page content.

        The preserved base composes the action as a bare stretch/button row. This
        replaces that row, in place, with a named Action Region so the action
        keeps the working column, follows the final Major Section, and remains
        reachable by ordinary page scrolling.
        """

        outer = content.layout()
        if not isinstance(outer, QBoxLayout):
            return None

        index = outer.count()
        for position in range(outer.count()):
            row = outer.itemAt(position).layout()
            if row is None or row.indexOf(button) < 0:
                continue
            index = position
            outer.takeAt(position)
            while row.count():
                row.takeAt(0)
            row.deleteLater()
            break

        region = QFrame(content)
        region.setObjectName("pageActionRegion")
        region.setProperty("actionRegion", "page")
        region_layout = QHBoxLayout(region)
        region_layout.setContentsMargins(0, 0, 0, 0)
        region_layout.setSpacing(self._theme.control_to_control)
        # Logical trailing placement: Qt mirrors the stretch under RTL, so the
        # action keeps the working column's trailing edge in both directions.
        region_layout.addStretch(1)
        button.setParent(region)
        button.setProperty("variant", "primary")
        region_layout.addWidget(button)
        outer.insertWidget(index, region)
        return region

    # -------------------------------------------------------------- geometry/bidi
    def _prepare_form_geometry(
        self,
        root: QWidget,
        utilities: dict[FilePicker, QPushButton],
    ) -> None:
        forms: list[QFormLayout] = []
        for group in root.findChildren(QGroupBox):
            layout = group.layout()
            if isinstance(layout, QFormLayout):
                forms.append(layout)
        for form in forms:
            form.setLabelAlignment(Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
            form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
            self._normalize_file_columns(form, utilities)
            self._convert_empty_label_rows(form)

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
            if picker is None:
                continue
            rows.append((row, field, picker, utilities.get(picker)))
        if not rows or not any(utility is not None for _, _, _, utility in rows):
            return

        utility_width = 124
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
            grid.setHorizontalSpacing(8)
            picker.setParent(row_widget)
            grid.addWidget(picker, 0, 0)
            grid.setColumnStretch(0, 1)
            if utility is not None:
                utility.setParent(row_widget)
                utility.setProperty("rowUtility", True)
                utility.setMinimumWidth(utility_width)
                grid.addWidget(utility, 0, 1)
            else:
                grid.addItem(
                    QSpacerItem(utility_width, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum),
                    0,
                    1,
                )
            if old_field is not picker and old_field.parent() is not None:
                # Hide before the deferred delete: an emptied row wrapper keeps
                # painting its opaque background over the section title until the
                # event loop actually collects it.
                old_field.hide()
                old_field.deleteLater()
            if label_widget is not None:
                form.insertRow(row, label_widget, row_widget)
            else:
                form.insertRow(row, row_widget)

    def _convert_empty_label_rows(self, form: QFormLayout) -> None:
        for row in reversed(range(form.rowCount())):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            label = label_item.widget() if label_item is not None else None
            field = field_item.widget() if field_item is not None else None
            if not isinstance(label, QLabel) or label.text().strip() or field is None:
                continue
            form.takeRow(row)
            label.deleteLater()
            form.insertRow(row, field)

    # --------------------------------------------------------------- localization
    def _bind(self, target: object, key: str, fallback: str, kind: str = "text") -> None:
        if target is None:
            return
        marker = (id(target), key, kind)
        if any((id(item.target), item.key, item.kind) == marker for item in self._ui_text_bindings):
            return
        binding = _TextBinding(target, key, fallback, kind)
        self._ui_text_bindings.append(binding)
        self._apply_binding(binding)

    def _apply_binding(self, binding: _TextBinding) -> None:
        text = self._translator.text(binding.key, binding.fallback)
        target = binding.target
        if binding.kind == "text" and hasattr(target, "setText"):
            target.setText(text)
        elif binding.kind == "title" and hasattr(target, "setTitle"):
            target.setTitle(text)
        elif binding.kind == "placeholder" and hasattr(target, "setPlaceholderText"):
            target.setPlaceholderText(text)
        elif binding.kind == "picker_placeholder" and hasattr(target, "set_placeholder_text"):
            target.set_placeholder_text(text)
        elif binding.kind == "tooltip" and hasattr(target, "setToolTip"):
            target.setToolTip(text)

    def _bind_picker(self, picker: FilePicker, key: str, fallback: str) -> None:
        picker.update_translator(self._translator)
        self._bind(picker, key, fallback, "picker_placeholder")

    def _bind_line_placeholder(self, edit: QLineEdit | None, key: str, fallback: str) -> None:
        if edit is not None:
            edit.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
            self._bind(edit, key, fallback, "placeholder")

    def _bind_hero(self, root: QWidget, scenario: str) -> None:
        title = root.findChild(QLabel, "heroTitle")
        subtitle = root.findChild(QLabel, "heroSubtitle")
        badge = root.findChild(QLabel, "heroBadge")
        names = {
            "build": ("Build Matrix", "Select inputs and build the eligibility matrix.", "Step 1 of 3"),
            "allocate": ("Allocate", "Pick student and mentor pools for allocation and Sabt exports.", "Step 2 of 3"),
            "rule": ("Rule Engine", "Run the Rule Engine on the built matrix to review policy and counters.", "Step 3 of 3"),
            "explain": ("Explain Report", "Quick access to decision explainability for audits and training.", "Appendix"),
        }
        fallback_title, fallback_subtitle, fallback_badge = names[scenario]
        self._bind(title, f"hero.{scenario}.title", fallback_title)
        self._bind(subtitle, f"hero.{scenario}.subtitle", fallback_subtitle)
        self._bind(badge, f"hero.{scenario}.badge", fallback_badge)

    def _literal_index(self) -> dict[str, tuple[str, str]]:
        """Return the literal→key index, widened to every catalogue language.

        A reviewed page constructed while one language is active carries that
        language's catalogue values as literals. Indexing only one language left
        rows such as the database-reference labels unbound after a switch, so the
        other language kept showing through. The authored map stays authoritative
        for ambiguous literals; catalogue values only add entries for keys it
        already governs.
        """

        if self._literal_binding_index is None:
            index: dict[str, tuple[str, str]] = dict(_LITERAL_BINDINGS)
            catalogues = [UiTranslator(language) for language in SUPPORTED_LANGUAGES]
            for key, fallback in set(_LITERAL_BINDINGS.values()):
                for catalogue in catalogues:
                    literal = catalogue.text(key, "").strip()
                    if literal and index.get(literal, (key, fallback))[0] == key:
                        index[literal] = (key, fallback)
            self._literal_binding_index = index
        return self._literal_binding_index

    def _bind_existing_literals(self, root: QWidget) -> None:
        index = self._literal_index()
        for group in root.findChildren(QGroupBox):
            mapping = index.get(group.title())
            if mapping is not None:
                self._bind(group, mapping[0], mapping[1], "title")
        for label in root.findChildren(QLabel):
            mapping = index.get(label.text())
            if mapping is not None:
                self._bind(label, mapping[0], mapping[1])
        for button in root.findChildren(QPushButton):
            mapping = index.get(button.text())
            if mapping is not None:
                self._bind(button, mapping[0], mapping[1])
        for picker in root.findChildren(FilePicker):
            picker.update_translator(self._translator)

    def _bind_semantic_label(
        self, root: QWidget, object_name: str, key: str, fallback: str
    ) -> None:
        """Bind one catalogue key to one stable, semantically identified label.

        Layout-position heuristics (for example "the first spanning label in the
        form") silently stop binding when a row is normalized or replaced, which
        is how the reviewed Persian surface fell back to English copy.
        """

        label = root.findChild(QLabel, object_name)
        if label is not None:
            self._bind(label, key, fallback)

    def _refresh_reviewed_surface_texts(self) -> None:
        for binding in self._ui_text_bindings:
            self._apply_binding(binding)
        for label, center_name in self._formatted_center_labels:
            template = self._translator.text("center.manager_label", "Manager {center}:")
            label.setText(template.format(center=center_name))
        for picker in self.findChildren(FilePicker):
            picker.update_translator(self._translator)
        if self._health_widget is not None:
            self._health_widget.update_translator(self._translator)
        if self._database_tab is not None:
            self._database_tab.update_translator(self._translator)
        self._refresh_settings_indicators()

    def _register_shell_bindings(self) -> None:
        self._bind(self._btn_settings, "settings.title", "Settings")
        self._bind(self._btn_history_metrics, "settings.history_metrics", "History Metrics")

    def _apply_language(self, language: object) -> None:
        super()._apply_language(language)
        self._refresh_reviewed_surface_texts()

    # ------------------------------------------------------------- toolbar/status
    def _build_ribbon(self) -> None:
        super()._build_ribbon()
        self._refresh_action_texts()

    def _refresh_action_texts(self) -> None:
        mapping = {
            "build": ("action.run_build", "Run Build", "tooltip.build", "Run the full matrix build pipeline"),
            "allocate": ("action.run_allocate", "Run Allocation", "tooltip.allocate", "Allocate students to mentors"),
            "mentor_pool": ("action.pool_governance", "Pool governance", "tooltip.pool_governance", "Review mentor and manager availability for this run"),
            "rule_engine": ("action.run_rule_engine", "Run Rule Engine", "tooltip.rule_engine", "Execute the rule engine for policy testing"),
            "output": ("dashboard.button.output", "Output Folder", "tooltip.output_folder", "Open the last generated output folder"),
            "prefs": ("action.preferences", "Preferences", "tooltip.preferences", "Change appearance and language"),
            "database": ("action.database", "Database", "tooltip.database", "Open database management"),
        }
        for name, (text_key, text_fallback, tip_key, tip_fallback) in mapping.items():
            action = self._toolbar_actions.get(name)
            if action is None:
                continue
            action.setText(self._translator.text(text_key, text_fallback))
            action.setToolTip(self._translator.text(tip_key, tip_fallback))
        if self._toolbar_theme_label is not None:
            self._toolbar_theme_label.setText(self._t("theme.label", "Theme"))
        if self._theme_selector is not None:
            self._theme_selector.setItemText(0, self._t("theme.light", "Light"))
            self._theme_selector.setItemText(1, self._t("theme.dark", "Dark"))

    def _build_status_bar(self) -> None:
        super()._build_status_bar()
        self._compact_persistent_shell()
        self._update_status_bar_state("ready")

    def _update_status_bar_state(self, key: str) -> None:
        if not hasattr(self, "_status_bar_state"):
            return
        mapping = {
            "ready": self._t("statusbar.ready", "Status: Ready"),
            "running": self._t("statusbar.running", "Status: Running"),
            "error": self._t("statusbar.error", "Status: Error"),
        }
        state = key if key in mapping else "ready"
        self._status_bar_state.setText(mapping[state])
        self._status_bar_state.setProperty("state", state)
        self._status_bar_state.style().unpolish(self._status_bar_state)
        self._status_bar_state.style().polish(self._status_bar_state)

    def _settings_label_map(self) -> dict[str, str]:
        return {
            "enable_history_metrics": self._t("settings.short.history", "History"),
            "enable_trace_debug_sheets": self._t("settings.short.debug_sheets", "Debug Sheets"),
            "enable_trace_export": self._t("settings.short.trace", "Trace"),
            "enable_mentor_trace_debug": self._t("settings.short.mentor_trace", "Mentor Trace"),
            "enable_pool_governance_trace": self._t("settings.short.pool_trace", "Pool Trace"),
            "enable_bucket_trace": self._t("settings.short.bucket_trace", "Bucket Trace"),
            "enable_qa_pool_coverage_rules": self._t("settings.short.qa_coverage", "QA Coverage"),
            "use_join_buckets": self._t("settings.short.join_buckets", "Join Buckets"),
        }

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self._user_settings, self._translator, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._user_settings = dialog.result_settings
            save_user_settings(self._user_settings)
            self._refresh_settings_indicators()
            if not self._user_settings.enable_history_metrics:
                self._reset_history_metrics()

    # --------------------------------------------------------------- shell balance
    def _compact_persistent_shell(self) -> None:
        # Keep _status alive because execution code uses its value as internal state,
        # but remove its duplicated user-visible presentation.
        self._status.hide()
        self._stage_detail.setMaximumHeight(36)
        self._last_run_badge.setMaximumHeight(36)
        self._progress_caption.setAlignment(Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self._progress_caption.setMaximumWidth(220)
        self._log_panel.setMinimumHeight(84)

        progress_layout = self._find_layout_containing(self._progress.parentWidget().layout(), self._progress)
        if isinstance(progress_layout, QBoxLayout):
            progress_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            progress_layout.setSpacing(6)

        lower = self._log_panel.parentWidget()
        lower_layout = lower.layout() if lower is not None else None
        if not isinstance(lower_layout, QBoxLayout):
            return
        lower_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        lower_layout.setContentsMargins(12, 4, 12, 8)
        lower_layout.setSpacing(8)
        lower_layout.setStretch(0, 2)
        lower_layout.setStretch(1, 4)
        lower_layout.setStretch(2, 0)

        controls_item = lower_layout.itemAt(2)
        controls_layout = controls_item.layout() if controls_item is not None else None
        if not isinstance(controls_layout, QBoxLayout):
            return
        if controls_layout.count() and controls_layout.itemAt(0).spacerItem() is not None:
            controls_layout.takeAt(0)
        controls_layout.setDirection(QBoxLayout.Direction.TopToBottom)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._compact_settings_indicator_grid(controls_layout)

    def _compact_settings_indicator_grid(self, controls_layout: QBoxLayout) -> None:
        indicators = list(self._settings_indicators.values())
        for index in range(controls_layout.count()):
            child_layout = controls_layout.itemAt(index).layout()
            if child_layout is None or not any(child_layout.indexOf(item) >= 0 for item in indicators):
                continue
            controls_layout.takeAt(index)
            while child_layout.count():
                child_layout.takeAt(0)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(2)
            for item_index, indicator in enumerate(indicators):
                grid.addWidget(indicator, item_index // 4, item_index % 4)
            controls_layout.insertLayout(index, grid)
            child_layout.deleteLater()
            return

    def _find_layout_containing(self, layout: QLayout | None, widget: QWidget) -> QLayout | None:
        if layout is None:
            return None
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is widget:
                return layout
            child_layout = item.layout()
            found = self._find_layout_containing(child_layout, widget)
            if found is not None:
                return found
        return None

    # -------------------------------------------------- compatibility/test seams
    def _create_center_management_section(self) -> QGroupBox:
        # Preserve the established monkeypatch seam on app.ui.main_window.
        _base.get_cached_policy = get_cached_policy
        group = _base.MainWindow._create_center_management_section(self)
        self._bind(group, "group.center_management", "Center management", "title")
        buttons = group.findChildren(QPushButton)
        if buttons:
            self._bind(buttons[0], "action.reset_default", "Reset to default")
        if len(buttons) > 1:
            self._bind(buttons[1], "action.refresh", "Reload managers")
        for label in group.findChildren(QLabel):
            text = label.text().strip()
            if text.startswith("مدیر ") and text.endswith(":"):
                center_name = text.removeprefix("مدیر ").removesuffix(":")
                self._formatted_center_labels.append((label, center_name))
        return group

    def _create_manager_combo(self, parent: QWidget):
        combo = _base.MainWindow._create_manager_combo(self, parent)
        self._bind(combo, "center.manager_tooltip", "Select or enter the center manager", "tooltip")
        edit = combo.lineEdit()
        if edit is not None:
            edit.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
        return combo


def __getattr__(name: str) -> object:
    """Delegate compatibility attributes to the preserved implementation module."""

    return getattr(_base, name)
