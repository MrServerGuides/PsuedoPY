from __future__ import annotations

import pytest

from psuedopy.errors import TranspilerError
from psuedopy.transpiler import Transpiler


def translate(source: str) -> str:
    return Transpiler().translate(source).python_code


def execute(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {}
    code = translate(source)
    exec(compile(code, "<test.ppy>", "exec"), namespace, namespace)
    return namespace


def test_documented_input_assignment_translates() -> None:
    assert 'name = input("Name: ")' in translate('Let name = Ask("Name: ")')


def test_function_return_executes() -> None:
    namespace = execute("Function add(a, b)\nReturn a + b\nEnd\nLet answer = add(2, 3)")
    assert namespace["answer"] == 5


def test_repeat_to_is_inclusive() -> None:
    namespace = execute("Let values = []\nRepeat i = 1 To 3\nvalues.append(i)\nEnd")
    assert namespace["values"] == [1, 2, 3]


def test_repeat_downward_with_step() -> None:
    namespace = execute(
        "Let values = []\nRepeat i = 3 To 1 Step -1\nvalues.append(i)\nEnd"
    )
    assert namespace["values"] == [3, 2, 1]


def test_repeat_times() -> None:
    namespace = execute("Let count = 0\nRepeat 4 Times\nSet count To count + 1\nEnd")
    assert namespace["count"] == 4


def test_from_import_translates_both_keywords() -> None:
    assert translate("From pathlib Import Path As P").endswith(
        "from pathlib import Path as P"
    )


def test_case_insensitive_keywords_and_friendly_builtins() -> None:
    namespace = execute(
        "let values = [3, 1, 2]\n"
        "let size = length(values)\n"
        "let ordered = sorted(values)"
    )
    assert namespace["size"] == 3
    assert namespace["ordered"] == [1, 2, 3]


def test_strings_comments_and_attributes_are_not_rewritten() -> None:
    python = translate('Let message = "Text True <>"  # Text False <>\nobj.Text()')
    assert '"Text True <>"' in python
    assert "# Text False <>" in python
    assert "obj.Text()" in python


def test_multiline_strings_are_not_parsed_as_language_statements() -> None:
    namespace = execute(
        'Let message = """first\nWhen True\nText and <> stay text\nEnd\nlast"""'
    )
    assert "When True" in namespace["message"]
    assert "Text and <>" in namespace["message"]


def test_declarations_support_annotations_attributes_and_unpacking() -> None:
    namespace = execute(
        "Let first, second = (1, 2)\n"
        "Let answer: int = first + second\n"
        "Let values = [0]\n"
        "Set values[0] To answer"
    )
    assert namespace["values"] == [3]


def test_condition_single_equals_does_not_change_call_keywords() -> None:
    namespace = execute(
        "Function accepts(value=True)\n"
        "Return value\n"
        "End\n"
        "When accepts(value=False) = False\n"
        "Let result = True\n"
        "End"
    )
    assert namespace["result"] is True


def test_match_case_default_executes() -> None:
    namespace = execute(
        "Let code = 404\n"
        "Match code\n"
        "Case 200\n"
        'Let result = "ok"\n'
        "Case 404\n"
        'Let result = "missing"\n'
        "Default\n"
        'Let result = "other"\n'
        "End"
    )
    assert namespace["result"] == "missing"


def test_try_catch_finally_executes() -> None:
    namespace = execute(
        "Let events = []\n"
        "Try\n"
        'Raise ValueError("bad")\n'
        "Catch ValueError As error\n"
        "events.append(String(error))\n"
        "Finally\n"
        'events.append("done")\n'
        "End"
    )
    assert namespace["events"] == ["bad", "done"]


def test_const_cannot_be_reassigned_in_same_scope() -> None:
    with pytest.raises(TranspilerError, match="Cannot assign to Const"):
        translate("Const answer = 42\nSet answer = 1")

    with pytest.raises(TranspilerError, match="Cannot assign to Const"):
        translate("Const index = 0\nRepeat index = 1 To 3\nPass\nEnd")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("End", "no matching"),
        ("When True\nText('x')", "needs End"),
        ("When True\nEnd", "empty"),
        ("Break", "inside a loop"),
        ("Return 1", "inside Function"),
        ("Try\nPass\nEnd", "Catch or Finally"),
        ("Match 1\nText('x')\nEnd", "Case or Default"),
    ],
)
def test_structural_errors_are_reported(source: str, message: str) -> None:
    with pytest.raises(TranspilerError, match=message):
        translate(source)
