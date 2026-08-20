# PsuedoPY Architecture

## Overview

PsuedoPY is a transpiled language layered on top of Python. It provides a
friendly syntax while preserving full interoperability with the Python
ecosystem.

The toolchain is organised into distinct compiler stages:

1. Lexical analysis and transpilation
2. Source mapping and error mapping
3. Execution or bytecode compilation
4. Interactive REPL
5. Package management bridge
6. Source formatting

## Data Flow

.ppy source
    │
    ▼
Transpiler.translate()
    │
    ├─ Python source
    ├─ Original source
    └─ SourceMap
         │
         ├── run_ppy_file(): compile + exec
         ├── compile_ppy_file(): code object + marshal → .cppy
         └── REPL: compile + exec in persistent namespace