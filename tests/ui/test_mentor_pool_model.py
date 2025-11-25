"""تست‌های دودکشی برای مدل فیلتر استخر منتورها در لایهٔ UI."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "PySide6.QtWidgets",
    reason="PySide6 GUI stack requires libGL/libEGL.",
    exc_type=ImportError,
)

from PySide6.QtCore import QModelIndex

from app.ui.mentor_pool_model import ManagerMentorFilterProxy, ManagerMentorModel
from app.ui.models import MentorPoolEntry


def _sample_entries() -> list[MentorPoolEntry]:
    return [
        MentorPoolEntry(
            mentor_id="101",
            mentor_name="الف",
            manager="مدیر الف",
            center="مرکز ۱",
            school="مدرسه ۱",
            capacity=3,
            enabled=True,
        ),
        MentorPoolEntry(
            mentor_id="202",
            mentor_name="ب",
            manager="مدیر الف",
            center="مرکز ۲",
            school="مدرسه ۲",
            capacity=2,
            enabled=False,
        ),
    ]


def test_mentor_pool_model_can_be_instantiated_with_standard_item_model() -> None:
    model = ManagerMentorModel(_sample_entries())
    assert model.rowCount() > 0


def test_mentor_pool_model_filter_accepts_row_returns_bool() -> None:
    model = ManagerMentorModel(_sample_entries())
    proxy = ManagerMentorFilterProxy()
    proxy.setSourceModel(model)

    assert isinstance(proxy.filterAcceptsRow(0, QModelIndex()), bool)

    proxy.set_query("مدرسه ۱")
    assert proxy.filterAcceptsRow(0, QModelIndex()) is True
