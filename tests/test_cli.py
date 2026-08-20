
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from psuedopy.cli import main


def test_run_subcommand(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(sys, "argv", ["psuedopy", "run", "test.ppy"])
    with patch("psuedopy.main.run_ppy_file") as runner:
        main()
        runner.assert_called_once_with("test.ppy")


def test_compile_subcommand(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(
        sys, "argv", ["psuedopy", "compile", "test.ppy", "-o", "out.cppy"]
    )
    with patch("psuedopy.main.compile_ppy_file") as compiler:
        main()
        compiler.assert_called_once_with("test.ppy", "out.cppy")


def test_repl_subcommand(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(sys, "argv", ["psuedopy", "repl"])
    with patch("psuedopy.main.start_repl") as start_repl:
        main()
        start_repl.assert_called_once_with()


def test_format_subcommand(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(sys, "argv", ["psuedopy", "format", "test.ppy"])
    with patch("psuedopy.main.format_ppy_file") as formatter:
        main()
        formatter.assert_called_once_with("test.ppy")