from __future__ import annotations

import json
from pathlib import Path

import pytest

from psuedopy.errors import IncompleteInputError, TranspilerError
from psuedopy.formatter import PsuedoPYFormatter
from psuedopy.grammar import Grammar
from psuedopy.main import compile_ppy_file, run_ppy_file, transpile_ppy_file
from psuedopy.runtime import inclusive_range, repeat_times
from psuedopy.source_map import SourceMap
from psuedopy.transpiler import Transpiler


def execute(source: str) -> tuple[dict[str, object], str]:
    translated = Transpiler().translate(source)
    namespace: dict[str, object] = {}
    exec(compile(translated.python_code, "<advanced.ppy>", "exec"), namespace)
    return namespace, translated.python_code


def test_multiline_operators_and_decimal_import_collision() -> None:
    namespace, python = execute(
        "From decimal Import Decimal\n"
        "Let value = (\n"
        "    Decimal(2) * (3 Pow 3)\n"
        ") Div 2\n"
    )
    assert namespace["value"] == 27
    assert "Decimal(2)" in python
    assert "**" in python
    assert "//" in python


def test_pi_regression_program_uses_unaliased_decimal() -> None:
    namespace, _ = execute(
        "From decimal Import Decimal, getcontext\n"
        "Function calculate_pi(digits: Integer) Returns Decimal\n"
        "    Set getcontext().prec To digits + 8\n"
        "    Let constant = Decimal(426880) * Decimal(10005).sqrt()\n"
        "    Let multiplier = 1\n"
        "    Let linear = 13591409\n"
        "    Let exponential = 1\n"
        "    Let factor = 6\n"
        "    Let total = Decimal(linear)\n"
        "    Let iterations = digits Div 14 + 1\n"
        "    Repeat index = 1 To iterations\n"
        "        Set multiplier To (\n"
        "            multiplier * (factor Pow 3 - 16 * factor)\n"
        "        ) Div (index Pow 3)\n"
        "        Set linear To linear + 545140134\n"
        "        Set exponential To exponential * -262537412640768000\n"
        "        Set total To total + Decimal(multiplier * linear) "
        "/ Decimal(exponential)\n"
        "        Set factor To factor + 12\n"
        "    End\n"
        "    Return constant / total\n"
        "End\n"
        "Let result = String(calculate_pi(30))\n"
    )
    assert str(namespace["result"]).startswith("3.141592653589793238462643383")


def test_declared_and_parameter_names_shadow_friendly_builtins() -> None:
    namespace, python = execute(
        "Let Decimal = (value: Integer) => value * 2\n"
        "Function apply(Text, value)\n"
        "    Return Text(value)\n"
        "End\n"
        "Let result = apply(Decimal, 5)\n"
    )
    assert namespace["result"] == 10
    assert "Decimal(5)" not in python


def test_types_optional_parameters_type_alias_and_arrow_function() -> None:
    namespace, python = execute(
        "Type Identifier = Integer | String\n"
        "Function describe(value: Identifier, suffix?: String) Returns String\n"
        '    Return String(value) + (suffix ?? "")\n'
        "End\n"
        "Let double = (value: Integer) => value * 2\n"
        'Let result = describe(double(4), "!")\n'
    )
    assert namespace["result"] == "8!"
    assert "value: Identifier" in python
    assert "suffix: str | None = None" in python


def test_typescript_style_generic_and_array_annotations() -> None:
    namespace, python = execute(
        "Let values: Integer[] = [1, 2, 3]\n"
        'Let lookup: Map<String, Integer> = {"answer": 42}\n'
        "Let maybe: Optional<String> = None\n"
        'Let result = values[2] + lookup["answer"]\n'
    )
    assert namespace["result"] == 45
    assert "values: list[int]" in python
    assert "lookup: dict[str, int]" in python
    assert "maybe: (str) | None" in python


def test_cpp_operators_ternary_increment_comments_and_braces() -> None:
    namespace, python = execute(
        "Let value = 2;\n"
        "When (value > 0 && value < 5) { // bounded value\n"
        "    value++\n"
        "}\n"
        'Let label = value = 3 ? "three" : "other"\n'
        "Let opposite = !(value == 0)\n"
    )
    assert namespace["value"] == 3
    assert namespace["label"] == "three"
    assert namespace["opposite"] is True
    assert "# bounded value" in python


def test_cpp_joined_else_braces() -> None:
    namespace, _ = execute(
        "Let value = 10;\n"
        "If (value < 5) {\n"
        '    Let result = "small";\n'
        "} Else {\n"
        '    Let result = "large";\n'
        "}\n"
    )
    assert namespace["result"] == "large"


