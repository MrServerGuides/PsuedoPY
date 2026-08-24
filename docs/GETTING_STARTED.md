# Getting started

## Requirements

- Python 3.10 or newer
- A terminal
- A virtual environment is strongly recommended

## Installation

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On macOS or Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Confirm the installation:

```console
psuedopy --version
```

## A small calculator

Save this as `calculator.ppy`:

```psuedopy
Function calculate(left, operator, right)
    Match operator
        Case "+"
            Return left + right
        Case "-"
            Return left - right
        Case "*"
            Return left * right
        Case "/"
            When right = 0
                Raise ValueError("Cannot divide by zero")
            End
            Return left / right
        Default
            Raise ValueError("Unknown operator")
    End
End

Try
    Let left = Decimal(Ask("First number: "))
    Let operator = Ask("Operator (+, -, *, /): ")
    Let right = Decimal(Ask("Second number: "))
    Text("Result: " + String(calculate(left, operator, right)))
Catch ValueError As error
    Text("Input error: " + String(error))
End
```

Check and run it:

```console
psuedopy check calculator.ppy
psuedopy run calculator.ppy
```

## Interactive mode

Start the REPL with `psuedopy repl`. Expressions display their values. A block is
held until its matching `End` arrives.

```text
PsuedoPY >>> Let values = [1, 2, 3]
PsuedoPY >>> Sum(values)
6
PsuedoPY >>> Repeat value In values
          ... Text(value Pow 2)
          ... End
1
4
9
```

Use `:help` for REPL commands and `cancel` to discard an unfinished block.

## Next steps

Read the [language reference](LANGUAGE_REFERENCE.md), then explore the programs in
the repository's `examples` directory.
