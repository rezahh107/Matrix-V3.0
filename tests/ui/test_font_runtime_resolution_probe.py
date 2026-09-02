from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

import PySide6
import pytest
from PySide6.QtCore import QByteArray, QChar, QSettings, qVersion
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetrics, QRawFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QWidget,
)

from app.ui import fonts
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.widgets.file_picker import FilePicker

PROBE_MARKER = "FONT_RUNTIME_PROBE_JSON="


def _enum_value(value: Any) -> int | str:
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _font_request(font: QFont) -> dict[str, object]:
    return {
        "family": font.family(),
        "styleName": font.styleName(),
        "pointSize": font.pointSize(),
        "pixelSize": font.pixelSize(),
        "weight": _enum_value(font.weight()),
        "italic": font.italic(),
        "styleStrategy": _enum_value(font.styleStrategy()),
        "hintingPreference": _enum_value(font.hintingPreference()),
    }


def _font_info(font: QFont) -> dict[str, object]:
    info = QFontInfo(font)
    return {
        "family": info.family(),
        "styleName": info.styleName(),
        "pointSize": info.pointSize(),
        "pixelSize": info.pixelSize(),
        "weight": _enum_value(info.weight()),
        "italic": info.italic(),
        "exactMatch": info.exactMatch(),
    }


def _font_pair(widget: QWidget, role: str) -> dict[str, object]:
    widget.ensurePolished()
    font = widget.font()
    return {
        "widget_class": type(widget).__name__,
        "object_name": widget.objectName(),
        "visible_text_sample_or_role": role,
        "requested": {
            "family": font.family(),
            "pointSize": font.pointSize(),
            "weight": _enum_value(font.weight()),
        },
        "resolved": _font_info(font),
    }


def _ordinary_label(window: MainWindow, excluded: set[QWidget]) -> QLabel:
    for label in window.findChildren(QLabel):
        if label not in excluded and label.objectName() not in {
            "databaseHealthIcon",
            "fileIconLabel",
            "heroSubtitle",
            "heroBadge",
        }:
            return label
    raise AssertionError("No ordinary QLabel found in actual MainWindow")


def _generic_line_edit(window: MainWindow, picker: FilePicker) -> QLineEdit:
    for edit in window.findChildren(QLineEdit):
        parent = edit.parentWidget()
        inside_picker = False
        while parent is not None:
            if parent is picker or isinstance(parent, FilePicker):
                inside_picker = True
                break
            parent = parent.parentWidget()
        if not inside_picker:
            return edit
    raise AssertionError("No non-FilePicker QLineEdit found in actual MainWindow")


def _required_widget_map(window: MainWindow) -> dict[str, QWidget]:
    hero = window.findChild(QLabel, "heroTitle")
    combo = window.findChild(QComboBox, "themeSelector")
    status_text = window.findChild(QLabel, "statusPill")
    db_text = window.findChild(QLabel, "databaseHealthText")
    log_text = window.findChild(QPlainTextEdit, "textLog")
    build_button = window.findChild(QPushButton, "btnBuildMatrix")
    nav_button = window.findChild(QToolButton, "workspaceNav_build")
    picker = next(iter(window.findChildren(FilePicker)), None)

    required: dict[str, QWidget | None] = {
        "main_window": window,
        "hero_page_title": hero,
        "push_button": build_button,
        "tool_button": nav_button,
        "combo_box": combo,
        "status_bar_text": status_text,
        "database_status_text": db_text,
        "log_diagnostic_text": log_text,
        "file_picker": picker,
    }
    missing = [role for role, widget in required.items() if widget is None]
    if missing:
        raise AssertionError(f"Missing actual Matrix widgets: {missing}")

    assert picker is not None
    picker_edit = picker.line_edit()
    picker_button = picker.findChild(QPushButton, "secondaryButton")
    if picker_button is None:
        raise AssertionError("Actual FilePicker QPushButton not found")

    assert hero is not None
    ordinary = _ordinary_label(window, {hero, status_text, db_text})
    line_edit = _generic_line_edit(window, picker)

    return {
        "main_window": window,
        "hero_page_title": hero,
        "ordinary_label": ordinary,
        "line_edit": line_edit,
        "push_button": build_button,
        "tool_button": nav_button,
        "combo_box": combo,
        "status_bar_text": status_text,
        "database_status_text": db_text,
        "log_diagnostic_text": log_text,
        "file_picker_line_edit": picker_edit,
        "file_picker_push_button": picker_button,
    }


