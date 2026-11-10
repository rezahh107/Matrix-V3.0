"""Academic-period suggestions for the Allocate workspace."""

from PySide6.QtCore import QCalendar, QDate

from app.core.counter import year_to_yy


def counter_accepts_year(year: int) -> bool:
    """Use the registration counter's existing year contract."""
    try:
        year_to_yy(year)
    except ValueError:
        return False
    return True


def suggest_academic_year(local_date: QDate | None = None) -> int | None:
    """Suggest the start year of the period containing the local date."""
    date = QDate.currentDate() if local_date is None else local_date
    calendar = QCalendar(QCalendar.System.Jalali)
    if not date.isValid() or not calendar.isValid():
        return None
    parts = calendar.partsFromDate(date)
    if not parts.isValid():
        return None
    year = parts.year if parts.month >= 4 else parts.year - 1
    return year if counter_accepts_year(year) else None
