#!/usr/bin/env python3
from __future__ import annotations
import re
import sys
from typing import List

_RE_SINGLE_COMMENT = re.compile(r'//(.*)$')
_RE_MULTI_COMMENT_START = re.compile(r'/\*')
_RE_MULTI_COMMENT_END = re.compile(r'\*/')
_RE_DECLARATION = re.compile(r'^\s*(VAR|INT|STRING|FLOAT|BOOL)\b', re.IGNORECASE)
_RE_SET = re.compile(r'^\s*SET\b', re.IGNORECASE)
_RE_AND = re.compile(r'&&')
_RE_OR = re.compile(r'\|\|')
_RE_NOT = re.compile(r'(?<![!=])!(?!=)')
_RE_TRUE = re.compile(r'\btrue\b', re.IGNORECASE)
_RE_FALSE = re.compile(r'\bfalse\b', re.IGNORECASE)
_RE_NULL = re.compile(r'\bnull\b', re.IGNORECASE)
_RE_PRINT = re.compile(r'^\s*PRINT\b\s*(.*)$', re.IGNORECASE)
_RE_INPUT = re.compile(r'^\s*(READ|INPUT)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*$', re.IGNORECASE)
_RE_IF_THEN = re.compile(r'^\s*(ELSE\s+IF|ELIF|IF)\b(.*?)(?:\bTHEN\b|\:|\{)?\s*$', re.IGNORECASE)
_RE_ELSE = re.compile(r'^\s*ELSE\b\s*(?:\{)?\s*$', re.IGNORECASE)
_RE_END_BLOCK = re.compile(r'^\s*(END(IF|FUNCTION|FUNC|FOR|WHILE|IF)|ENDFOR|ENDWHILE|ENDFUNCTION|})\s*$', re.IGNORECASE)
_RE_CLOSING_BRACE_INLINE = re.compile(r'\}\s*(.*)')
_RE_WHILE = re.compile(r'^\s*WHILE\b(.*?)(?:\bDO\b|\:|\{)?\s*$', re.IGNORECASE)
_RE_FOR = re.compile(r'^\s*FOR\s+([A-Za-z_]\w*)\s*=\s*(.+?)\s+TO\s+(.+?)(?:\s+STEP\s+(.+?))?\s*(?:\{)?\s*$', re.IGNORECASE)
_RE_FUNCTION = re.compile(r'^\s*(FUNCTION|FUNC|VOID)\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*(?:\{)?\s*$', re.IGNORECASE)
_RE_RETURN = re.compile(r'^\s*RETURN\b\s*(.*)$', re.IGNORECASE)
_RE_TRAILING_BRACE = re.compile(r'\{\s*$')

def replace_not(expr: str) -> str:
    return _RE_NOT.sub(' not ', expr)

