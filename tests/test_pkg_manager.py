
from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

from psuedopy.pkg_manager import PackageManager


def test_install_runs_pip_install(monkeypatch: MagicMock) -> None:
    fake = MagicMock(returncode=0, stdout="Installing...\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake)

    PackageManager().install("requests")

    fake.assert_called_once()
    args, kwargs = fake.call_args
    assert args[0][:3] == [sys.executable, "-m", "pip"]
    assert args[0][-1] == "requests"
    assert kwargs["capture_output"] is True


def test_install_raises_runtime_error_on_pip_failure(
    monkeypatch: MagicMock,
) -> None:
    fake = MagicMock(returncode=1, stdout="", stderr="No matching distribution")
    monkeypatch.setattr(subprocess, "run", fake)

    try:
        PackageManager().install("not-a-real-package")
    except RuntimeError as exc:
        assert "pip install failed" in str(exc)
    else:
        raise AssertionError("RuntimeError was not raised")