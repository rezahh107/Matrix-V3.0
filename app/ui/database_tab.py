from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.infra.db.reference_tables import ReferenceTableStatus
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.schools.school_repository import SchoolRepository
from app.ui.texts import UiTranslator

__all__ = ["DatabaseTab"]


class DatabaseTab(QWidget):
    """نمای وضعیت و import داده‌های مرجع."""

    def __init__(
        self,
        translator: UiTranslator | None = None,
        parent: QWidget | None = None,
        school_repository: SchoolRepository | None = None,
        groupcode_repository: GroupCodeRepository | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._school_repository = school_repository
        self._groupcode_repository = groupcode_repository
        self.setObjectName("databaseTab")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(self._t("database.title", "Database"))
        title.setObjectName("databaseTitleLabel")
        subtitle = QLabel(
            self._t(
                "database.subtitle",
                "Reference data status and imports for schools and group codes.",
            )
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("databaseSubtitleLabel")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._schools_status_label = QLabel(self._t("database.placeholder", "Not connected yet"))
        self._schools_status_label.setObjectName("databaseSchoolsLabel")
        self._schools_status_label.setWordWrap(True)
        layout.addLayout(
            self._build_section(
                self._t("database.schools", "Schools"),
                self._schools_status_label,
                self.import_schools_via_dialog,
            )
        )

        self._groupcodes_status_label = QLabel(self._t("database.placeholder", "Not connected yet"))
        self._groupcodes_status_label.setObjectName("databaseGroupCodesLabel")
        self._groupcodes_status_label.setWordWrap(True)
        layout.addLayout(
            self._build_section(
                self._t("database.group_codes", "Group codes"),
                self._groupcodes_status_label,
                self.import_groupcodes_via_dialog,
            )
        )

        layout.addStretch(1)
        self.refresh_status()

    def refresh_status(self) -> None:
        self._schools_status_label.setText(self._format_status("schools"))
        self._groupcodes_status_label.setText(self._format_status("groupcodes"))

    def _format_status(self, table: str) -> str:
        repo: object = self._school_repository if table == "schools" else self._groupcode_repository
        status: ReferenceTableStatus | None = None
        if repo is not None and hasattr(repo, "status"):
            status = repo.status()
        if status is None or status.row_count == 0:
            return self._t("database.placeholder", "Not connected yet")
        parts = [self._t("database.rows", "Rows"), str(status.row_count)]
        if status.version_tag:
            parts.append(f"• {self._t('database.version', 'Version')} {status.version_tag}")
        if status.imported_at:
            parts.append(status.imported_at.isoformat())
        if status.source_filename:
            parts.append(status.source_filename)
        return " | ".join(parts)

    def _build_section(
        self, title: str, status_label: QLabel, handler: Callable[[], None]
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName(f"label{title}Heading")
        button = QPushButton(self._t("database.import", "Import"))
        button.clicked.connect(handler)
        row.addWidget(heading)
        row.addStretch(1)
        row.addWidget(status_label)
        row.addWidget(button)
        return row

    def import_schools_via_dialog(self) -> None:
        if self._school_repository is None:
            return
        self._import_with_dialog(self._school_repository)

    def import_groupcodes_via_dialog(self) -> None:
        if self._groupcode_repository is None:
            return
        self._import_with_dialog(self._groupcode_repository)

    def _import_with_dialog(self, repository: object) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("database.select_file", "Select Excel file"),
            "",
            self._t("database.excel_filter", "Excel Files (*.xlsx *.xlsm *.xls)"),
        )
        if not path:
            return
        self._import_from_path(repository, Path(path))

    def _import_from_path(self, repository: object, path: Path) -> None:
        try:
            if hasattr(repository, "import_from_excel"):
                repository.import_from_excel(path)
            self.refresh_status()
            QMessageBox.information(
                self,
                self._t("database.import_done", "Import completed"),
                self._t("database.import_success", "Reference data imported successfully."),
            )
        except Exception as exc:  # pragma: no cover - UI messaging
            QMessageBox.warning(
                self,
                self._t("database.import_failed", "Import failed"),
                str(exc),
            )

    def _t(self, key: str, fallback: str) -> str:
        if self._translator is None:
            return fallback
        return self._translator.text(key, fallback)
