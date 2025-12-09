from __future__ import annotations

import pytest

try:  # pragma: no cover - import guard for headless CI
    from PySide6.QtWidgets import QApplication, QLabel
except ImportError as exc:  # pragma: no cover - skipped when Qt missing
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.db.reference_tables import ReferenceTableStatus
from app.ui.database_tab import DatabaseTab
from app.ui.main_window import MainWindow


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeRepo:
    def __init__(self, count: int) -> None:
        self._count = count

    def status(self) -> ReferenceTableStatus:
        return ReferenceTableStatus(
            table_name="test", row_count=self._count, version_tag="v1", source_filename="src.xlsx"
        )


def test_database_tab_shows_status(qapp: QApplication) -> None:
    tab = DatabaseTab(school_repository=_FakeRepo(3), groupcode_repository=_FakeRepo(2))
    assert tab.objectName() == "databaseTab"
    schools_label = tab.findChild(QLabel, "databaseSchoolsLabel")
    group_codes_label = tab.findChild(QLabel, "databaseGroupCodesLabel")
    assert schools_label is not None
    assert group_codes_label is not None
    assert "3" in schools_label.text()
    assert "2" in group_codes_label.text()
    tab.deleteLater()
    qapp.processEvents()


def test_main_window_contains_database_tab(qapp: QApplication) -> None:
    window = MainWindow()
    tab_titles = [window._tabs.tabText(i) for i in range(window._tabs.count())]
    expected_title = window._t("tabs.database", "پایگاه داده")
    assert expected_title in tab_titles
    absent_title = window._t("tabs.validate", "اعتبارسنجی")
    assert absent_title not in tab_titles
    database_tab = next(
        (
            window._tabs.widget(i)
            for i in range(window._tabs.count())
            if isinstance(window._tabs.widget(i), DatabaseTab)
        ),
        None,
    )
    assert database_tab is not None
    window.close()
    qapp.processEvents()
