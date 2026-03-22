"""
VoxLang Interpreter
====================
Executes VoxLang AST with full transparency:
  - Execution trace with scope levels
  - Data width tracking (int-32, float-64, precise-128, string)
  - Symbol table with scope awareness
  - PEMDAS-correct math
  - Linear and quadratic equation solving
  - All formula built-ins
  - Full alias support
"""

import math
from decimal import Decimal, getcontext
from shared.grammar import (
    StoreNode, UpdateNode, RaiseNode, LowerNode,
    OutputNode, InputNode, BuildNode, UseNode, CaptureNode,
    DoThisNode, GoThroughNode, KeepGoingNode, WhenNode,
    ReturnNode, SolveNode, MathBlockNode, CommentNode,
    BinOpNode, UnaryOpNode, CompNode, CollectionNode,
    UseExprNode, CaptureExprNode, IdentNode, LiteralNode,
    FormulaNode, JoinedNode,
)

getcontext().prec = 28


class ReturnSignal(Exception):
    def __init__(self, v): self.value = v


class VoxLangError(Exception):
    pass


class InputNeeded(Exception):
    """
    Raised by the interpreter when an InputNode is hit and no value
    has been pre-supplied. Carries the prompt text and the variable
    name that should receive the answer.
    """
    def __init__(self, prompt: str, var_name: str):
        self.prompt   = prompt
        self.var_name = var_name


# ── Symbol Table Entry ────────────────────────────────────────────────────────
class SymbolEntry:
    def __init__(self, name, value, precise=False, scope="global", line=0):
        self.name    = name
        self.value   = value
        self.precise = precise
        self.scope   = scope
        self.line    = line

    @property
    def vtype(self):
        if isinstance(self.value, bool):    return "bool"
        if isinstance(self.value, Decimal): return "precise"
        if isinstance(self.value, int):     return "num"
        if isinstance(self.value, float):   return "num"
        if isinstance(self.value, str):     return "text"
        if isinstance(self.value, list):    return "collection"
        return "unknown"

    @property
    def width(self):
        if isinstance(self.value, bool):    return "bool-1"
        if isinstance(self.value, Decimal): return "precise-128"
        if isinstance(self.value, int):     return "int-32"
        if isinstance(self.value, float):   return "float-64"
        if isinstance(self.value, str):     return f"string-{len(self.value)*8}"
        if isinstance(self.value, list):    return f"collection-{len(self.value)}"
        return "unknown"