def _glyph_evidence(font: QFont) -> dict[str, object]:
    chars = ["م", "ی", "ژ", "ک", "گ"]
    metrics = QFontMetrics(font)
    metrics_result: dict[str, object] = {}
    for char in chars:
        row: dict[str, object] = {}
        try:
            row["inFont_QChar"] = bool(metrics.inFont(QChar(char)))
        except (AttributeError, TypeError) as exc:
            row["inFont_QChar"] = f"GLYPH_API_UNAVAILABLE:{type(exc).__name__}"
        try:
            row["inFontUcs4"] = bool(metrics.inFontUcs4(ord(char)))
        except (AttributeError, TypeError) as exc:
            row["inFontUcs4"] = f"GLYPH_API_UNAVAILABLE:{type(exc).__name__}"
        metrics_result[char] = row

    result: dict[str, object] = {
        "sample": "سلام فارسی",
        "QFontMetrics": metrics_result,
    }
    try:
        raw = QRawFont.fromFont(font)
        raw_result: dict[str, object] = {
            "familyName": raw.familyName(),
            "styleName": raw.styleName(),
            "isValid": raw.isValid(),
            "supportsCharacter_ucs4": {},
        }
        support = raw_result["supportsCharacter_ucs4"]
        assert isinstance(support, dict)
        for char in chars:
            try:
                support[char] = bool(raw.supportsCharacter(ord(char)))
            except (AttributeError, TypeError) as exc:
                support[char] = f"GLYPH_API_UNAVAILABLE:{type(exc).__name__}"
        result["QRawFont"] = raw_result
    except (AttributeError, TypeError) as exc:
        result["QRawFont"] = f"GLYPH_API_UNAVAILABLE:{type(exc).__name__}"
    return result


def _family_database_evidence() -> dict[str, object]:
    families = list(QFontDatabase.families())
    matching = [
        family
        for family in families
        if "vazir" in family.casefold() or "vazirmatn" in family.casefold() or "وزیر" in family
    ]
    metadata: dict[str, object] = {}
    for family in matching:
        entry: dict[str, object] = {}
        try:
            entry["styles"] = list(QFontDatabase.styles(family))
        except (AttributeError, TypeError) as exc:
            entry["styles"] = f"UNAVAILABLE:{type(exc).__name__}"
        try:
            entry["writingSystems"] = [
                getattr(item, "name", str(item)) for item in QFontDatabase.writingSystems(family)
            ]
        except (AttributeError, TypeError) as exc:
            entry["writingSystems"] = f"UNAVAILABLE:{type(exc).__name__}"
        metadata[family] = entry
    return {
        "matching_vazir_families": matching,
        "Segoe UI_present": "Segoe UI" in families,
        "Tahoma_present": "Tahoma" in families,
        "metadata": metadata,
    }


def _active_override_evidence(app: QApplication, widgets: dict[str, QWidget]) -> dict[str, object]:
    app_qss = app.styleSheet()
    family_rules = re.findall(r"font-family\s*:\s*([^;}]+)", app_qss, flags=re.IGNORECASE)
    shorthand_rules = re.findall(
        r"(?<![-\w])font\s*:\s*([^;}]+)",
        app_qss,
        flags=re.IGNORECASE,
    )
    local_rules: list[dict[str, str]] = []
    for role, widget in widgets.items():
        qss = widget.styleSheet()
        if re.search(r"font-family\s*:|(?<![-\w])font\s*:", qss, flags=re.IGNORECASE):
            local_rules.append({"role": role, "qss": qss})
    return {
        "application_font_family_rules": family_rules,
        "application_font_shorthand_rules": shorthand_rules,
        "representative_local_font_rules": local_rules,
    }


