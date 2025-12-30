from __future__ import annotations

from pathlib import Path

JOIN_KEY_NAMES = (
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
)

ALLOWLIST = {
    "app/core/common/unknown_data_channel.py",
    "app/core/common/join_keys.py",
}


def test_no_silent_join_key_coercion() -> None:
    violations: list[str] = []
    repo_root = Path(__file__).resolve().parents[2]
    for path in (repo_root / "app").rglob("*.py"):
        rel = path.relative_to(repo_root).as_posix()
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "pd.to_numeric" not in line or "errors" not in line or "coerce" not in line:
                continue
            if any(name in line for name in JOIN_KEY_NAMES):
                violations.append(f"{rel}:{line_no}:{line.strip()}")
    assert not violations, "Join-key coercion found outside allowlist:\n" + "\n".join(
        violations
    )