# ── Environment ───────────────────────────────────────────────────────────────
class Environment:
    def __init__(self, parent=None, scope_name="global", is_function=False):
        self.vars        = {}
        self.parent      = parent
        self.scope_name  = scope_name
        self.depth       = (parent.depth + 1) if parent else 0
        self.is_function = is_function

    def get(self, name, line=0):
        if name in self.vars:
            return self.vars[name].value
        if self.parent:
            return self.parent.get(name, line)
        similar = self._find_similar(name)
        hint = f" Did you mean '{similar}'?" if similar else \
               f" Try: store 0 into {name}"
        raise VoxLangError(f"Line {line}: '{name}' is not defined.{hint}")

    def get_entry(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get_entry(name)
        return None

    def _find_similar(self, name):
        all_vars = list(self.vars.keys())
        if self.parent:
            all_vars += list(self.parent.vars.keys())
        for v in all_vars:
            if v.lower() == name.lower() or name.lower() in v.lower():
                return v
        return None

    def set(self, name, value, precise=False, line=0):
        self.vars[name] = SymbolEntry(name, value, precise, self.scope_name, line)

    def assign(self, name, value, line=0):
        """Update an existing variable, walking UP the scope chain.
        Stops at function boundaries."""
        if name in self.vars:
            self.vars[name].value = value
        elif self.parent and not self.is_function:
            self.parent.assign(name, value, line)
        else:
            self.vars[name] = SymbolEntry(name, value, False, self.scope_name, line)

    def has(self, name):
        if name in self.vars:
            return True
        if self.parent:
            return self.parent.has(name)
        return False

    def has_local(self, name):
        if name in self.vars:
            return True
        if self.parent and not self.is_function:
            return self.parent.has_local(name)
        return False

    def all_symbols(self):
        symbols = {}
        if self.parent:
            symbols.update(self.parent.all_symbols())
        symbols.update(self.vars)
        return symbols


# ── Interpreter ───────────────────────────────────────────────────────────────
class Interpreter:
    def __init__(self):
        self.global_env   = Environment(scope_name="global")
        self.output_log   = []
        self.warnings     = []
        self.trace_log    = []
        self.token_log    = []
        self.syntax_log   = []
        self.semantic_log = []
        self.input_hook   = None
        self._scope_depth = 0
        self._line_count  = 0
        # ── symbol_log: captures every variable at the moment it is defined,
        #    including locals inside functions/loops that are destroyed after
        #    execution. Each entry is a dict with all fields needed for the
        #    symbol table. Later entries for the same (name, scope) pair
        #    overwrite earlier ones so we always show the final value.
        self._symbol_log_index = {}   # (name, scope) → index in _symbol_log_list
        self._symbol_log_list  = []   # ordered list of symbol dicts
        self._setup_builtins()

    # ── Record a variable into the persistent symbol log ─────────────────────
    def _record_symbol(self, entry: SymbolEntry):
        """Called every time a variable is set or updated anywhere.
        Skips BuildNode (function definitions) — those are not data variables."""
        if isinstance(entry.value, BuildNode):
            return
        key = (entry.name, entry.scope)
        sym = {
            "name":        entry.name,
            "type":        entry.vtype,
            "value":       self._display(entry.value),
            "scope":       entry.scope,
            "scope_level": self._scope_level(entry.scope),
            "line":        str(entry.line),
        }
        if key in self._symbol_log_index:
            self._symbol_log_list[self._symbol_log_index[key]] = sym
        else:
            self._symbol_log_index[key] = len(self._symbol_log_list)
            self._symbol_log_list.append(sym)

    @staticmethod
    def _scope_level(scope_name: str) -> int:
        if scope_name == "global":
            return 0
        if scope_name.startswith("function:"):
            return 1
        parts = scope_name.split(":")
        return min(len(parts), 4)

    def _setup_builtins(self):
        self.builtins = {
            "length":    lambda a: len(a[0]) if a else 0,
            "reverse":   lambda a: list(reversed(a[0])) if a else [],
            "sum":       lambda a: sum(a[0]) if a else 0,
            "max":       lambda a: max(a[0]) if a else None,
            "min":       lambda a: min(a[0]) if a else None,
            "text":      lambda a: str(a[0]) if a else "",
            "number":    lambda a: float(a[0]) if a else 0,
            "round":     lambda a: round(float(a[0]), int(a[1]) if len(a) > 1 else 0) if a else 0,
            "abs":       lambda a: abs(a[0]) if a else 0,
            "contains":  lambda a: a[1] in a[0] if len(a) >= 2 else False,
            "join":      lambda a: (a[1] if len(a) > 1 else " ").join(str(x) for x in a[0]) if a else "",
            "split":     lambda a: a[0].split(a[1] if len(a) > 1 else " ") if a else [],
            "upper":     lambda a: str(a[0]).upper() if a else "",
            "lower":     lambda a: str(a[0]).lower() if a else "",
            "range":     lambda a: list(range(int(a[0]), int(a[1]) + 1)) if len(a) >= 2 else list(range(int(a[0]))),
            "sqrt":      lambda a: math.sqrt(float(a[0])) if a else 0,
            "power":     lambda a: float(a[0]) ** float(a[1]) if len(a) >= 2 else float(a[0]),
            "floor":     lambda a: math.floor(float(a[0])) if a else 0,
            "ceiling":   lambda a: math.ceil(float(a[0])) if a else 0,
            "factorial": lambda a: math.factorial(int(a[0])) if a else 1,
            "sin":       lambda a: math.sin(math.radians(float(a[0]))) if a else 0,
            "cos":       lambda a: math.cos(math.radians(float(a[0]))) if a else 0,
            "tan":       lambda a: math.tan(math.radians(float(a[0]))) if a else 0,
            "log":       lambda a: math.log(float(a[0]), float(a[1]) if len(a) > 1 else math.e) if a else 0,
            "log10":     lambda a: math.log10(float(a[0])) if a else 0,
            "random":    lambda a: __import__("random").uniform(float(a[0]), float(a[1])) if len(a) >= 2 else __import__("random").random(),
            "is_number": lambda a: (lambda v: (lambda: True, lambda: False)[1]() if not str(v).strip() else
                                    (lambda: True)() if (lambda: (float(str(v).strip()), True))()[1]
                                    else False)(a[0]) if a else False,
        }

    # ── Pre-run warnings ───────────────────────────────────────────────────────
    def precheck(self, ast):
        warnings = []
        defined  = set(self.builtins.keys())

        def scan(nodes, scope):
            for node in nodes:
                if node is None:
                    continue
                if isinstance(node, StoreNode):
                    scope.add(node.name)
                    scan_expr(node.value, scope)
                elif isinstance(node, InputNode):
                    # ── FIX: ask/hear defines the variable it saves into ──────
                    scope.add(node.into)
                elif isinstance(node, UpdateNode):
                    if node.name not in scope:
                        warnings.append(
                            f"⚠️  Line {node.line}: Updating '{node.name}' but it was never defined.\n"
                            f"   Fix: store 0 into {node.name}"
                        )
                    scan_expr(node.value, scope)
                elif isinstance(node, RaiseNode):
                    if node.name not in scope:
                        warnings.append(
                            f"⚠️  Line {node.line}: Raising '{node.name}' but it was never defined.\n"
                            f"   Fix: store 0 into {node.name}"
                        )
                elif isinstance(node, LowerNode):
                    if node.name not in scope:
                        warnings.append(
                            f"⚠️  Line {node.line}: Lowering '{node.name}' but it was never defined.\n"
                            f"   Fix: store 0 into {node.name}"
                        )
                elif isinstance(node, OutputNode):
                    scan_expr(node.value, scope)
                elif isinstance(node, BuildNode):
                    scope.add(node.name)
                    inner = set(scope) | set(node.params)
                    scan(node.body, inner)
                elif isinstance(node, DoThisNode):
                    scan(node.body, set(scope) | {"index"})
                elif isinstance(node, GoThroughNode):
                    if node.iterable not in scope:
                        warnings.append(
                            f"⚠️  Line {node.line}: '{node.iterable}' used in loop but never defined.\n"
                            f"   Fix: store collection 1 and 2 and 3 into {node.iterable}"
                        )
                    scan(node.body, set(scope) | {node.var})
                elif isinstance(node, WhenNode):
                    scan_expr(node.condition, scope)
                    scan(node.then_block, set(scope))
                    scan(node.else_block, set(scope))
                elif isinstance(node, SolveNode):
                    scope.add(node.var)
                    scope.add(node.var + "2")
                elif isinstance(node, CaptureNode):
                    scope.add(node.name)
                elif isinstance(node, MathBlockNode):
                    scan(node.body, scope)

        def scan_expr(node, scope):
            if isinstance(node, IdentNode):
                if node.name not in scope and node.name not in self.builtins:
                    warnings.append(
                        f"⚠️  Line {node.line}: '{node.name}' used but never defined.\n"
                        f"   Fix: store <value> into {node.name}"
                    )
            elif isinstance(node, BinOpNode):
                scan_expr(node.left, scope)
                if node.right:
                    scan_expr(node.right, scope)
            elif isinstance(node, UnaryOpNode):
                scan_expr(node.operand, scope)
            elif isinstance(node, CompNode):
                scan_expr(node.left, scope)
                if node.right:
                    scan_expr(node.right, scope)

        scan(ast, defined)
        return warnings

    # ── Run ────────────────────────────────────────────────────────────────────
    def run(self, ast, env=None):
        self.output_log        = []
        self.warnings          = self.precheck(ast)
        self.trace_log         = []
        self.semantic_log      = []
        self._line_count       = 0
        self._symbol_log_index = {}
        self._symbol_log_list  = []
        env = env or self.global_env

        try:
            self._exec_block(ast, env)
        except ReturnSignal:
            pass
        except InputNeeded:
            self._build_semantic_log(env)
            raise
        except VoxLangError as e:
            self.output_log.append(f"❌ {e}")
            self.trace_log.append(f"❌ ERROR: {e}")
        except Exception as e:
            self.output_log.append(f"❌ Unexpected error: {e}")

        self._build_semantic_log(env)
        return self.warnings + self.output_log

    def _build_semantic_log(self, env):
        self.semantic_log = []
        self.semantic_log.append({
            "header": ["Name", "Type", "Width", "Value", "Scope", "Line"],
            "rows": [
                [
                    e.name,
                    e.vtype,
                    e.width,
                    self._display(e.value),
                    e.scope,
                    str(e.line),
                ]
                for e in env.all_symbols().values()
                if not isinstance(e.value, type(lambda: None))
            ]
        })

    def _exec_block(self, stmts, env):
        for s in stmts:
            if s:
                self._exec(s, env)

    def _exec(self, node, env):
        self._line_count += 1
        scope  = env.scope_name
        indent = "  " * env.depth

        if isinstance(node, StoreNode):
            val = self._eval(node.value, env)
            if node.precise and isinstance(val, (int, float)):
                val = Decimal(str(val))
            if env.has_local(node.name):
                env.assign(node.name, val)
                if node.precise:
                    entry = env.get_entry(node.name)
                    if entry:
                        entry.precise = True
            else:
                env.set(node.name, val, node.precise, getattr(node, "line", 0))
            entry = env.get_entry(node.name)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  STORE    "
                f"{node.name} = {self._display(val)}"
                f"  [{self._width_of(val)}]  scope:{scope}"
            )

        elif isinstance(node, UpdateNode):
            if not env.has(node.name):
                raise VoxLangError(
                    f"Line {node.line}: Cannot update '{node.name}' — not defined.\n"
                    f"   Fix: store 0 into {node.name}"
                )
            val = self._eval(node.value, env)
            env.assign(node.name, val, getattr(node, "line", 0))
            entry = env.get_entry(node.name)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  UPDATE   "
                f"{node.name} → {self._display(val)}  scope:{scope}"
            )

        elif isinstance(node, RaiseNode):
            if not env.has(node.name):
                raise VoxLangError(
                    f"Line {node.line}: Cannot raise '{node.name}' — not defined.\n"
                    f"   Fix: store 0 into {node.name}"
                )
            current = env.get(node.name, getattr(node, "line", 0))
            amount  = self._eval(node.amount, env)
            self._assert_numbers(current, amount, "raise by")
            new_val = current + amount
            env.assign(node.name, new_val)
            entry = env.get_entry(node.name)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  RAISE    "
                f"{node.name}: {self._display(current)} + "
                f"{self._display(amount)} = {self._display(new_val)}  scope:{scope}"
            )

        elif isinstance(node, LowerNode):
            if not env.has(node.name):
                raise VoxLangError(
                    f"Line {node.line}: Cannot lower '{node.name}' — not defined.\n"
                    f"   Fix: store 0 into {node.name}"
                )
            current = env.get(node.name, getattr(node, "line", 0))
            amount  = self._eval(node.amount, env)
            self._assert_numbers(current, amount, "lower by")
            new_val = current - amount
            env.assign(node.name, new_val)
            entry = env.get_entry(node.name)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  LOWER    "
                f"{node.name}: {self._display(current)} - "
                f"{self._display(amount)} = {self._display(new_val)}  scope:{scope}"
            )

        elif isinstance(node, OutputNode):
            val = self._eval(node.value, env)
            out = self._display(val)
            self.output_log.append(out)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  OUTPUT   \"{out}\"  scope:{scope}"
            )

        elif isinstance(node, InputNode):
            if self.input_hook is not None:
                raw = self.input_hook(node.prompt, node.into)
            else:
                raise InputNeeded(node.prompt, node.into)
            result = self._coerce_input(raw, node.into, env)
            if env.has_local(node.into):
                env.assign(node.into, result)
            else:
                env.set(node.into, result)
            entry = env.get_entry(node.into)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  INPUT    "
                f"asked \"{node.prompt}\" → stored in {node.into} = {self._display(result)}"
                f"  [{self._width_of(result)}]  scope:{scope}"
            )

        elif isinstance(node, BuildNode):
            env.set(node.name, node)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  BUILD    "
                f"function '{node.name}' defined  "
                f"params:[{', '.join(node.params)}]  scope:{scope}"
            )

        elif isinstance(node, UseNode):
            self._call(node.name, node.args, env, getattr(node, "line", 0))

        elif isinstance(node, CaptureNode):
            result = self._call(node.func, node.args, env, getattr(node, "line", 0))
            value  = result if result is not None else "nothing"
            if env.has_local(node.name):
                env.assign(node.name, value)
            else:
                env.set(node.name, value)
            entry = env.get_entry(node.name)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  CAPTURE  "
                f"result of {node.func}() → {node.name} = "
                f"{self._display(result)}  scope:{scope}"
            )

        elif isinstance(node, DoThisNode):
            count = int(self._eval(node.count, env))
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  LOOP     "
                f"do this {count} times  scope:{scope}"
            )
            for i in range(count):
                child = Environment(env, scope_name=f"loop:{i+1}")
                child.set("index", i + 1)
                self._record_symbol(child.vars["index"])
                self.trace_log.append(f"{indent}  → iteration {i+1} of {count}")
                self._exec_block(node.body, child)

        elif isinstance(node, GoThroughNode):
            lst = env.get(node.iterable, getattr(node, "line", 0))
            if not isinstance(lst, list):
                lst = list(lst)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  FOREACH  "
                f"go through every {node.var} in {node.iterable} "
                f"({len(lst)} items)  scope:{scope}"
            )
            for i, item in enumerate(lst):
                child = Environment(env, scope_name=f"foreach:{node.iterable}")
                child.set(node.var, item, line=getattr(node, "line", 0))
                self._record_symbol(child.vars[node.var])
                self.trace_log.append(f"{indent}  → {node.var} = {self._display(item)}")
                self._exec_block(node.body, child)

        elif isinstance(node, KeepGoingNode):
            guard = 0
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  WHILE    "
                f"keep going while condition  scope:{scope}"
            )
            while self._eval_cond(node.condition, env):
                guard += 1
                if guard > 10000:
                    raise VoxLangError(
                        "Loop ran more than 10,000 times.\n"
                        "   The condition never became false.\n"
                        "   Check that you are updating the variable inside the loop."
                    )
                self.trace_log.append(f"{indent}  → iteration {guard} (condition true)")
                self._exec_block(node.body, Environment(env, scope_name=f"while:{guard}"))

        elif isinstance(node, WhenNode):
            result = self._eval_cond(node.condition, env)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  WHEN     "
                f"condition → {'true, taking then-branch' if result else 'false, taking otherwise-branch'}  "
                f"scope:{scope}"
            )
            if result:
                self._exec_block(node.then_block, Environment(env, scope_name="when:then"))
            elif node.else_block:
                self._exec_block(node.else_block, Environment(env, scope_name="when:otherwise"))

        elif isinstance(node, ReturnNode):
            val = self._eval(node.value, env)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  RETURN   "
                f"{self._display(val)}  scope:{scope}"
            )
            raise ReturnSignal(val)

        elif isinstance(node, SolveNode):
            result = self._solve(node, env)
            env.set(node.var, result, False, getattr(node, "line", 0))
            entry = env.get_entry(node.var)
            if entry:
                self._record_symbol(entry)
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  SOLVE    "
                f"{node.var} = {self._display(result)}  scope:{scope}"
            )

        elif isinstance(node, MathBlockNode):
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  MATHBLOCK  entering math block  scope:{scope}"
            )
            self._exec_block(node.body, env)

        elif isinstance(node, CommentNode):
            self.trace_log.append(
                f"{indent}Line {self._line_count:>3}  COMMENT  -- {node.text}"
            )

    # ── Function call ──────────────────────────────────────────────────────────
    def _call(self, name, arg_nodes, env, line=0):
        args = [self._eval(a, env) for a in arg_nodes]
        self.trace_log.append(
            f"{'  ' * env.depth}  CALL     {name}("
            f"{', '.join(self._display(a) for a in args)})  scope:{env.scope_name}"
        )
        if name in self.builtins:
            try:
                result = self.builtins[name](args)
                self.trace_log.append(
                    f"{'  ' * env.depth}  RESULT   {name}() → {self._display(result)}"
                )
                return result
            except Exception as e:
                raise VoxLangError(f"Line {line}: Error in '{name}': {e}")

        try:
            fn = env.get_entry(name)
            if fn is None:
                raise VoxLangError(
                    f"Line {line}: '{name}' is not defined.\n"
                    f"   Fix: build {name} using ... done"
                )
            fn = fn.value
        except VoxLangError:
            raise VoxLangError(
                f"Line {line}: '{name}' is not defined.\n"
                f"   Fix: build {name} using ... done"
            )

        if not isinstance(fn, BuildNode):
            raise VoxLangError(f"Line {line}: '{name}' is not a function.")
        if len(args) != len(fn.params):
            raise VoxLangError(
                f"Line {line}: '{name}' needs {len(fn.params)} input(s) "
                f"({', '.join(fn.params)}) but you gave {len(args)}."
            )

        child = Environment(self.global_env, scope_name=f"function:{name}", is_function=True)
        for p, v in zip(fn.params, args):
            child.set(p, v)
            self._record_symbol(child.vars[p])

        try:
            self._exec_block(fn.body, child)
        except ReturnSignal as r:
            return r.value
        return None

    # ── Expression evaluator ───────────────────────────────────────────────────
    def _eval(self, node, env):
        if isinstance(node, LiteralNode):
            return node.value

        if isinstance(node, IdentNode):
            return env.get(node.name, node.line)

        if isinstance(node, UnaryOpNode):
            operand = self._eval(node.operand, env)
            if node.op == "-":
                if not isinstance(operand, (int, float, Decimal)):
                    raise VoxLangError(f"Cannot negate '{operand}' — it is not a number.")
                return -operand
            if node.op == "not":
                return not bool(operand)

        if isinstance(node, BinOpNode):
            l = self._eval(node.left, env)
            r = self._eval(node.right, env) if node.right is not None else None
            if node.op == "+":
                if isinstance(l, str) or isinstance(r, str):
                    return str(l) + str(r)
                return l + r
            if node.op == "-":
                self._assert_numbers(l, r, "-"); return l - r
            if node.op == "*":
                self._assert_numbers(l, r, "*"); return l * r
            if node.op == "/":
                self._assert_numbers(l, r, "/")
                if r == 0:
                    raise VoxLangError(
                        "Division by zero.\n"
                        "   Dividing by zero is undefined in mathematics.\n"
                        "   Change the divisor to a non-zero number."
                    )
                return l / r
            if node.op == "%":
                self._assert_numbers(l, r, "%")
                if r == 0:
                    raise VoxLangError("Modulo by zero is undefined.")
                return l % r
            if node.op == "**":
                self._assert_numbers(l, r, "to the power of"); return l ** r
            if node.op == "<<":  return int(l) << int(r)
            if node.op == ">>":  return int(l) >> int(r)
            if node.op == "percent":
                self._assert_numbers(l, r, "percent of"); return (l / 100) * r

        if isinstance(node, JoinedNode):
            l = self._eval(node.left, env)
            r = self._eval(node.right, env)
            return str(l) + str(r)

        if isinstance(node, CollectionNode):
            return [self._eval(i, env) for i in node.items]

        if isinstance(node, UseExprNode):
            return self._call(node.name, node.args, env)

        if isinstance(node, CaptureExprNode):
            return self._call(node.func, node.args, env)

        if isinstance(node, CompNode):
            return self._eval_cond(node, env)

        if isinstance(node, FormulaNode):
            return self._formula(node, env)

        return None

    # ── Condition evaluator ────────────────────────────────────────────────────
    def _eval_cond(self, node, env):
        if isinstance(node, CompNode):
            if node.op == "and":
                return self._eval_cond(node.left, env) and self._eval_cond(node.right, env)
            if node.op == "or":
                return self._eval_cond(node.left, env) or self._eval_cond(node.right, env)
            l = self._eval(node.left, env)
            if node.op == "is_true":    return bool(l)
            if node.op == "is_false":   return not bool(l)
            if node.op == "is_empty":   return l in ([], "", None, 0)
            if node.op == "is_nothing": return l is None or l == ""
            r = self._eval(node.right, env)
            if node.op == "==": return l == r
            if node.op == "!=": return l != r
            if node.op == ">":
                self._assert_numbers(l, r, "is bigger than"); return l > r
            if node.op == "<":
                self._assert_numbers(l, r, "is smaller than"); return l < r
            if node.op == ">=": return l >= r
            if node.op == "<=": return l <= r
        return bool(self._eval(node, env))

    # ── Formula evaluator ──────────────────────────────────────────────────────
    def _formula(self, node, env):
        kw = {k: self._eval(v, env) for k, v in node.kwargs.items()}
        if node.name == "circle":
            r = float(kw.get("radius", 0))
            return round(math.pi * r * r, 10)
        if node.name == "hypotenuse":
            a = float(kw.get("a", 0)); b = float(kw.get("b", 0))
            return round(math.sqrt(a ** 2 + b ** 2), 10)
        if node.name == "volume_sphere":
            r = float(kw.get("radius", 0))
            return round((4 / 3) * math.pi * r ** 3, 10)
        if node.name == "sqrt":
            x = float(kw.get("x", 0))
            if x < 0:
                raise VoxLangError(
                    f"Cannot take square root of a negative number ({x}).\n"
                    f"   Change the value to 0 or higher."
                )
            return round(math.sqrt(x), 10)
        raise VoxLangError(f"Unknown formula '{node.name}'.")

    # ── Equation solver ────────────────────────────────────────────────────────
    def _solve(self, node, env):
        var    = node.var
        tokens = node.lhs_tokens
        rhs    = self._eval(node.rhs, env)
        coeff2 = 0.0; coeff1 = 0.0; const = 0.0
        i = 0

        def _skip_times(idx):
            """Skip over optional * or 'times' at idx; return new idx."""
            if idx < len(tokens) and tokens[idx].value in ("*", "times"):
                return idx + 1
            return idx

        def _is_coeff_var_squared(idx):
            if tokens[idx].type != "NUMBER": return False
            n = _skip_times(idx + 1)
            if n >= len(tokens) or tokens[n].value != var: return False
            n2 = n + 1
            return n2 < len(tokens) and tokens[n2].value in ("squared", "^")

        def _is_coeff_var(idx):
            if tokens[idx].type != "NUMBER": return False
            n = _skip_times(idx + 1)
            if n >= len(tokens) or tokens[n].value != var: return False
            n2 = n + 1
            return not (n2 < len(tokens) and tokens[n2].value in ("squared", "^"))

        def _len_coeff_var_squared(idx):
            n = _skip_times(idx + 1)
            return (n + 2) - idx   # var + squared

        def _len_coeff_var(idx):
            n = _skip_times(idx + 1)
            return (n + 1) - idx   # var

        while i < len(tokens):
            t = tokens[i]

            # NUMBER [* | times] var [squared | ^]
            if _is_coeff_var_squared(i):
                coeff2 += float(t.value)
                i += _len_coeff_var_squared(i); continue

            # NUMBER [* | times] var
            if _is_coeff_var(i):
                coeff1 += float(t.value)
                i += _len_coeff_var(i); continue

            # var squared
            if t.value == var:
                if i + 1 < len(tokens) and tokens[i+1].value in ("squared", "^"):
                    coeff2 += 1.0; i += 2; continue
                else:
                    coeff1 += 1.0; i += 1; continue

            # plus / +
            if t.value in ("plus", "+") and i + 1 < len(tokens):
                nxt_i = i + 1
                if tokens[nxt_i].type == "NUMBER":
                    if _is_coeff_var_squared(nxt_i):
                        coeff2 += float(tokens[nxt_i].value)
                        i = nxt_i + _len_coeff_var_squared(nxt_i); continue
                    if _is_coeff_var(nxt_i):
                        coeff1 += float(tokens[nxt_i].value)
                        i = nxt_i + _len_coeff_var(nxt_i); continue
                    const += float(tokens[nxt_i].value); i += 2; continue

            # minus / -
            if t.value in ("minus", "-") and i + 1 < len(tokens):
                nxt_i = i + 1
                if tokens[nxt_i].type == "NUMBER":
                    if _is_coeff_var_squared(nxt_i):
                        coeff2 -= float(tokens[nxt_i].value)
                        i = nxt_i + _len_coeff_var_squared(nxt_i); continue
                    if _is_coeff_var(nxt_i):
                        coeff1 -= float(tokens[nxt_i].value)
                        i = nxt_i + _len_coeff_var(nxt_i); continue
                    const -= float(tokens[nxt_i].value); i += 2; continue

            i += 1

        if coeff2 != 0:
            a = coeff2; b = coeff1; c = const - rhs
            discriminant = b ** 2 - 4 * a * c
            if discriminant < 0:
                raise VoxLangError(
                    f"No real solutions (discriminant = {discriminant:.4f}).\n"
                    f"   The equation has no real roots."
                )
            if discriminant == 0:
                result = -b / (2 * a)
                return int(result) if result == int(result) else round(result, 10)
            x1 = (-b + math.sqrt(discriminant)) / (2 * a)
            x2 = (-b - math.sqrt(discriminant)) / (2 * a)
            x1 = int(x1) if x1 == int(x1) else round(x1, 10)
            x2 = int(x2) if x2 == int(x2) else round(x2, 10)
            env.set(var, x1); env.set(var + "2", x2)
            self.output_log.append(f"Two solutions: {var} = {x1} and {var}2 = {x2}")
            return x1

        if coeff1 == 0:
            raise VoxLangError(
                f"Could not find '{var}' in the equation.\n"
                f"   Make sure the variable name matches exactly."
            )
        result = (rhs - const) / coeff1
        return int(result) if result == int(result) else round(result, 10)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _coerce_input(self, raw: str, var_name: str, env) -> object:
        existing = env.get_entry(var_name)
        if existing is not None and isinstance(existing.value, (int, float)):
            try:
                f = float(raw.strip())
                return int(f) if f == int(f) else f
            except (ValueError, AttributeError):
                return raw
        try:
            stripped = raw.strip()
            f = float(stripped)
            return int(f) if f == int(f) else f
        except (ValueError, AttributeError):
            return raw

    def _assert_numbers(self, l, r, op):
        if not isinstance(l, (int, float, Decimal)):
            raise VoxLangError(f"Cannot use '{op}' on '{l}' — it is text, not a number.")
        if r is not None and not isinstance(r, (int, float, Decimal)):
            raise VoxLangError(f"Cannot use '{op}' on '{r}' — it is text, not a number.")

    def _width_of(self, val):
        if isinstance(val, bool):    return "bool-1"
        if isinstance(val, Decimal): return "precise-128"
        if isinstance(val, int):     return "int-32"
        if isinstance(val, float):   return "float-64"
        if isinstance(val, str):     return f"string-{len(val)*8}"
        if isinstance(val, list):    return f"collection-{len(val)}"
        return "unknown"

    def _display(self, val):
        if isinstance(val, list):    return "[" + ", ".join(self._display(v) for v in val) + "]"
        if isinstance(val, bool):    return "true" if val else "false"
        if isinstance(val, Decimal): return str(val)
        if isinstance(val, float) and val == int(val): return str(int(val))
        return str(val) if val is not None else "nothing"