def _transition_record(
    app: QApplication,
    window: MainWindow,
    widgets: dict[str, QWidget],
    language: Language,
    sequence: str,
) -> dict[str, object]:
    window._apply_language(language)
    app.processEvents()
    app_font = app.font()
    return {
        "sequence": sequence,
        "language": language.code,
        "layout_direction": app.layoutDirection().name,
        "application_font": {
            "requested": _font_request(app_font),
            "resolved_QFontInfo": _font_info(app_font),
        },
        "widget_object_ids": {role: id(widget) for role, widget in widgets.items()},
        "widgets": {role: _font_pair(widget, role) for role, widget in widgets.items()},
        "glyph_support_primary_font": _glyph_evidence(app_font),
        "override_evidence": _active_override_evidence(app, widgets),
    }


def _collect_payload(app: QApplication) -> dict[str, object]:
    checkout_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    embedded = fonts._embedded_font_bytes()
    production_diagnostics = fonts.collect_font_diagnostics()

    probe_font_id = QFontDatabase.addApplicationFontFromData(QByteArray(embedded))
    probe_families = (
        list(QFontDatabase.applicationFontFamilies(probe_font_id))
        if probe_font_id >= 0
        else []
    )

    window = MainWindow()
    window.show()
    app.processEvents()
    widgets = _required_widget_map(window)

    transitions: list[dict[str, object]] = []
    for index, language in enumerate((Language.FA, Language.EN, Language.FA), start=1):
        transitions.append(_transition_record(app, window, widgets, language, f"FA_EN_FA_{index}"))
    for index, language in enumerate((Language.EN, Language.FA, Language.EN), start=1):
        transitions.append(_transition_record(app, window, widgets, language, f"EN_FA_EN_{index}"))

    payload = {
        "probe_contract": "MATRIX-C2V2-F01-WINDOWS-FONT-RUNTIME-EVIDENCE",
        "runtime_identity": {
            "repository_head": checkout_head,
            "os": platform.platform(),
            "windows_version": {
                "release": platform.release(),
                "version": platform.version(),
                "win32_ver": list(platform.win32_ver()),
            },
            "python_version": platform.python_version(),
            "PySide6_version": PySide6.__version__,
            "Qt_version": qVersion(),
            "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", ""),
            "qt_platform_name": app.platformName(),
            "process_architecture": {
                "machine": platform.machine(),
                "pointer_bits": struct.calcsize("P") * 8,
            },
        },
        "embedded_payload": {
            "embedded_bytes_length": len(embedded),
            "embedded_bytes_sha256": hashlib.sha256(embedded).hexdigest(),
            "PRODUCTION_FONT_DIAGNOSTICS": production_diagnostics,
        },
        "PROBE_REGISTRATION": {
            "probe_font_id": probe_font_id,
            "applicationFontFamilies": probe_families,
        },
        "family_database": _family_database_evidence(),
        "transitions": transitions,
    }
    window.close()
    app.processEvents()
    return payload


def _child_probe() -> int:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("MatrixFontRuntimeProbe")
    app.setApplicationName("MatrixFontRuntimeProbe")
    settings = QSettings()
    settings.clear()
    settings.sync()
    try:
        payload = _collect_payload(app)
        print(
            PROBE_MARKER
            + json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                default=str,
            )
        )
        return 0
    finally:
        settings.clear()
        settings.sync()
        app.closeAllWindows()
        app.processEvents()


def test_font_runtime_resolution_probe(qapp: QApplication) -> None:
    del qapp
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child-probe"],
        cwd=Path(__file__).resolve().parents[2],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    marker_line = next(
        (line for line in result.stdout.splitlines() if line.startswith(PROBE_MARKER)),
        None,
    )
    if marker_line is None:
        pytest.fail(
            "FONT_PROBE_CHILD_FAILED\n"
            f"returncode={result.returncode}\n"
            f"stdout={result.stdout[-4000:]}\n"
            f"stderr={result.stderr[-4000:]}"
        )
    pytest.fail("EXPECTED_FONT_EVIDENCE_CAPTURE\n" + marker_line)


if __name__ == "__main__" and "--child-probe" in sys.argv:
    raise SystemExit(_child_probe())
