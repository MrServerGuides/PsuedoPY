from __future__ import annotations

import pytest

from psuedopy.repl import PsuedoPYRepl


def test_repl_variable_state_persists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    inputs: list[str] = ["Let x = 5", "Text(x)", "exit"]
    gen = iter(inputs)

    monkeypatch.setattr("builtins.input", lambda prompt="": next(gen))

    repl = PsuedoPYRepl()
    repl.run()

    captured = capsys.readouterr()
    assert "5" in captured.out


def test_repl_collects_complete_end_block(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    inputs = iter(
        [
            "Let values = []",
            "Repeat i = 1 To 2",
            "values.append(i)",
            "values.append(i * 10)",
            "End",
            "Text(values)",
            "exit",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    PsuedoPYRepl().run()
    assert "[1, 10, 2, 20]" in capsys.readouterr().out


def test_repl_echoes_expression_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    inputs = iter(["1 + 1", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    PsuedoPYRepl().run()
    assert "2" in capsys.readouterr().out
