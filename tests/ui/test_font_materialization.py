"""Tests for deterministic in-memory Vazirmatn variable-font authority."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "PySide6.QtGui",
    exc_type=ImportError,
    reason="PySide6 not available in test environment",
)

from PySide6.QtGui import QFont, QFontInfo, QRawFont
from PySide6.QtWidgets import QApplication, QLabel

from app.ui import fonts, theme
from app.ui.assets.font_data_vazirmatn import VAZIRMATN_VARIABLE_TTF_BASE64
from app.ui.i18n import Language

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VAZIRMATN_SIZE = 241328
EXPECTED_VAZIRMATN_SHA256 = "696249a2c74b39ffdef55de4df2809c5b639d3ff80d618d8160a095d2fd49dca"
NATIVE_ORACLE_MARKER = "MATRIX_NATIVE_FONT_ORACLE_JSON="


def _weight_value(value: object) -> int:
    raw = getattr(value, "value", value)
    return int(raw)  # type: ignore[arg-type]


def _is_vazirmatn_family(value: str) -> bool:
    normalized = value.casefold()
    return "vazirmatn" in normalized or normalized.startswith("vazir") or "وزیر" in value


def test_embedded_vazirmatn_binary_identity_and_round_trip() -> None:
    canonical = base64.b64decode(VAZIRMATN_VARIABLE_TTF_BASE64)
    runtime = fonts._embedded_font_bytes()

    assert canonical == runtime
    assert len(runtime) == EXPECTED_VAZIRMATN_SIZE
    assert hashlib.sha256(runtime).hexdigest() == EXPECTED_VAZIRMATN_SHA256


def test_ensure_vazir_local_fonts_does_not_materialize_production_font(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fonts_dir = tmp_path / "fonts"
    monkeypatch.setattr(fonts, "FONTS_DIR", fonts_dir)

    result = fonts.ensure_vazir_local_fonts()

    assert result == fonts_dir
    assert fonts_dir.is_dir()
    assert list(fonts_dir.glob("*.ttf")) == []


def test_explicit_embedded_font_materialization_is_idempotent(tmp_path) -> None:
    fonts_dir = tmp_path / "development-fonts"

    first = fonts._materialize_embedded_font(fonts_dir)
    second = fonts._materialize_embedded_font(fonts_dir)

    assert first is not None
    assert second == first
    assert first.name == "Vazirmatn-Variable.ttf"
    data = first.read_bytes()
    assert len(data) == EXPECTED_VAZIRMATN_SIZE
    assert hashlib.sha256(data).hexdigest() == EXPECTED_VAZIRMATN_SHA256
    assert list(fonts_dir.glob("*.ttf")) == [first]


def test_embedded_vazirmatn_registers_in_memory_without_disk_write(
    qapp, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fonts_dir = tmp_path / "empty-fonts"
    fonts_dir.mkdir()
    monkeypatch.setattr(fonts, "FONTS_DIR", fonts_dir)
    monkeypatch.setattr(fonts, "_EMBEDDED_FAMILIES", None)

    families = fonts._register_embedded_vazirmatn()

    assert "Vazirmatn" in families
    assert list(fonts_dir.iterdir()) == []
    assert qapp is not None


def test_embedded_variable_vazirmatn_preserves_representative_persian_glyphs(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fonts, "_EMBEDDED_FAMILIES", None)
    families = fonts._register_embedded_vazirmatn()
    family = fonts.resolve_vazir_family_name(candidates=families)

    assert qapp is not None
    assert family == "Vazirmatn"

    raw = QRawFont.fromFont(QFont(family, fonts.DEFAULT_POINT_SIZE))
    assert raw.isValid()
    assert _is_vazirmatn_family(raw.familyName())
    for character in "گچپژی":
        assert raw.supportsCharacter(ord(character))


def test_windows_candidates_use_only_explicit_development_paths(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VAZIR_FONT_PATHS", raising=False)
    assert fonts._windows_candidates() == []

    first = tmp_path / "one"
    second = tmp_path / "two"
    monkeypatch.setenv("VAZIR_FONT_PATHS", os.pathsep.join((str(first), str(second))))
    assert fonts._windows_candidates() == [first, second]


def test_create_app_font_defaults_to_antialias_and_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fonts, "load_vazir_font", lambda point_size=None: None)

    font = fonts.create_app_font()

    assert font.pointSize() == fonts.DEFAULT_POINT_SIZE
    assert font.styleStrategy() & QFont.StyleStrategy.PreferAntialias
    assert font.styleStrategy() & QFont.StyleStrategy.PreferQuality
    if hasattr(QFont, "HintingPreference") and hasattr(
        QFont.HintingPreference, "PreferFullHinting"
    ):
        assert font.hintingPreference() == QFont.HintingPreference.PreferFullHinting


def _native_windows_font_oracle() -> int:
    app = QApplication([])
    if app.platformName().casefold() != "windows":
        raise AssertionError(f"expected windows Qt platform, got {app.platformName()!r}")

    fonts._EMBEDDED_FAMILIES = None
    data = fonts._embedded_font_bytes()
    assert len(data) == EXPECTED_VAZIRMATN_SIZE
    assert hashlib.sha256(data).hexdigest() == EXPECTED_VAZIRMATN_SHA256

    families = fonts._register_embedded_vazirmatn()
    assert "Vazirmatn" in families

    weight_cases = (
        (400, QFont.Weight.Normal),
        (500, QFont.Weight.Medium),
        (600, QFont.Weight.DemiBold),
        (700, QFont.Weight.Bold),
    )
    weights: list[dict[str, object]] = []
    for expected, requested_weight in weight_cases:
        requested = QFont("Vazirmatn", fonts.DEFAULT_POINT_SIZE)
        requested.setWeight(requested_weight)
        info = QFontInfo(requested)
        raw = QRawFont.fromFont(requested)

        resolved_weight = _weight_value(info.weight())
        raw_weight = _weight_value(raw.weight())
        assert info.family() == "Vazirmatn"
        assert resolved_weight == expected
        assert raw.isValid()
        assert raw.familyName() == "Vazirmatn"
        assert raw_weight == expected

        weights.append(
            {
                "requested_weight": expected,
                "resolved_family": info.family(),
                "resolved_style": info.styleName(),
                "resolved_weight": resolved_weight,
                "raw_family": raw.familyName(),
                "raw_style": raw.styleName(),
                "raw_weight": raw_weight,
            }
        )

    glyph_font = QRawFont.fromFont(QFont("Vazirmatn", fonts.DEFAULT_POINT_SIZE))
    assert glyph_font.isValid()
    glyphs = {
        character: glyph_font.supportsCharacter(ord(character))
        for character in "گچپژی"
    }
    assert all(glyphs.values())

    theme.apply_layout_direction(app, Language.FA)

    semantic = QLabel("عنوان معنایی")
    semantic.setObjectName("fontOracleSemanticLabel")
    semantic_font = QFont(app.font())
    semantic_font.setPointSize(13)
    semantic_font.setWeight(QFont.Weight.DemiBold)
    semantic.setFont(semantic_font)

    widget_id = id(semantic)
    expected_size = semantic.font().pointSize()
    expected_weight = _weight_value(semantic.font().weight())

    transitions: list[dict[str, object]] = []
    for language in (Language.FA, Language.EN, Language.FA):
        theme.apply_layout_direction(app, language)
        app.processEvents()

        app_info = QFontInfo(app.font())
        raw_app = QRawFont.fromFont(app.font())
        assert raw_app.isValid()
        assert id(semantic) == widget_id
        assert semantic.font().pointSize() == expected_size
        assert _weight_value(semantic.font().weight()) == expected_weight
        assert semantic.font().family() == app.font().family()

        if language is Language.FA:
            assert app_info.family() == "Vazirmatn"
            assert raw_app.familyName() == "Vazirmatn"
        else:
            assert app_info.family().casefold().startswith("segoe ui")
            assert raw_app.familyName().casefold().startswith("segoe ui")

        transitions.append(
            {
                "language": language.code,
                "application_requested_family": app.font().family(),
                "application_resolved_family": app_info.family(),
                "application_resolved_weight": _weight_value(app_info.weight()),
                "raw_family": raw_app.familyName(),
                "semantic_widget_family": semantic.font().family(),
                "semantic_widget_point_size": semantic.font().pointSize(),
                "semantic_widget_weight": _weight_value(semantic.font().weight()),
                "semantic_widget_id": id(semantic),
            }
        )

    evidence = {
        "qt_platform": app.platformName(),
        "embedded_size": len(data),
        "embedded_sha256": hashlib.sha256(data).hexdigest(),
        "applicationFontFamilies": list(families),
        "weights": weights,
        "glyphs": glyphs,
        "transitions": transitions,
    }
    print(NATIVE_ORACLE_MARKER + json.dumps(evidence, sort_keys=True, ensure_ascii=True))

    semantic.close()
    app.processEvents()
    return 0


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows font oracle requires Windows")
def test_native_windows_variable_font_oracle() -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "windows"
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(ROOT)
        if not existing_pythonpath
        else str(ROOT) + os.pathsep + existing_pythonpath
    )

    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--native-windows-font-oracle"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    marker = next(
        (line for line in result.stdout.splitlines() if line.startswith(NATIVE_ORACLE_MARKER)),
        None,
    )
    if result.returncode != 0 or marker is None:
        pytest.fail(
            "NATIVE_WINDOWS_FONT_ORACLE_FAILED\n"
            f"returncode={result.returncode}\n"
            f"stdout={result.stdout[-4000:]}\n"
            f"stderr={result.stderr[-4000:]}"
        )

    evidence = json.loads(marker.removeprefix(NATIVE_ORACLE_MARKER))
    assert evidence["qt_platform"].casefold() == "windows"
    assert evidence["embedded_size"] == EXPECTED_VAZIRMATN_SIZE
    assert evidence["embedded_sha256"] == EXPECTED_VAZIRMATN_SHA256
    registered_families = evidence["applicationFontFamilies"]
    assert registered_families
    assert registered_families[0] == "Vazirmatn"
    assert all(_is_vazirmatn_family(family) for family in registered_families)
    assert [item["resolved_weight"] for item in evidence["weights"]] == [400, 500, 600, 700]
    assert [item["raw_weight"] for item in evidence["weights"]] == [400, 500, 600, 700]
    assert [item["language"] for item in evidence["transitions"]] == ["fa", "en", "fa"]
    assert evidence["transitions"][0]["application_resolved_family"] == "Vazirmatn"
    assert evidence["transitions"][1]["application_resolved_family"].casefold().startswith(
        "segoe ui"
    )
    assert evidence["transitions"][2]["application_resolved_family"] == "Vazirmatn"

    widget_ids = [item["semantic_widget_id"] for item in evidence["transitions"]]
    assert len(set(widget_ids)) == 1
    assert [item["semantic_widget_point_size"] for item in evidence["transitions"]] == [13, 13, 13]
    assert [item["semantic_widget_weight"] for item in evidence["transitions"]] == [600, 600, 600]


if __name__ == "__main__" and "--native-windows-font-oracle" in sys.argv:
    raise SystemExit(_native_windows_font_oracle())
