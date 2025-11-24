"""بارگذار Async برای فایل‌های Excel/CSV بر پایه QThread.

این کلاس مسیر فایل را گرفته و با تشخیص پسوند، دیتافریم pandas را در نخ جداگانه
می‌خواند. استفادهٔ نمونه:

    loader = ExcelLoader(Path("data.xlsx"))
    loader.loaded.connect(lambda df: print(df.shape))
    loader.start()
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QThread, Signal


class ExcelLoader(QThread):
    """خواندن ایمن فایل‌های Excel/CSV در نخ جداگانه."""

    loaded: Signal = Signal(object)
    failed: Signal = Signal(str)

    def __init__(self, path: Path):
        super().__init__()
        self._path = Path(path)

    def run(self) -> None:  # type: ignore[override]
        try:
            if not self._path.exists():
                raise FileNotFoundError(str(self._path))
            suffix = self._path.suffix.lower()
            df = pd.read_csv(self._path) if suffix == ".csv" else pd.read_excel(self._path)
            self.loaded.emit(df)
        except Exception as exc:  # pragma: no cover - خطای غیرمنتظره
            self.failed.emit(str(exc))
