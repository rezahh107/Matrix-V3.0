from __future__ import annotations

from pytest import Config


def test_pytest_timeout_configured(pytestconfig: Config) -> None:
    timeout = int(pytestconfig.getini("timeout"))
    assert timeout == 180


def test_pytest_timeout_method(pytestconfig: Config) -> None:
    timeout_method = pytestconfig.getini("timeout_method")
    assert timeout_method == "thread"
