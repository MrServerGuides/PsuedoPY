# PsuedoPY

PsuedoPY is a typed, executable pseudocode programming language with a Python
backend. It combines readable `End` blocks, TypeScript-inspired types, selected
C++ conveniences, and explicit access to Python's standard library and packages.

```psuedopy
Function classify(score)
    When score >= 90
        Return "excellent"
    ElseIf score >= 75
        Return "passed"
    Otherwise
        Return "keep practicing"
    End
End

Repeat student In ["Ada", "Linus", "Grace"]
    Text(student + ": " + classify(88))
End
```

PsuedoPY parses the source, validates its block structure, generates source-mapped
Python, and executes it on Python 3.10 or newer. Language keywords are
case-insensitive; strings, comments, non-keyword identifiers, import clauses, and
attributes are preserved.

## Highlights

- Explicit `End` blocks with automatic generated indentation
- Logical multiline expressions with accurate physical-line diagnostics
- Typed variables/functions, aliases, optional parameters, and generic annotations
- Classes, interfaces, enums, constructors, inheritance, and static members
- `When`, `ElseIf`, `Otherwise`, `While`, and three forms of `Repeat`
- `ForEach`, C-style `For`, `Switch`, pattern matching, and exception handling
- Friendly operators such as `And`, `Or`, `Not`, `Div`, `Mod`, `Pow`, and `<>`
- `&&`, `||`, `!`, `++`, `--`, arrows, ternaries, `??`, braces, and `//` comments
- Beginner-friendly built-ins such as `Text`, `Ask`, `Length`, `Integer`, and `Sum`
- Scope-aware names: imports such as `decimal.Decimal` never collide with aliases
- Python modules and PyPI packages through normal import syntax
- Source-mapped diagnostics that point back to `.ppy` lines
- Persistent REPL with expression output and reliable multi-line blocks
- Formatter, syntax checker, Python transpiler, and portable `.cppy` artifacts
- Validated, integrity-checked compiled containers instead of unsafe marshal data

## Install

Clone the repository and install it into a virtual environment:

```console
git clone https://github.com/MrServerGuides/PsuedoPY.git
cd PsuedoPY
python -m venv .venv
```

Activate the environment, then install:

```console
python -m pip install -e .
psuedopy --version
```

The short command `ppyx` is recommended for daily use. The aliases `psuedopy` and
`pseudopy` are installed as well.

## First program

Create `hello.ppy`:

```psuedopy
Let name = Ask("What is your name? ")
Text("Hello, " + name + "!")

Repeat number = 1 To 3
    Text("Count " + String(number))
End
```

Types and modern expressions remain readable:

```psuedopy
Type Identifier = Integer | String

Interface Named
    Field name: String
End

Class Student
    Constructor(name: String, scores: Integer[])
        Set This.name To name
        Set This.scores To scores
    End

    Function average(This) Returns Decimal
        Return Sum(This.scores) / Length(This.scores)
    End
End

Let label = (score: Integer) => score >= 75 ? "passed" : "retry"
Let student = New Student("Ada", [92, 88, 95])
Text(student.name + ": " + label(Integer(student.average())))
```

Run it:

```console
psuedopy run hello.ppy
```

Indentation in source files is recommended for readability but block meaning comes
from `End`. Run `psuedopy format hello.ppy` to canonicalize both casing and
indentation.

## Commands

```console
psuedopy run program.ppy -- argument1 argument2
psuedopy check program.ppy
psuedopy format program.ppy
psuedopy format --check program.ppy
psuedopy transpile program.ppy -o program.py
psuedopy compile program.ppy -o program.cppy
psuedopy run program.cppy
psuedopy repl
psuedopy install requests
```

Use `psuedopy --help` or see the [CLI reference](docs/CLI_REFERENCE.md).

## Repeat forms

```psuedopy
# Inclusive: 1, 2, 3, 4, 5
Repeat i = 1 To 5
    Text(i)
End

# Inclusive countdown
Repeat i = 5 To 1 Step -1
    Text(i)
End

# Iterate through any Python iterable
Repeat item In ["red", "green", "blue"]
    Text(item)
End

# Fixed count
Repeat 3 Times
    Text("Again")
End
```

## Python interoperability

```psuedopy
From pathlib Import Path
Import json

Let data = {"ready": True, "items": [1, 2, 3]}
Let output = Path("result.json")
output.write_text(json.dumps(data), encoding="utf-8")
Text(output.resolve())
```

PsuedoPY programs have the same permissions as the Python process that runs them.
They are not sandboxed. Only run trusted programs and only install trusted packages.
The `run` command accepts only `.ppy` and integrity-checked `.cppy` inputs; it does
not execute `.py` source files. Use the explicit `transpile` command only when you
need to inspect backend output.

## Documentation

- [Getting started](docs/GETTING_STARTED.md)
- [Language reference](docs/LANGUAGE_REFERENCE.md)
- [CLI reference](docs/CLI_REFERENCE.md)
- [Configuration](docs/CONFIGURATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Development

```console
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest --cov=psuedopy
python -m build
```

CI tests the package on Python 3.10–3.13 across Windows, macOS, and Linux and also
installs the built wheel to ensure packaged grammar resources are present.

## Project status

Version 2.0 defines the typed/modern language surface and `.cppy` format version 2. See
[CHANGELOG.md](CHANGELOG.md) for release details. The historical project spelling
`PsuedoPY` is retained as the official brand; the correctly spelled `pseudopy`
command alias is provided for convenience.

## License

MIT. See [LICENCE](LICENCE).