def test_c_style_for_loop_and_decrement() -> None:
    namespace, _ = execute(
        "Let values = []\n"
        "For (Let index = 3; index > 0; index--)\n"
        "    values.append(index)\n"
        "End\n"
    )
    assert namespace["values"] == [3, 2, 1]


def test_c_style_for_loop_supports_inclusive_custom_steps() -> None:
    namespace, _ = execute(
        "Let values = []\n"
        "For (Let index = 1; index <= 5; index += 2)\n"
        "    values.append(index)\n"
        "End\n"
        "For (Let index = 5; index >= 1; index -= 2)\n"
        "    values.append(index)\n"
        "End\n"
    )
    assert namespace["values"] == [1, 3, 5, 5, 3, 1]


def test_class_constructor_new_interface_and_enum() -> None:
    namespace, python = execute(
        "Interface Named\n"
        "    Field name: String\n"
        "End\n"
        "Enum Color\n"
        "    Const RED = 1\n"
        "    Const BLUE = 2\n"
        "End\n"
        "Class Counter\n"
        "    Constructor(start: Integer)\n"
        "        Set This.value To start\n"
        "    End\n"
        "    Function increment(This) Returns Integer\n"
        "        This.value++\n"
        "        Return This.value\n"
        "    End\n"
        "End\n"
        "Let counter = New Counter(2)\n"
        "Let result = counter.increment()\n"
        "Let color = Color.BLUE.value\n"
    )
    assert namespace["result"] == 3
    assert namespace["color"] == 2
    assert "Protocol as __PpyProtocol" in python
    assert "Enum as __PpyEnum" in python


def test_generic_syntax_and_class_member_modifiers() -> None:
    namespace, python = execute(
        "Class Factory<T>\n"
        '    Public Field label: String = "factory"\n'
        "    Public Static Function make<T>(value: T) Returns T\n"
        "        Return value\n"
        "    End\n"
        "End\n"
        "Let result = Factory.make(5)\n"
    )
    assert namespace["result"] == 5
    assert "@staticmethod" in python
    assert "def make(value: T) -> T" in python


def test_inheritance_and_optional_parameter_without_annotation() -> None:
    namespace, python = execute(
        "Class Base\n"
        "    Function value(This) Returns Integer\n"
        "        Return 7\n"
        "    End\n"
        "End\n"
        "Class Child Extends Base\n"
        "    Function choose(This, fallback?)\n"
        "        Return fallback ?? This.value()\n"
        "    End\n"
        "End\n"
        "Let result = New Child().choose()\n"
    )
    assert namespace["result"] == 7
    assert "fallback: object | None = None" in python


def test_raw_assignments_are_rejected_but_expression_calls_are_allowed() -> None:
    with pytest.raises(TranspilerError, match="Raw assignment"):
        Transpiler().translate("answer = 42")
    namespace, _ = execute("Let values = []\nvalues.append(1)")
    assert namespace["values"] == [1]


def test_unclosed_multiline_expression_has_ppy_diagnostic() -> None:
    with pytest.raises(TranspilerError, match="missing a closing bracket") as error:
        Transpiler().translate("Let value = (\n    1 + 2")
    assert error.value.location is not None
    assert error.value.location.line == 1

    with pytest.raises(IncompleteInputError):
        Transpiler().translate("Let value = (\n  1", allow_incomplete=True)


def test_backslash_continuation_and_multiline_string_cpp_markers() -> None:
    namespace, python = execute(
        "Let value = 1 + \\\n"
        "    2\n"
        'Let message = """literal // comment\n} Else {\nlast"""\n'
        'Let url = "https://example.com" // actual comment\n'
    )
    assert namespace["value"] == 3
    assert "} Else {" in namespace["message"]
    assert namespace["url"] == "https://example.com"
    assert "# actual comment" in python


def test_null_coalescing_evaluates_left_side_once() -> None:
    namespace, _ = execute(
        "Let calls = 0\n"
        "Function missing()\n"
        "    Global calls\n"
        "    Set calls To calls + 1\n"
        "    Return None\n"
        "End\n"
        'Let result = missing() ?? "fallback"\n'
    )
    assert namespace["calls"] == 1
    assert namespace["result"] == "fallback"


