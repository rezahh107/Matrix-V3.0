"""
نقطه ورود برنامه تخصیص دانشجو-منتور
مدیریت: Singleton، DPI Scaling، خطاهای بحرانی
نسخه بهبود یافته
"""

from __future__ import annotations

import atexit
import getpass
import importlib
import logging
import os
import re
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import ModuleType, TracebackType
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QSharedMemory, Qt, QTimer, qVersion
from PySide6.QtWidgets import QApplication, QMessageBox

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
else:

    class QWidget:  # pragma: no cover - جایگزین ساده برای زمان نبود PySide6
        """شبه‌کلاس برای استفاده در تایپ هینت بدون وابستگی PySide6."""

        pass


from app.infra.logging import LoggingContext, configure_logging, install_exception_hook
from app.utils.path_utils import get_log_directory

__version__ = "1.0.1"
__author__ = "Your Name"
__description__ = "سیستم تخصیص دانشجو-منتور"


logger = logging.getLogger("app.ui.main")
_LOGGING_CONTEXT: LoggingContext | None = None
_RESTORE_EXCEPTION_HOOK: Callable[[], None] | None = None
_RESTORE_GUI_EXCEPTION_HOOK: Callable[[], None] | None = None


def _bootstrap_logging() -> LoggingContext:
    global _LOGGING_CONTEXT, _RESTORE_EXCEPTION_HOOK
    if _LOGGING_CONTEXT is None:
        context = configure_logging(
            app_name="AllocationApp",
            app_version=__version__,
            logger_name=logger.name,
        )
        _LOGGING_CONTEXT = context
        _RESTORE_EXCEPTION_HOOK = install_exception_hook(logger, context)
    return _LOGGING_CONTEXT


def _log_startup_exception(
    target_logger: logging.Logger,
    context: LoggingContext,
    *,
    level: int,
    report_message: str,
    log_message: str,
    traceback_text: str,
) -> tuple[str, Path]:
    error_id = context.new_error_id()
    report_path = context.write_error_report(
        error_id=error_id,
        message=report_message,
        traceback_text=traceback_text,
    )
    target_logger.log(
        level,
        log_message,
        extra={"error_id": error_id, "report_path": str(report_path)},
    )
    return error_id, report_path


def _write_gui_crash_log(traceback_text: str) -> Path:
    log_dir = get_log_directory()
    log_file = log_dir / "gui_crash.log"
    timestamp = datetime.now().isoformat(timespec="seconds")
    payload = [
        "=" * 60,
        f"timestamp={timestamp}",
        f"python={sys.version.split()[0]}",
        "traceback:",
        traceback_text.strip(),
        "",
    ]
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(payload))
    return log_file


