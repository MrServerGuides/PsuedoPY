# PsuedoPY language reference

## Lexical rules

- Files use UTF-8 and normally end in `.ppy`.
- Language keywords are case-insensitive and the formatter writes canonical casing.
- Identifiers and strings retain their original case.
- `#` and C++-style `//` begin comments outside a string.
- Python string forms, including multiline strings, are supported.
- Reserved words are translated only as language syntax, never after attribute access
  such as `object.Text`.

Blocks are explicit. Every block opener requires a matching `End`; optional labels
such as `End Function` and `End Repeat` are validated. Source indentation is for
humans. The parser generates correct Python indentation from block structure.
Standalone `}` is accepted as `End`, and a recognized block may end its header in
`{`. Trailing semicolons are optional.

Parenthesized, bracketed, braced, backslash-continued, and multiline-string
statements are parsed as logical units. Operators on continuation lines are fully
translated, and diagnostics retain their original physical line numbers.

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
| `&&`, `||`, `!` | C++-style boolean operators |
| `condition ? yes : no` | conditional expression |
| `left ?? fallback` | null-coalescing expression |
| `(value) => expression` | arrow function |
| `New Type(...)` | construct an instance |

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

Friendly built-ins are scope-aware. An exact imported, declared, parameter, loop,
class, or exception binding takes precedence. This works without an alias:

```psuedopy
From decimal Import Decimal
Let precise = Decimal("3.1415926535")
```

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
Raw `name = value` statements are rejected; use a declaration or `Set`. Postfix
`value++` and `value--` are available as statement-level increment/decrement forms.

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

`ForEach` is an iterable-loop spelling. A restricted C-style loop is also accepted
when it can be represented safely as a range:

```psuedopy
For (Let index = 0; index < 10; index++)
    Text(index)
End
```

The initializer must bind one name, the condition must compare that same name, and
the update must be `++`, `--`, `+= step`, or `-= step`.

## Types

Types are preserved as Python annotations and use postponed evaluation, similar to
TypeScript's erased type model. They document APIs and are available to development
tools; they do not insert automatic runtime type checks.

```psuedopy
Type Identifier = Integer | String

Let names: String[] = ["Ada", "Grace"]
Let scores: Map<String, Integer> = {"Ada": 98}
Let nickname: Optional<String> = None

Function find(id: Identifier, limit?: Integer) Returns String | None
    Return String(id)
End
```

Built-in type spellings include `Integer`, `Decimal`, `String`, `Boolean`, `Number`,
`Any`, `Unknown`, `Never`, `Void`, `Array`, `List`, `Map`, `Record`, `Set`, `Tuple`,
and `Optional`. Both `Integer[]` and `Array<Integer>` are accepted. Generic type
parameters on functions, classes, and interfaces are accepted and erased at runtime.

## Functions and generators

```psuedopy
Function greet(name: String = "world") Returns String
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
    Constructor(start: Integer)
        Set This.value To start
    End

    Method increment(This) Returns Integer
        This.value++
        Return This.value
    End
End
```

`This` means the current instance. `New Counter(0)` constructs a value. Inheritance
uses either `Class Child Extends Parent` or `Class Child(Parent)`.

Interfaces contain typed fields and compile to structural protocols. Enums contain
constant members:

```psuedopy
Interface Named
    Field name: String
End

Enum Status
    Const READY = "ready"
    Const DONE = "done"
End
```

`Public`, `Private`, and `Protected` are documentation modifiers because Python does
not enforce member visibility. `Static Function` creates an executable static method.

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

`Switch` is an alternative spelling for `Match`.

## Imports

```psuedopy
Import json
Import pathlib As paths
From datetime Import datetime As DateTime
```

`Include` and `Use` are aliases for `Import`. Module paths and attributes are not
rewritten. Imported bindings override friendly built-ins in their scope, while
structural words such as `End` remain reserved.

## Python interoperability boundary

Expressions support runtime literals, calls, attributes, indexing, slicing,
comprehensions, and f-strings needed to use imported modules. Expression-call
statements such as `output.write_text(...)` are allowed. Python-only block statements
and raw assignments are rejected, and `ppyx run` never accepts `.py` input.

The backend still executes with the permissions of Python and is not a security
sandbox. Imported modules and installed packages are trusted executable code.

## Reserved aliases

The authoritative keyword list is stored in `psuedopy/data/keywords.json`. The
formatter, expression translator, and custom grammar loader all consume this file.