class Transpiler:
    def __init__(self, indent_unit: str = '    '):
        self.indent_unit = indent_unit
        self.indent_level = 0
        self.in_multiline_comment = False

    def _emit(self, content: str) -> str:
        if content.strip() == '':
            return ''
        return f'{self.indent_unit * self.indent_level}{content}'

    def transpile_lines(self, src_lines: List[str]) -> List[str]:
        out_lines: List[str] = []
        self.indent_level = 0
        self.in_multiline_comment = False

        for line in src_lines:
            raw = line.rstrip('\n')
            processed = ''

            if self.in_multiline_comment:
                end_m = _RE_MULTI_COMMENT_END.search(raw)
                if end_m:
                    before = raw[: end_m.start()]
                    processed = '"""' + before.strip() if before.strip() else '"""'
                    self.in_multiline_comment = False
                else:
                    processed = raw
                out_lines.append(self._emit(processed))
                continue

            start_m = _RE_MULTI_COMMENT_START.search(raw)
            if start_m:
                end_m = _RE_MULTI_COMMENT_END.search(raw, start_m.end())
                if end_m:
                    comment_text = raw[start_m.end() : end_m.start()].strip()
                    processed = f'"""{comment_text}"""'
                    out_lines.append(self._emit(processed))
                    continue
                else:
                    rest = raw[start_m.end() :].strip()
                    processed = '"""' + rest if rest else '"""'
                    self.in_multiline_comment = True
                    out_lines.append(self._emit(processed))
                    continue

            sc = _RE_SINGLE_COMMENT.search(raw)
            if sc:
                code_before = raw[: sc.start()].rstrip()
                comment_part = sc.group(1).rstrip()
                if code_before:
                    processed_code = code_before
                    processed_comment = f'  # {comment_part}'
                    processed = processed_code + processed_comment
                else:
                    processed = '#' + comment_part
                out_lines.append(self._emit(processed))
                continue

            stripped = raw.strip()
            if stripped == '':
                out_lines.append('')
                continue

            cb_inline = _RE_CLOSING_BRACE_INLINE.match(stripped)
            if cb_inline:
                remainder = cb_inline.group(1).strip()
                self.indent_level = max(0, self.indent_level - 1)
                if remainder.upper().startswith('ELSE'):
                    processed = 'else:'
                    out_lines.append(self._emit(processed))
                    self.indent_level += 1
                    continue
                else:
                    stripped = remainder

            if _RE_END_BLOCK.match(stripped) or stripped == '}':
                self.indent_level = max(0, self.indent_level - 1)
                out_lines.append('')
                continue

            pm = _RE_PRINT.match(raw)
            if pm:
                arg = pm.group(1).strip()
                if arg == '':
                    processed = 'print()'
                else:
                    if arg.startswith('(') and arg.endswith(')'):
                        processed = 'print' + arg
                    else:
                        s = arg
                        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")) or s.startswith('f"') or s.startswith("f'") or s.startswith('('):
                            processed = f'print({s})' if not s.startswith('(') else f'print{s}'
                        else:
                            processed = f'print({s})'
                out_lines.append(self._emit(processed))
                continue

            im = _RE_INPUT.match(stripped)
            if im:
                varname = im.group(2)
                processed = f'{varname} = input()'
                out_lines.append(self._emit(processed))
                continue

            fm = _RE_FUNCTION.match(raw)
            if fm:
                func_name = fm.group(2)
                args = fm.group(3).strip()
                args = args if args else ''
                processed = f'def {func_name}({args}):'
                out_lines.append(self._emit(processed))
                self.indent_level += 1
                continue

            rm = _RE_RETURN.match(raw)
            if rm:
                val = rm.group(1).strip()
                processed = f'return {val}' if val else 'return'
                out_lines.append(self._emit(processed))
                continue

            ifm = _RE_IF_THEN.match(raw)
            if ifm:
                kw = ifm.group(1).upper()
                cond = ifm.group(2).strip()
                if cond.endswith('{'):
                    cond = cond[:-1].strip()
                if kw.startswith('ELSE'):
                    if kw.startswith('ELSE') and 'IF' in kw:
                        processed = f'elif {cond}:'
                    else:
                        processed = 'else:'
                elif kw == 'ELIF':
                    processed = f'elif {cond}:'
                else:
                    processed = f'if {cond}:'
                processed = _RE_AND.sub(' and ', processed)
                processed = _RE_OR.sub(' or ', processed)
                processed = replace_not(processed)
                processed = _RE_TRUE.sub('True', processed)
                processed = _RE_FALSE.sub('False', processed)
                processed = _RE_NULL.sub('None', processed)
                out_lines.append(self._emit(processed))
                if processed.rstrip().endswith(':'):
                    self.indent_level += 1
                continue

            if _RE_ELSE.match(raw):
                processed = 'else:'
                out_lines.append(self._emit(processed))
                self.indent_level += 1
                continue

            wm = _RE_WHILE.match(raw)
            if wm:
                cond = wm.group(1).strip()
                if cond.endswith('{'):
                    cond = cond[:-1].strip()
                processed = f'while {cond}:'
                processed = _RE_AND.sub(' and ', processed)
                processed = _RE_OR.sub(' or ', processed)
                processed = replace_not(processed)
                processed = _RE_TRUE.sub('True', processed)
                processed = _RE_FALSE.sub('False', processed)
                processed = _RE_NULL.sub('None', processed)
                out_lines.append(self._emit(processed))
                self.indent_level += 1
                continue

            fm2 = _RE_FOR.match(raw)
            if fm2:
                varname = fm2.group(1)
                start_expr = fm2.group(2).strip()
                end_expr = fm2.group(3).strip()
                step_expr = fm2.group(4)
                if step_expr:
                    step_expr = step_expr.strip()
                else:
                    step_expr = '1'
                range_end = f'({end_expr}) + 1'
                processed = f'for {varname} in range({start_expr}, {range_end}, {step_expr}):'
                processed = _RE_AND.sub(' and ', processed)
                processed = _RE_OR.sub(' or ', processed)
                processed = replace_not(processed)
                processed = _RE_TRUE.sub('True', processed)
                processed = _RE_FALSE.sub('False', processed)
                processed = _RE_NULL.sub('None', processed)
                out_lines.append(self._emit(processed))
                self.indent_level += 1
                continue

            if _RE_DECLARATION.match(raw):
                decl_removed = _RE_DECLARATION.sub('', raw, count=1).lstrip()
                decl_removed = _RE_TRUE.sub('True', decl_removed)
                decl_removed = _RE_FALSE.sub('False', decl_removed)
                decl_removed = _RE_NULL.sub('None', decl_removed)
                processed = decl_removed
                processed = _RE_SET.sub('', processed)
                out_lines.append(self._emit(processed))
                continue

            if _RE_SET.match(raw):
                processed = _RE_SET.sub('', raw, count=1).lstrip()
                processed = _RE_TRUE.sub('True', processed)
                processed = _RE_FALSE.sub('False', processed)
                processed = _RE_NULL.sub('None', processed)
                out_lines.append(self._emit(processed))
                continue

            line_after = raw
            line_after = _RE_AND.sub(' and ', line_after)
            line_after = _RE_OR.sub(' or ', line_after)
            line_after = replace_not(line_after)
            line_after = _RE_TRUE.sub('True', line_after)
            line_after = _RE_FALSE.sub('False', line_after)
            line_after = _RE_NULL.sub('None', line_after)

            if _RE_TRAILING_BRACE.search(line_after):
                line_after = _RE_TRAILING_BRACE.sub('', line_after).rstrip()
                if not line_after.rstrip().endswith(':'):
                    line_after = line_after.rstrip() + ':'
                out_lines.append(self._emit(line_after))
                self.indent_level += 1
                continue

            if line_after.rstrip().endswith(':'):
                out_lines.append(self._emit(line_after))
                self.indent_level += 1
                continue

            out_lines.append(self._emit(line_after))

        return out_lines

    def transpile(self, source: str) -> str:
        src_lines = source.splitlines(keepends=False)
        out_lines = self.transpile_lines(src_lines)
        return '\n'.join(out_lines) + '\n'

def run_file(path: str) -> None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
    except Exception as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        sys.exit(2)

    transpiler = Transpiler()
    py_src = transpiler.transpile(src)
    globs = {'__name__': '__main__', '__file__': path}
    try:
        code_obj = compile(py_src, path, 'exec')
        exec(code_obj, globs, globs)
    except Exception:
        raise

def main():
    if len(sys.argv) < 3 or sys.argv[1] != 'run':
        print("Usage: psuedopy run <file.ppy>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[2]
    run_file(path)

if __name__ == '__main__':
    main()
