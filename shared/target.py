"""
shared/target.py
=================
VoxLang — Phase 6: Target Code Generation

Translates optimized TAC into two readable targets side by side:
  A) Stack Machine (pseudo-assembly using symbol table offsets)
  B) Python Equivalent (preserves "coding with common sense" spirit)
"""

from .codegen import TACInstruction


class TargetGenerator:
    def __init__(self, symbol_table: dict):
        self.symbol_table  = symbol_table
        self.stack_code:   list[str] = []
        self.python_code:  list[str] = []
        self.target_log:   list[dict] = []

    def generate(self, instructions: list[TACInstruction]):
        self.stack_code  = []
        self.python_code = []
        self.target_log  = []

        self.stack_code.append(";── VoxLang Stack Machine ─────────────")
        self.python_code.append("# VoxLang → Python ─────────────────────")

        for ins in instructions:
            self._emit(ins)

        self._build_log()

    def _emit(self, ins: TACInstruction):
        dead   = getattr(ins, '_dead',   False)
        dead_c = "  ; ← dead store" if dead else ""
        dead_p = "  # ← dead store" if dead else ""

        op = ins.op

        if op == "STORE":
            entry  = self.symbol_table.get(str(ins.result))
            offset = entry.offset if entry else "?"
            dtype  = entry.dtype  if entry else "?"
            val    = ins.arg1

            # Format value for Python
            if entry and dtype == "word" and isinstance(val, str) and not val.startswith("t"):
                py_val = f'"{val}"'
            elif isinstance(val, list):
                py_val = "[" + ", ".join(str(v) for v in val) + "]"
            else:
                py_val = str(val) if val is not None else "None"

            asm = f"ISTORE  addr[{offset}]  ; {ins.result} ({dtype}){dead_c}"
            py  = f"{ins.result} = {py_val}{dead_p}"
            self._add(asm, py)

        elif op == "LOAD_CONST":
            val = ins.arg1
            if isinstance(val, str) and not val.startswith(("'", '"')):
                asm = f"PUSH_SCONST \"{val}\""
                py  = f"# load \"{val}\" → {ins.result}"
            elif isinstance(val, (int, float)):
                asm = f"PUSH_ICONST {val}"
                py  = f"# load {val} → {ins.result}"
            else:
                asm = f"PUSH_CONST  {val}"
                py  = f"# load {val} → {ins.result}"
            self._add(asm, py)

        elif op == "LOAD_VAR":
            entry  = self.symbol_table.get(str(ins.arg1))
            offset = entry.offset if entry else "?"
            asm = f"ILOAD   addr[{offset}]  ; load {ins.arg1}"
            py  = f"_tmp = {ins.arg1}"
            self._add(asm, py)

        elif op == "INPUT":
            asm = f"READ_INPUT  → addr[{self.symbol_table.get(str(ins.result), type('', (), {'offset': '?'})()).offset}]  ; {ins.result}"
            py  = f"{ins.result} = input({ins.arg1!r})"
            self._add(asm, py)

        elif op == "OUTPUT":
            asm = f"PRINT_TOP              ; output to console"
            py  = f"print(_tmp)"
            self._add(asm, py)

        elif op == "ADD":
            asm = f"IADD    {ins.arg1}, {ins.arg2} → {ins.result}"
            py  = f"{ins.result} = {ins.arg1} + {ins.arg2}"
            self._add(asm, py)

        elif op == "SUB":
            asm = f"ISUB    {ins.arg1}, {ins.arg2} → {ins.result}"
            py  = f"{ins.result} = {ins.arg1} - {ins.arg2}"
            self._add(asm, py)

        elif op == "DEF_FUNC":
            asm = f"DEF     {ins.arg1}({ins.arg2})"
            py  = f"def {ins.arg1}({ins.arg2}):"
            self._add(asm, py)

        elif op == "CALL":
            asm = f"CALL    {ins.arg1}  ; {ins.arg2}"
            py  = f"{ins.arg1}(...)  # {ins.arg2}"
            self._add(asm, py)

        elif op == "LOOP_N":
            asm = f"LOOP    {ins.arg1} times"
            py  = f"for _i in range({ins.arg1}):"
            self._add(asm, py)

        elif op == "LOOP_END":
            asm = f"LOOP_END"
            py  = f"# end loop"
            self._add(asm, py)

        elif op == "FOREACH":
            asm = f"FOREACH {ins.arg1} IN {ins.arg2}"
            py  = f"for {ins.arg1} in {ins.arg2}:"
            self._add(asm, py)

        elif op == "FOREACH_END":
            asm = "FOREACH_END"
            py  = "# end foreach"
            self._add(asm, py)

        elif op == "WHILE_START":
            asm = "WHILE_START"
            py  = "while <condition>:"
            self._add(asm, py)

        elif op == "WHILE_END":
            asm = "WHILE_END"
            py  = "# end while"
            self._add(asm, py)

        elif op == "WHEN_START":
            asm = "CMP_JUMP  <condition>"
            py  = "if <condition>:"
            self._add(asm, py)

        elif op == "OTHERWISE":
            asm = "JMP_ELSE"
            py  = "else:"
            self._add(asm, py)

        elif op == "WHEN_END":
            asm = "WHEN_END"
            py  = "# end if"
            self._add(asm, py)

        elif op == "SOLVE":
            asm = f"SOLVE   {ins.arg1}  → {ins.result}"
            py  = f"{ins.result} = solve_for('{ins.arg1}', equation)"
            self._add(asm, py)

        elif op in ("MATH_BLOCK_START", "MATH_BLOCK_END"):
            asm = op
            py  = f"# {op.lower().replace('_', ' ')}"
            self._add(asm, py)

        elif op == "COMMENT":
            asm = f"; {ins.arg1}"
            py  = f"# {ins.arg1}"
            self._add(asm, py)

    def _add(self, asm, py):
        self.stack_code.append(f"  {asm}")
        self.python_code.append(f"  {py}")

    def _build_log(self):
        max_len = max(len(self.stack_code), len(self.python_code))
        for i in range(max_len):
            asm = self.stack_code[i]  if i < len(self.stack_code)  else ""
            py  = self.python_code[i] if i < len(self.python_code) else ""
            self.target_log.append({"asm": asm, "python": py})