def _parse_qt_version(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", version.strip())
    if not match:
        return None
    major, minor, patch_str = match.groups()
    patch = int(patch_str) if patch_str is not None else 0
    return (int(major), int(minor), patch)


def _is_deprecated_application_attribute(
    attr: Qt.ApplicationAttribute, qt_version: tuple[int, int, int] | None | str
) -> bool:
    deprecated_since: dict[Qt.ApplicationAttribute, tuple[int, int, int]] = {
        Qt.ApplicationAttribute.AA_EnableHighDpiScaling: (6, 8, 0),
        Qt.ApplicationAttribute.AA_UseHighDpiPixmaps: (6, 8, 0),
    }
    threshold = deprecated_since.get(attr)
    if threshold is None:
        return False
    if isinstance(qt_version, str):
        qt_version = _parse_qt_version(qt_version)
    if qt_version is None:
        return True
    return qt_version >= threshold


def _set_attribute_if_supported(
    app: QApplication, attr_name: str, qt_version_str: str | None = None
) -> bool:
    qt_version = _parse_qt_version(qt_version_str or qVersion())
    attribute = getattr(Qt.ApplicationAttribute, attr_name, None)
    if attribute is None:
        logger.debug("ApplicationAttribute.%s در این نسخه موجود نیست", attr_name)
        return False
    if _is_deprecated_application_attribute(attribute, qt_version):
        logger.info(
            "ApplicationAttribute.%s در Qt %s منسوخ است و تنظیم نمی‌شود",
            attr_name,
            qt_version_str or qVersion(),
        )
        return False
    app.setAttribute(attribute, True)
    return True


def _configure_high_dpi_attributes(
    app: QApplication, qt_version_str: str | None = None
) -> list[str]:
    applied: list[str] = []
    resolved_version = qt_version_str or qVersion()
    for attr_name in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        if _set_attribute_if_supported(app, attr_name, resolved_version):
            applied.append(attr_name)
    return applied


def _show_gui_crash_dialog(log_path: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("خطای برنامه")
    box.setText("یک خطای غیرمنتظره رخ داد و برنامه متوقف می‌شود.")
    box.setInformativeText("جزئیات کامل در فایل لاگ ذخیره شده است.\n" f"مسیر فایل: {log_path}")
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
    QTimer.singleShot(0, app.quit)


def _install_gui_exception_guard() -> Callable[[], None]:
    previous_hook = sys.excepthook

    def _handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_tb)
            return
        traceback_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log_path = _write_gui_crash_log(traceback_text)
        _show_gui_crash_dialog(log_path)
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle_exception

    def restore() -> None:
        sys.excepthook = previous_hook

    return restore


def _apply_application_attributes(app: QApplication) -> None:
    try:
        qt_version_str = qVersion() or "0.0.0"
    except Exception:  # pragma: no cover
        qt_version_str = "0.0.0"
    attributes = (
        getattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling", None),
        getattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps", None),
    )
    for attr in attributes:
        if attr is None:
            continue
        if _is_deprecated_application_attribute(attr, qt_version_str):
            logger.debug(
                "Skipping deprecated Qt ApplicationAttribute %r on Qt %s",
                attr,
                qt_version_str,
            )
            continue
        app.setAttribute(attr, True)


def setup_environment() -> None:
    try:
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        current_dir = Path(__file__).resolve().parent
        root_dir = current_dir.parent
        for path in (str(root_dir), str(current_dir)):
            if path not in sys.path:
                sys.path.insert(0, path)
                logger.info("مسیر اضافه شد: %s", path)
        logger.info("پیکربندی محیط با موفقیت انجام شد")
    except Exception as exc:
        logger.error("خطا در پیکربندی محیط: %s", exc)
        logger.warning("ادامه اجرا با تنظیمات پیش‌فرض")


class SingleInstanceGuard:
    def __init__(self, key: str = "AllocationApp_SingleInstance_v1") -> None:
        user_specific_key = f"{key}_{getpass.getuser()}"
        self.key = user_specific_key
        self.shared_memory = QSharedMemory(user_specific_key)
        self._is_attached = False
        atexit.register(self.cleanup)

    def is_already_running(self) -> bool:
        try:
            if self.shared_memory.attach():
                self._is_attached = True
                logger.warning("نمونه دیگری از برنامه در حال اجراست")
                return True
            if self.shared_memory.create(1):
                self._is_attached = True
                logger.info("Shared memory ایجاد شد - اولین نمونه برنامه")
                return False
            error = self.shared_memory.error()
            logger.error("خطا در ایجاد shared memory: %s", error)
            return True
        except Exception as exc:
            logger.error("خطا در بررسی singleton: %s", exc)
            return True

    def cleanup(self) -> None:
        try:
            if self.shared_memory.isAttached():
                self.shared_memory.detach()
                logger.info("Shared memory آزاد شد")
        except Exception as exc:
            logger.error("خطا در آزادسازی shared memory: %s", exc)

    def __enter__(self) -> SingleInstanceGuard:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.cleanup()


def show_already_running_message() -> None:
    """Show the standard Qt message box without a competing local visual skin."""

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle("برنامه در حال اجرا")
    msg_box.setText("برنامه تخصیص دانشجو-منتور قبلاً اجرا شده است.")
    msg_box.setInformativeText(
        "لطفاً پنجره برنامه را از نوار وظیفه پیدا کنید.\n\n"
        "در صورت عدم دسترسی:\n"
        "• از Task Manager (Ctrl+Shift+Esc) استفاده کنید\n"
        "• process های مربوطه را ببندید\n"
        "• سپس مجدداً برنامه را اجرا کنید"
    )
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    if hasattr(msg_box, "setDefaultButton"):
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
    msg_box.exec()


def setup_application() -> QApplication:
    """Create/configure QApplication; theme.py owns the base UI font and skin."""

    try:
        app_instance = QApplication.instance()
        if app_instance is None:
            app = QApplication(sys.argv)
        elif isinstance(app_instance, QApplication):
            app = app_instance
        else:
            raise RuntimeError("Existing Qt application is not a QApplication instance")
        _configure_high_dpi_attributes(app, qVersion())
        app.setApplicationName("AllocationApp")
        app.setOrganizationName("YourOrg")
        app.setApplicationVersion(__version__)
        app.setQuitOnLastWindowClosed(True)
        logger.info("QApplication با موفقیت راه‌اندازی شد")
        return app
    except Exception as exc:
        logger.error("خطا در راه‌اندازی QApplication: %s", exc)
        raise


def load_main_window() -> type[QWidget]:
    try:
        module = _import_main_window_module()
        MainWindow = cast(type[QWidget], getattr(module, "MainWindow"))  # noqa: N806
        logger.info("ماژول MainWindow با موفقیت بارگذاری شد")
        return MainWindow
    except ImportError as exc:
        logger.error("خطای Import در بارگذاری MainWindow: %s", exc)
        raise ImportError(_format_dependency_import_error(exc)) from exc


def _import_main_window_module() -> ModuleType:
    return importlib.import_module("app.ui.main_window")


def _format_dependency_import_error(import_error: ImportError) -> str:
    missing = getattr(import_error, "name", None)
    missing_name = str(missing).strip() if missing else ""
    lines = ["خطا در وابستگی‌های رابط کاربری."]
    if missing_name:
        lines.append(f"کتابخانهٔ مفقود: {missing_name}")
    lines.append("برای نصب وابستگی‌ها: uv sync --locked")
    details = str(import_error).strip()
    if details:
        lines.append(f"جزئیات فنی: {details}")
    return "\n".join(lines)


def show_critical_error(
    message: str,
    technical_details: str = "",
    *,
    log_path: Path | None = None,
) -> None:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    error_msg = QMessageBox()
    error_msg.setIcon(QMessageBox.Icon.Critical)
    error_msg.setWindowTitle("خطای بحرانی")
    error_msg.setText("برنامه با خطای غیرمنتظره مواجه شد")
    info_text = message
    if log_path:
        info_text += f"\n\nمسیر گزارش خطا:\n{log_path}"
    error_msg.setInformativeText(info_text)
    if technical_details and hasattr(error_msg, "setDetailedText"):
        error_msg.setDetailedText(technical_details)
    error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_msg.exec()


def main() -> int:
    context = _bootstrap_logging()
    global _RESTORE_GUI_EXCEPTION_HOOK
    if _RESTORE_GUI_EXCEPTION_HOOK is None:
        _RESTORE_GUI_EXCEPTION_HOOK = _install_gui_exception_guard()
    guard = None

    try:
        logger.info("شروع راه‌اندازی برنامه - نسخه %s", __version__)
        logger.info("Python: %s", sys.version)
        logger.info("Platform: %s", sys.platform)
        setup_environment()
        guard = SingleInstanceGuard()
        if guard.is_already_running():
            logger.warning("تلاش برای اجرای نمونه دوم برنامه")
            show_already_running_message()
            return 1
        app = setup_application()
        MainWindowClass = load_main_window()  # noqa: N806
        window = MainWindowClass()
        window.show()
        logger.info("برنامه با موفقیت راه‌اندازی شد و پنجره اصلی نمایش داده شد")
        exit_code = app.exec()
        logger.info("برنامه با کد خروج %s بسته شد", exit_code)
        return exit_code

    except ImportError as exc:
        error_msg = str(exc)
        error_details = traceback.format_exc()
        _, report_path = _log_startup_exception(
            logger,
            context,
            level=logging.ERROR,
            report_message=error_msg,
            log_message=f"خطای Import: {error_msg}",
            traceback_text=error_details,
        )
        show_critical_error(
            "خطا در بارگذاری کامپوننت‌های برنامه.\n\n"
            "راه‌حل‌های احتمالی:\n"
            "• از کامل بودن فایل‌های برنامه اطمینان حاصل کنید\n"
            "• مجدداً برنامه را نصب کنید\n"
            "• با پشتیبانی تماس بگیرید",
            f"ImportError: {error_msg}\nPython Path: {sys.path}",
            log_path=report_path,
        )
        return 1

    except Exception as exc:
        error_message = f"خطای غیرمنتظره: {exc}"
        technical_details = traceback.format_exc()
        _, report_path = _log_startup_exception(
            logger,
            context,
            level=logging.CRITICAL,
            report_message=error_message,
            log_message=f"خطای بحرانی: {error_message}\n{technical_details}",
            traceback_text=technical_details,
        )
        show_critical_error(
            "برنامه با یک خطای غیرمنتظره مواجه شد.\n\n"
            "لطفاً:\n"
            "• شرایط را بررسی کنید\n"
            "• مجدداً تلاش کنید\n"
            "• در صورت تکرار، با پشتیبانی تماس بگیرید",
            technical_details,
            log_path=report_path,
        )
        return 1

    finally:
        if guard:
            guard.cleanup()
        logger.info("تمیزکاری منابع انجام شد")
        global _RESTORE_EXCEPTION_HOOK
        if _RESTORE_EXCEPTION_HOOK:
            _RESTORE_EXCEPTION_HOOK()
            _RESTORE_EXCEPTION_HOOK = None
        if _RESTORE_GUI_EXCEPTION_HOOK is not None:
            _RESTORE_GUI_EXCEPTION_HOOK()
            _RESTORE_GUI_EXCEPTION_HOOK = None


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
