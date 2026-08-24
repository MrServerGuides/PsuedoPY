from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from psuedopy.config import ConfigManager
from psuedopy.errors import TranspilerError
from psuedopy.exceptions import print_ppy_error
from psuedopy.grammar import Grammar
from psuedopy.source_map import SourceMap
from psuedopy.transpiler import Transpiler


def isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_config_precedence_and_relative_grammar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = isolate_home(monkeypatch, tmp_path)
    (home / ".psuedopyrc").write_text(
        'theme = "light"\nverbose = false\n', encoding="utf-8"
    )
    (tmp_path / ".psuedopyrc").write_text(
        'grammar_path = "custom.json"\nverbose = true\n', encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.psuedopy]\ntheme = "dark"\ncolor_enabled = false\n',
        encoding="utf-8",
    )
    config = ConfigManager(tmp_path).load()
    assert config.grammar_path == (tmp_path / "custom.json").resolve()
    assert config.theme == "dark"
    assert config.color_enabled is False
    assert config.verbose is True


def test_json_config_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_home(monkeypatch, tmp_path)
    (tmp_path / ".psuedopyrc").write_text(
        json.dumps({"psuedopy": {"theme": "auto"}}), encoding="utf-8"
    )
    assert ConfigManager(tmp_path).load().theme == "auto"


@pytest.mark.parametrize(
    "text",
    [
        'theme = "blue"',
        'color_enabled = "yes"',
        'verbose = "no"',
        "grammar_path = 42",
    ],
)
def test_invalid_configuration_is_rejected(
    text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_home(monkeypatch, tmp_path)
    (tmp_path / ".psuedopyrc").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        ConfigManager(tmp_path).load()


def test_custom_simple_grammar(tmp_path: Path) -> None:
    grammar = tmp_path / "grammar.json"
    grammar.write_text(json.dumps({"Say": "print"}), encoding="utf-8")
    assert (
        Transpiler(grammar)
        .translate('Say("hello")')
        .python_code.endswith('print("hello")')
    )


def test_custom_structured_grammar(tmp_path: Path) -> None:
    grammar = tmp_path / "grammar.json"
    grammar.write_text(
        json.dumps(
            {
                "keywords": {
                    "Say": {
                        "python_target": "print",
                        "category": "statement_start",
                        "canonical": "Say",
                        "aliases": ["Speak"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert (
        Transpiler(grammar)
        .translate('Speak("hello")')
        .python_code.endswith('print("hello")')
    )


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '{"keywords": []}',
        '{"keywords": {"Bad": {"python_target": 1, "category": "x"}}}',
        '{"keywords": {"Bad": {"python_target": "x", "category": "x", "aliases": 1}}}',
    ],
)
def test_invalid_grammar_is_rejected(payload: str, tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(TranspilerError):
        Grammar.load(path)


def test_diagnostic_renders_location_and_generated_source() -> None:
    source_map = SourceMap(
        python_to_ppy={1: 2},
        ppy_lines=["first", "bad line"],
        python_lines=["bad_python"],
    )
    error = TranspilerError("bad syntax", line=2, column=3, source_line="bad line")
    stream = io.StringIO()
    print_ppy_error(
        error,
        source_map,
        filename="program.ppy",
        show_translated=True,
        color=False,
        stream=stream,
    )
    rendered = stream.getvalue()
    assert "bad syntax" in rendered
    assert "line 2, column 3" in rendered
    assert "bad line" in rendered
    assert "bad_python" in rendered
    assert "\033[" not in rendered


def test_runtime_diagnostic_maps_traceback() -> None:
    source_map = SourceMap.identity(["missing_name"])
    stream = io.StringIO()
    try:
        exec(compile("missing_name", "program.ppy", "exec"), {}, {})
    except NameError as exc:
        print_ppy_error(
            exc,
            source_map,
            filename="program.ppy",
            color=False,
            stream=stream,
        )
    assert "NameError" in stream.getvalue()
    assert "missing_name" in stream.getvalue()
