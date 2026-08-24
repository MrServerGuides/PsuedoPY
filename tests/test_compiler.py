from __future__ import annotations

from pathlib import Path

import pytest

from psuedopy.compiler import Compiler
from psuedopy.errors import CompiledFileError


def test_compiled_artifact_round_trip(tmp_path: Path, capsys) -> None:
    output = tmp_path / "hello.cppy"
    compiler = Compiler()
    compiler.write_compiled('Text("portable")', output, "hello.ppy")

    artifact = compiler.load_artifact(output)
    assert artifact.metadata["format_version"] == 2
    assert artifact.original_source == 'Text("portable")'

    compiler.run_compiled(output)
    assert "portable" in capsys.readouterr().out


def test_compiled_artifact_rejects_tampering(tmp_path: Path) -> None:
    output = tmp_path / "program.cppy"
    Compiler().write_compiled('Text("safe")', output)
    payload = bytearray(output.read_bytes())
    payload[-1] ^= 1
    output.write_bytes(payload)

    with pytest.raises(CompiledFileError, match="verification"):
        Compiler().load_artifact(output)


def test_compiled_artifact_rejects_old_magic(tmp_path: Path) -> None:
    output = tmp_path / "old.cppy"
    output.write_bytes(b"PPY\x00\x01bad")
    with pytest.raises(CompiledFileError, match="format version 2"):
        Compiler().load_artifact(output)
