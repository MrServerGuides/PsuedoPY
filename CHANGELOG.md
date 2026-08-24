# Changelog

All notable changes are documented here. This project follows semantic versioning.

## 2.0.0 - 2026-08-24

### Added

- Logical multiline statements with physical-line source mapping
- Scope-aware identifiers so imports and declarations can shadow friendly built-ins
- Typed declarations, typed returns, optional parameters, type aliases, and generics
- `Interface`, `Enum`, `Field`, `Constructor`, `New`, and `Extends`
- TypeScript-style arrays, generic collections, arrow functions, `??`, and ternaries
- C++-style `&&`, `||`, `!`, `++`, `--`, `//` comments, braces, and `For` loops
- `Public`, `Private`, `Protected`, and executable `Static` member modifiers
- `Switch` and `ForEach` control-flow forms

### Changed

- `.ppy` import and declaration bindings now take precedence over friendly aliases
- Generated code uses postponed annotations for forward and generic type names
- The formatter understands bindings, multiline statements, braces, and new blocks
- `run`, `check`, `format`, and `compile` validate PsuedoPY file extensions
- Direct assignments require `Let`, `Var`, `Declare`, `Const`, or `Set`
- Internal generated lines are distinguished from original source in diagnostics

### Fixed

- `Div` and `Pow` now translate correctly across multiline expressions
- `From decimal Import Decimal` no longer becomes the built-in float conversion
- Multiline strings remain opaque to comment, keyword, and brace processing
- Loop, function-parameter, import, class, and exception bindings respect scope

## 1.0.0 - 2026-08-24

### Added

- Structural explicit-`End` parser with branch and nesting validation
- Case-insensitive language keywords with token-aware expression translation
- Inclusive, descending, iterable, fixed-count, and forever repeat loops
- Constants, annotations, unpacking, attribute/index assignment, classes, and `This`
- Functions, async functions, generators, exceptions, resources, and pattern matching
- Friendly conversion, collection, numeric, input, and output built-ins
- Source-mapped diagnostics with optional generated-Python debugging
- Persistent block-aware REPL with expression values and namespace reset
- `check`, `format --check`, `transpile`, portable `compile`, and compiled `run`
- Program argument forwarding and local-module import behavior
- Version-2 `.cppy` format with strict decoding and integrity verification
- Shared structured grammar and configurable custom grammar support
- Cross-platform CI, wheel installation test, examples, and release documentation

### Changed

- Replaced direct keyword substitution with structural parsing
- Replaced Python `marshal` artifacts with portable UTF-8 containers
- Standardized the primary executable as `psuedopy`; kept `pseudopy` and `ppyx`
- Made package installation reject paths, URLs, whitespace, and pip flags
- Raised the release version from 0.1.0 to 1.0.0

### Fixed

- Packaged wheels now include grammar resources
- `Ask` in assignments, `Return`, `From ... Import`, and documented repeat syntax
- Real `End` semantics, multiline REPL collection, source diagnostics, and formatter
- The package-manager test now mocks `subprocess.run` correctly
