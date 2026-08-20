
from __future__ import annotations

from typing import List

import pytest

from psuedopy.repl import PsuedoPYRepl


def test_repl_variable_state_persists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    inputs: List[str] = ["Let x = 5", "Text(x)", "exit"]
    gen = iter(inputs)

    monkeypatch.setattr("builtins.input", lambda prompt="": next(gen))

    repl = PsuedoPYRepl()
    repl.run()

    captured = capsys.readouterr()
    assert "5" in captured.out