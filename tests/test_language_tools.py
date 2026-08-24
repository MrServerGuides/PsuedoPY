from __future__ import annotations

from pathlib import Path

import pytest

from psuedopy.cli import main
from psuedopy.formatter import PsuedoPYFormatter
from psuedopy.main import run_ppy_file
from psuedopy.pkg_manager import PackageManager
from psuedopy.runtime import inclusive_range, repeat_times


def test_formatter_is_structural_and_idempotent() -> None:
    source = "when true then\ntext('yes')\notherwise\ntext('no')\nend\n"
    expected = "When True Then\n    Text('yes')\nOtherwise\n    Text('no')\nEnd\n"
    formatter = PsuedoPYFormatter()
    assert formatter.format(source) == expected
    assert formatter.format(expected) == expected


def test_formatter_keeps_strings_comments_and_attributes() -> None:
    source = 'let value = "text true" # text false\nobject.text()\n'
    formatted = PsuedoPYFormatter().format(source)
    assert '"text true" # text false' in formatted
    assert "object.text()" in formatted


def test_formatter_indents_multiline_collections() -> None:
    source = "let values = [\n1,\n2,\n]\n"
    assert PsuedoPYFormatter().format(source) == ("Let values = [\n    1,\n    2,\n]\n")


def test_run_receives_program_arguments(tmp_path: Path, capsys) -> None:
    program = tmp_path / "args.ppy"
    program.write_text("Import sys\nText(sys.argv[1])\n", encoding="utf-8")
    run_ppy_file(str(program), ["hello"])
    assert capsys.readouterr().out.strip() == "hello"


def test_cli_transpile_command(tmp_path: Path, capsys) -> None:
    source = tmp_path / "hello.ppy"
    output = tmp_path / "hello.py"
    source.write_text('Text("hello")\n', encoding="utf-8")
    main(["transpile", str(source), "-o", str(output)])
    assert "print" in output.read_text(encoding="utf-8")
    assert "Transpiled" in capsys.readouterr().out


def test_cli_can_run_compiled_artifact(tmp_path: Path, capsys) -> None:
    source = tmp_path / "hello.ppy"
    artifact = tmp_path / "hello.cppy"
    source.write_text('Text("compiled")\n', encoding="utf-8")
    main(["compile", str(source), "-o", str(artifact)])
    capsys.readouterr()
    main(["run", str(artifact)])
    assert "compiled" in capsys.readouterr().out


def test_inclusive_range_validates_direction_and_step() -> None:
    assert list(inclusive_range(1, 3)) == [1, 2, 3]
    assert list(inclusive_range(3, 1, -1)) == [3, 2, 1]
    with pytest.raises(ValueError, match="zero"):
        inclusive_range(1, 3, 0)
    with pytest.raises(ValueError, match="positive"):
        inclusive_range(1, 3, -1)


def test_repeat_times_validates_count() -> None:
    assert list(repeat_times(3)) == [0, 1, 2]
    with pytest.raises(ValueError, match="negative"):
        list(repeat_times(-1))


@pytest.mark.parametrize(
    "package", ["--upgrade", "name with spaces", "https://x", "../x"]
)
def test_package_manager_rejects_unsafe_specs(package: str) -> None:
    with pytest.raises(ValueError):
        PackageManager().install(package)
