from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from psuedopy.cli import main
from psuedopy.compiler import Compiler
from psuedopy.errors import CompiledFileError
from psuedopy.main import format_ppy_file, run_ppy_file, transpile_ppy_file
from psuedopy.pkg_manager import PackageManager


def test_format_check_reports_changes_without_writing(tmp_path: Path) -> None:
    source = tmp_path / "format.ppy"
    original = "when true\ntext('x')\nend\n"
    source.write_text(original, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        format_ppy_file(str(source), check=True)
    assert error.value.code == 1
    assert source.read_text(encoding="utf-8") == original


def test_format_check_accepts_formatted_source(tmp_path: Path) -> None:
    source = tmp_path / "format.ppy"
    source.write_text("When True\n    Text('x')\nEnd\n", encoding="utf-8")
    assert format_ppy_file(str(source), check=True) is False


def test_runtime_error_is_a_clean_exit(tmp_path: Path, capsys) -> None:
    source = tmp_path / "failure.ppy"
    source.write_text("Text(missing_name)\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        run_ppy_file(str(source), color=False)
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert "NameError" in captured.err
    assert "missing_name" in captured.err


def test_transpile_rejects_invalid_source(tmp_path: Path) -> None:
    source = tmp_path / "invalid.ppy"
    source.write_text("When True\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        transpile_ppy_file(str(source))
    assert error.value.code == 1


def test_compiled_loader_rejects_missing_and_truncated_files(tmp_path: Path) -> None:
    compiler = Compiler()
    with pytest.raises(CompiledFileError, match="Cannot read"):
        compiler.load_artifact(tmp_path / "missing.cppy")

    truncated = tmp_path / "truncated.cppy"
    truncated.write_bytes(compiler._CPPY_MAGIC + struct.pack(">I", 10) + b"{}")
    with pytest.raises(CompiledFileError, match="truncated manifest"):
        compiler.load_artifact(truncated)


def test_compiled_loader_rejects_trailing_data(tmp_path: Path) -> None:
    output = tmp_path / "program.cppy"
    compiler = Compiler()
    compiler.write_compiled('Text("x")', output)
    output.write_bytes(output.read_bytes() + b"extra")
    with pytest.raises(CompiledFileError, match="trailing"):
        compiler.load_artifact(output)


def test_package_manager_builds_upgrade_and_dry_run_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = MagicMock(returncode=0, stdout="", stderr="")
    runner = MagicMock(return_value=completed)
    monkeypatch.setattr("subprocess.run", runner)
    manager = PackageManager("python-test")
    manager.install("requests>=2", upgrade=True, dry_run=True)
    command = runner.call_args.args[0]
    assert command[:3] == ["python-test", "-m", "pip"]
    assert "--upgrade" in command
    assert "--dry-run" in command
    assert command[-1] == "requests>=2"


def test_cli_no_command_prints_help(capsys) -> None:
    main([])
    assert "commands" in capsys.readouterr().out
