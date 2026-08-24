# Architecture

## Design goals

PsuedoPY is a source-to-source language with explicit pseudocode structure and
Python runtime compatibility. The implementation favors deterministic translation,
clear source diagnostics, safe artifact decoding, and one shared grammar across all
developer tools.

## Compilation pipeline

```text
.ppy UTF-8 source
        |
        v
Grammar loader -------- keywords.json / optional custom grammar
        |
        v
Structural parser ----- validates End blocks, branches, scopes, constants
        |
        v
Expression translator - token-aware aliases; preserves strings/comments/attributes
        |
        v
Generated Python + source map
        |
        +---- check ------ Python compile only
        +---- run -------- compile + execute in script namespace
        +---- transpile -- write readable .py
        +---- compile ---- write portable .cppy v2 container
        +---- REPL ------- persistent namespace + expression display
```

## Modules

| Module | Responsibility |
| --- | --- |
| `grammar.py` | Validate and load the packaged or custom grammar |
| `parser.py` | Structural blocks, statements, expression token rewriting, validation |
| `transpiler.py` | Assemble generated source, runtime imports, and source mappings |
| `compiler.py` | Python compilation and portable artifact encoding/validation |
| `runtime.py` | Inclusive ranges and validated fixed-count repeats |
| `formatter.py` | Canonical grammar casing and structural indentation |
| `exceptions.py` | Source-mapped, terminal-aware diagnostics |
| `repl.py` | Interactive buffering, commands, state, and expression evaluation |
| `main.py` | File-oriented application services and execution environment |
| `cli.py` | Argument parsing, configuration, exit-code behavior |

## Structural parser

The parser maintains an explicit stack of block frames. Frames record their opener,
generated indentation, current branch state, and lexical scope. Middle branches are
validated against the active frame, so `Otherwise` cannot follow `Try`, `Catch`
cannot follow `Finally`, and `Case` cannot appear outside `Match`.

Every meaningful source line produces one generated line. Runtime-helper imports add
a small mapped prefix when required. This predictable relationship lets runtime and
compile errors map back to the original source.

## Grammar

`keywords.json` is the canonical language data source. Every entry declares its
Python target, syntactic category, canonical formatter spelling, aliases, and block
behavior. `grammar_map.json` remains packaged as a backwards-compatible simple-map
format for custom grammar authors.

## Portable artifacts

`.cppy` version 2 deliberately avoids `marshal` and pickle. The binary layout is:

```text
5-byte magic: P P Y 00 02
4-byte big-endian manifest length
UTF-8 JSON manifest
UTF-8 generated Python payload
UTF-8 original PsuedoPY payload
```

The loader enforces size limits, validates every length, rejects trailing bytes,
checks SHA-256 hashes, verifies the format, and checks language-major compatibility
before compiling the UTF-8 payload.

## Trust model

Parsing and artifact decoding avoid unsafe deserialization. Executing a program is
intentionally equivalent to executing Python and is not sandboxed. Package
installation invokes pip without a shell and rejects option-like or path-like input,
but packages themselves remain third-party executable code.

## Compatibility policy

- Python 3.10 and newer are supported.
- Language 1.x keeps documented source syntax backward compatible.
- `.cppy` readers reject unknown format versions.
- Breaking language or artifact changes require a major version bump.
