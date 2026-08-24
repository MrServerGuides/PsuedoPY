# PsuedoPY language reference

## Lexical rules

- Files use UTF-8 and normally end in `.ppy`.
- Language keywords are case-insensitive and the formatter writes canonical casing.
- Identifiers and strings retain their original case.
- `#` begins a comment outside a string.
- Python string forms, including multiline strings, are supported.
- Reserved words are translated only as language syntax, never after attribute access
  such as `object.Text`.

Blocks are explicit. Every block opener requires a matching `End`; optional labels
such as `End Function` and `End Repeat` are validated. Source indentation is for
humans. The parser generates correct Python indentation from block structure.

## Values and expressions

PsuedoPY uses Python's runtime values and expression rules: integers, decimal
numbers, strings, booleans, `None`, lists, tuples, sets, dictionaries, slicing,
calls, comprehensions, and f-strings are available.

| PsuedoPY | Python meaning |
| --- | --- |
| `True`, `Yes`, `On` | true boolean |
| `False`, `No`, `Off` | false boolean |
| `None`, `Null`, `Nil`, `Nothing` | no value |
| `And`, `Or`, `Not` | boolean operators |
| `In`, `Is` | membership and identity |
| `Div`, `Mod`, `Pow` | `//`, `%`, `**` |
| `<>` | not equal |

A single `=` at the top level of a `When` or `While` condition means equality.
`==` remains valid. Keyword arguments inside calls are not changed.

Friendly built-ins include:

| PsuedoPY | Python |
| --- | --- |
| `Text(...)` | `print(...)` |
| `Ask(...)` | `input(...)` |
| `Length(value)` | `len(value)` |
| `Integer(value)` | `int(value)` |
| `Decimal(value)` | `float(value)` |
| `String(value)` | `str(value)` |
| `Boolean(value)` | `bool(value)` |
| `Range(...)` | `range(...)` |
| `Minimum`, `Maximum`, `Sum`, `Sorted`, `TypeOf` | corresponding Python built-ins |

## Variables and constants

```psuedopy
Let name = "Ada"
Var count: int = 0
Set count To count + 1
Set count = count + 1
Const MAX_ATTEMPTS = 3
```

`Let`, `Var`, and `Declare` introduce normal Python bindings. `Set` emphasizes
reassignment and supports either `=` or `To`. Destructuring, indexed assignments,
attribute assignments, and type annotations are supported.

`Const` requires a simple name and prevents later direct reassignment in the same
module, function, or class scope. Python objects referenced by a constant may still
be mutable.

## Conditions

```psuedopy
When score >= 90 Then
    Text("A")
ElseIf score >= 80
    Text("B")
Otherwise
    Text("Keep learning")
End
```

`Then` is optional. Aliases include `If`, `Elif`, and `Else`.

## Loops

```psuedopy
Repeat item In collection
    Text(item)
End

Repeat i = 1 To 10 Step 2
    Text(i)
End

Repeat 3 Times
    Text("again")
End

While queue
    Let item = queue.pop()
End
```

Numeric `To` ranges are inclusive. The default step is `1`; descending ranges
require a negative step. A zero step and a step in the wrong direction produce a
clear runtime error. `Break` and `Continue` are valid inside loops.

`While Forever` and `Repeat Forever` create intentional infinite loops.

## Functions and generators

```psuedopy
Function greet(name: str = "world")
    Return "Hello, " + name
End Function

Function countdown(start)
    Repeat value = start To 1 Step -1
        Yield value
    End
End
```

Aliases `Func`, `Define`, `Def`, and `Procedure` are accepted. `Async Function`
and `Await` map to Python async behavior. `Return` and `Yield` are checked so they
cannot appear outside a function.

## Classes

```psuedopy
Class Counter
    Function __init__(This, start=0)
        This.value = start
    End

    Method increment(This)
        This.value += 1
        Return This.value
    End
End
```

`This` means Python's `self`. Python inheritance and decorators are available.

## Exceptions and resources

```psuedopy
Try
    Using open("data.txt", encoding="utf-8") As handle
        Let content = handle.read()
    End
Catch OSError As error
    Text(error)
Finally
    Text("Finished")
End
```

`Raise` and `Throw` raise exceptions. A bare `Catch` catches `Exception`, not
process-control exceptions such as `KeyboardInterrupt` or `SystemExit`.

## Pattern matching

Pattern matching requires Python 3.10 or newer:

```psuedopy
Match response.status_code
    Case 200
        Text("Success")
    Case 404
        Text("Missing")
    Default
        Text("Other status")
End
```

## Imports

```psuedopy
Import json
Import pathlib As paths
From datetime Import datetime As DateTime
```

`Include` and `Use` are aliases for `Import`. Module paths, names inside an import
clause, and module attributes are not rewritten. Language keywords remain reserved;
alias a colliding imported name, for example `From package Import Text As PackageText`.

## Python interoperability boundary

Unrecognized statements and expressions are preserved as Python-compatible syntax.
This makes the Python standard library, installed packages, decorators,
comprehensions, type annotations, and advanced expressions available. It also means
PsuedoPY is not a security sandbox and follows Python's runtime semantics.

## Reserved aliases

The authoritative keyword list is stored in `psuedopy/data/keywords.json`. The
formatter, expression translator, and custom grammar loader all consume this file.