def test_cpp_try_catch_finally_joined_braces() -> None:
    namespace, _ = execute(
        "Let events = []\n"
        "Try {\n"
        '    Raise ValueError("bad")\n'
        "} Catch ValueError As error {\n"
        "    events.append(String(error))\n"
        "} Finally {\n"
        '    events.append("done")\n'
        "}\n"
    )
    assert namespace["events"] == ["bad", "done"]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("Public Function nope()\nPass\nEnd", "only valid inside a type"),
        ("Class Broken\nConstructor value\nEnd", "Constructor syntax"),
        ("Field name: String", "only valid inside Class or Interface"),
        ("Type Broken", "Type syntax"),
        ("Interface Empty\nEnd", "empty"),
        ("Enum Empty\nEnd", "empty"),
    ],
)
def test_advanced_declaration_errors(source: str, message: str) -> None:
    with pytest.raises(TranspilerError, match=message):
        Transpiler().translate(source)


def test_run_rejects_python_source(tmp_path: Path, capsys) -> None:
    source = tmp_path / "program.py"
    source.write_text("print('not ppy')", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        run_ppy_file(str(source))
    assert error.value.code == 2
    assert "not a supported PsuedoPY file" in capsys.readouterr().err


def test_output_commands_protect_source_and_extensions(tmp_path: Path) -> None:
    source = tmp_path / "program.ppy"
    source.write_text('Text("safe")\n', encoding="utf-8")
    with pytest.raises(SystemExit) as compile_error:
        compile_ppy_file(str(source), str(tmp_path / "wrong.bin"))
    assert compile_error.value.code == 2
    with pytest.raises(SystemExit) as transpile_error:
        transpile_ppy_file(str(source), str(source))
    assert transpile_error.value.code == 2
    assert source.read_text(encoding="utf-8") == 'Text("safe")\n'


def test_binding_scope_does_not_leak_out_of_function() -> None:
    namespace, python = execute(
        "Function local()\n"
        "    Let Decimal = (value) => value * 2\n"
        "    Return Decimal(4)\n"
        "End\n"
        "Let local_result = local()\n"
        'Let outer_result = Decimal("1.5")\n'
    )
    assert namespace["local_result"] == 8
    assert namespace["outer_result"] == 1.5
    assert "outer_result = float" in python


def test_formatter_preserves_shadowed_identifier_case_and_formats_new_blocks() -> None:
    formatted = PsuedoPYFormatter().format(
        "let decimal = (value) => value\ninterface sample {\nfield name: string\n}\n"
    )
    assert "Let decimal" in formatted
    assert "Interface sample" in formatted
    assert "Field name: String" in formatted
    assert formatted.rstrip().endswith("End")


def test_formatter_preserves_imports_loop_names_and_constructor_indentation() -> None:
    formatted = PsuedoPYFormatter().format(
        "from decimal import Decimal\n"
        "class sample\n"
        "constructor(value: integer)\n"
        "set this.value to value\n"
        "end\n"
        "end\n"
        "repeat number = 1 to 2\n"
        "text(number)\n"
        "end\n"
    )
    assert "From decimal Import Decimal" in formatted
    assert "        Set This.value To value" in formatted
    assert "Repeat number = 1 To 2" in formatted
    assert "Text(number)" in formatted


def test_multiline_source_map_tracks_each_physical_line() -> None:
    translated = Transpiler().translate(
        "Let value = (\n    2 Pow 3\n) Div 2\nText(value)\n"
    )
    power_line = next(
        number
        for number, text in enumerate(translated.source_map.python_lines, start=1)
        if "**" in text
    )
    division_line = next(
        number
        for number, text in enumerate(translated.source_map.python_lines, start=1)
        if ") //" in text
    )
    assert translated.source_map.original_line_no(power_line) == 2
    assert translated.source_map.original_line_no(division_line) == 3


def test_authoritative_and_compatibility_grammar_maps_stay_synchronized() -> None:
    data_path = Path(__file__).parents[1] / "psuedopy" / "data"
    compatibility = json.loads(
        (data_path / "grammar_map.json").read_text(encoding="utf-8")
    )
    grammar = Grammar.load()
    for spelling, target in compatibility.items():
        spec = grammar.resolve(spelling)
        assert spec is not None
        assert spec.python_target == target


def test_source_map_identity_and_runtime_validation_edges() -> None:
    mapping = SourceMap.identity(["first", "second"])
    assert mapping.original_line_no(2) == 2
    assert mapping.original_source_line(2) == "second"
    assert mapping.original_source_line(99) is None
    assert mapping.generated_source_line(99) is None

    with pytest.raises(TypeError, match="integers"):
        inclusive_range(1, 2.5)
    with pytest.raises(ValueError, match="positive"):
        inclusive_range(1, 3, -1)
    with pytest.raises(ValueError, match="negative"):
        list(repeat_times(-1))
