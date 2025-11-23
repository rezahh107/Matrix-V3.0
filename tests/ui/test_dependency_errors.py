import importlib
import sys
import types

import pytest


class _StubSharedMemory:
    def __init__(self, *_args, **_kwargs):
        self._attached = False

    def attach(self):
        self._attached = True
        return True

    def create(self, _size):
        self._attached = True
        return True

    def error(self):  # pragma: no cover - فقط برای سازگاری با اینترفیس
        return ""

    def isAttached(self):  # noqa: N802 - امضای Qt
        return self._attached

    def detach(self):
        self._attached = False


class _StubTimer:
    @staticmethod
    def singleShot(_interval, _func):  # pragma: no cover - تنها برای سازگاری
        return None


class _StubApplication:
    def __init__(self, *_args, **_kwargs):
        self.attributes: list[tuple[object, bool]] = []

    @staticmethod
    def instance():
        return None

    def setAttribute(self, attr, value):  # noqa: N802 - امضای Qt
        self.attributes.append((attr, value))

    def setApplicationName(self, *_args, **_kwargs):
        return None

    def setOrganizationName(self, *_args, **_kwargs):
        return None

    def setApplicationVersion(self, *_args, **_kwargs):
        return None

    def setQuitOnLastWindowClosed(self, *_args, **_kwargs):
        return None

    def exec(self):  # noqa: A003 - هم‌نام Qt
        return 0


class _StubMessageBox:
    Icon = types.SimpleNamespace(Critical=1, Warning=2)
    StandardButton = types.SimpleNamespace(Ok=1)

    def __init__(self):
        self.icon = None
        self.window_title = None
        self.text = None
        self.informative_text = None
        self.standard_buttons = None

    def setIcon(self, icon):  # noqa: N802 - امضای Qt
        self.icon = icon

    def setWindowTitle(self, title):  # noqa: N802 - امضای Qt
        self.window_title = title

    def setText(self, text):  # noqa: N802 - امضای Qt
        self.text = text

    def setInformativeText(self, text):  # noqa: N802 - امضای Qt
        self.informative_text = text

    def setStandardButtons(self, buttons):  # noqa: N802 - امضای Qt
        self.standard_buttons = buttons

    def exec(self):
        return 0


def _install_pyside_stub(monkeypatch):
    try:
        import PySide6.QtWidgets  # type: ignore
        import PySide6.QtCore  # type: ignore
        return
    except Exception:  # pragma: no cover - در صورت نبود PySide6 فعال می‌شود
        pass

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(ApplicationAttribute=types.SimpleNamespace())
    qtcore.QSharedMemory = _StubSharedMemory
    qtcore.QTimer = _StubTimer
    qtcore.qVersion = lambda: "0.0.0"

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = _StubApplication
    qtwidgets.QMessageBox = _StubMessageBox

    qt_root = types.ModuleType("PySide6")
    qt_root.QtCore = qtcore
    qt_root.QtWidgets = qtwidgets

    monkeypatch.setitem(sys.modules, "PySide6", qt_root)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)


@pytest.fixture()
def main_module(monkeypatch):
    _install_pyside_stub(monkeypatch)
    import app.main as module

    return importlib.reload(module)


def test_load_main_window_reports_missing_dependency(monkeypatch, main_module):
    original_error = ImportError("No module named PySide6", name="PySide6")

    def _fake_import():
        raise original_error

    monkeypatch.setattr(main_module, "_import_main_window_module", _fake_import)

    with pytest.raises(ImportError) as exc:
        main_module.load_main_window()

    message = str(exc.value)
    assert "وابستگی‌های رابط کاربری" in message
    assert "PySide6" in message
    assert "pip install -r requirements.txt" in message
    assert "No module named PySide6" in message
    assert exc.value.__cause__ is original_error


def test_load_main_window_reports_generic_import_error_without_name(monkeypatch, main_module):
    class NamelessImportError(ImportError):
        pass

    original_error = NamelessImportError("libGL error: something something")
    original_error.name = None

    def _fake_import():
        raise original_error

    monkeypatch.setattr(main_module, "_import_main_window_module", _fake_import)

    with pytest.raises(ImportError) as exc:
        main_module.load_main_window()

    message = str(exc.value)
    assert "وابستگی‌های رابط کاربری" in message
    assert "pip install -r requirements.txt" in message
    assert "کتابخانهٔ مفقود" not in message
    assert "libGL error: something something" in message
    assert exc.value.__cause__ is original_error
