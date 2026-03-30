"""
shared/codegen.py
==================
VoxLang — Phase 4: Intermediate Code Generation (TAC)

Works with the ORIGINAL VoxLang grammar nodes:
  StoreNode, UpdateNode, RaiseNode, LowerNode,
  OutputNode, BuildNode, UseNode, DoThisNode,
  GoThroughNode, KeepGoingNode, WhenNode, SolveNode,
  MathBlockNode, CommentNode, BinOpNode, etc.

Emits Three-Address Code (TAC) instructions.
Each instruction: op, arg1, arg2, result
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TACInstruction:
    op:      str
    arg1:    Any  = None
    arg2:    Any  = None
    result:  Any  = None
    _dead:   bool = False
    _folded: bool = False


class CodeGenerator:
    def __init__(self):
        self._temp  = 0
        self.instructions: list[TACInstruction] = []
        self.ir_log:       list[dict] = []

    def _t(self) -> str:
        """Generate a named temp register — uses a readable prefix."""
        name = f"t{self._temp}"
        self._temp += 1
        return name

    def _log(self, op, arg1, arg2, result, comment, group=None):
        self.ir_log.append({
            "op":      op,
            "arg1":    str(arg1),
            "arg2":    str(arg2),
            "result":  str(result),
            "comment": comment,
            "group":   group or "",   # used by frontend for visual grouping
        })

    def generate(self, ast: list) -> list[TACInstruction]:
        self.instructions = []
        self.ir_log       = []
        self._temp        = 0
        for node in ast:
            if node is not None:
                self._gen(node)
        return self.instructions

    def _emit(self, op, arg1=None, arg2=None, result=None, comment="", group=None):
        ins = TACInstruction(op=op, arg1=arg1, arg2=arg2, result=result)
        self.instructions.append(ins)
        self._log(
            op,
            arg1   if arg1   is not None else "—",
            arg2   if arg2   is not None else "—",
            result if result is not None else "—",
            comment,
            group,
        )
        return ins

    def _gen(self, node):
        t = type(node).__name__

        # ── Variable assignment ───────────────────────────────────────────────
        if t == "StoreNode":
            val = self._val(node.value)
            # Emit a single ASSIGN that reads directly as: name = value
            self._emit("ASSIGN",
                       arg1=val,
                       result=node.name,
                       comment=f"store {val} into {node.name}",
                       group="assign")

        elif t == "UpdateNode":
            val = self._val(node.value)
            self._emit("ASSIGN",
                       arg1=val,
                       result=node.name,
                       comment=f"update {node.name} to {val}",
                       group="assign")

        elif t == "RaiseNode":
            amt = self._val(node.amount)
            res = self._t()
            self._emit("ADD",
                       arg1=node.name,
                       arg2=amt,
                       result=res,
                       comment=f"{node.name} + {amt}",
                       group="math")
            self._emit("ASSIGN",
                       arg1=res,
                       result=node.name,
                       comment=f"raise {node.name} by {amt}",
                       group="math")

        elif t == "LowerNode":
            amt = self._val(node.amount)
            res = self._t()
            self._emit("SUB",
                       arg1=node.name,
                       arg2=amt,
                       result=res,
                       comment=f"{node.name} - {amt}",
                       group="math")
            self._emit("ASSIGN",
                       arg1=res,
                       result=node.name,
                       comment=f"lower {node.name} by {amt}",
                       group="math")

        # ── Output ────────────────────────────────────────────────────────────
        elif t == "OutputNode":
            val = self._val(node.value)
            self._emit("OUTPUT",
                       arg1=val,
                       comment=f"print {val} to console",
                       group="io")

        # ── Input ─────────────────────────────────────────────────────────────
        elif t == "InputNode":
            self._emit("INPUT",
                       arg1=f'"{node.prompt}"',
                       result=node.into,
                       comment=f"ask user → store answer in {node.into}",
                       group="io")

        # ── Function definition ───────────────────────────────────────────────
        elif t == "BuildNode":
            params = ", ".join(node.params) if node.params else "no params"
            self._emit("FUNC_DEF",
                       arg1=node.name,
                       arg2=params,
                       result=f"{len(node.body)} stmts",
                       comment=f"define '{node.name}' — params: {params}",
                       group=f"func:{node.name}")
            # Emit the function body indented under the same group
            for s in node.body:
                if s:
                    self._gen_in_group(s, group=f"func:{node.name}")
            self._emit("FUNC_END",
                       arg1=node.name,
                       comment=f"end of function '{node.name}'",
                       group=f"func:{node.name}")

        # ── Function call ─────────────────────────────────────────────────────
        elif t == "UseNode":
            args = ", ".join(self._val(a) for a in node.args) if node.args else "—"
            self._emit("CALL",
                       arg1=node.name,
                       arg2=args,
                       comment=f"call {node.name}({args})",
                       group="call")

        elif t == "CaptureNode":
            args = ", ".join(self._val(a) for a in node.args) if node.args else "—"
            self._emit("CALL",
                       arg1=node.func,
                       arg2=args,
                       result=node.name,
                       comment=f"{node.name} = result of {node.func}({args})",
                       group="call")

        # ── Counted loop ──────────────────────────────────────────────────────
        elif t == "DoThisNode":
            count = self._val(node.count)
            self._emit("LOOP_START",
                       arg1=count,
                       arg2="index",
                       comment=f"repeat {count} times — index counts 1 to {count}",
                       group="loop")
            for s in node.body:
                if s:
                    self._gen_in_group(s, group="loop")
            self._emit("LOOP_END",
                       comment=f"end repeat ({count} times)",
                       group="loop")

        # ── For-each loop ─────────────────────────────────────────────────────
        elif t == "GoThroughNode":
            self._emit("FOREACH_START",
                       arg1=node.var,
                       arg2=node.iterable,
                       comment=f"for each {node.var} in {node.iterable}",
                       group=f"foreach:{node.iterable}")
            for s in node.body:
                if s:
                    self._gen_in_group(s, group=f"foreach:{node.iterable}")
            self._emit("FOREACH_END",
                       arg1=node.var,
                       arg2=node.iterable,
                       comment=f"end for each {node.var} in {node.iterable}",
                       group=f"foreach:{node.iterable}")

        # ── While loop ────────────────────────────────────────────────────────
        elif t == "KeepGoingNode":
            cond = self._val(node.condition) if hasattr(node, "condition") else "condition"
            self._emit("WHILE_START",
                       arg1=cond,
                       comment=f"keep going while {cond} is true",
                       group="while")
            for s in node.body:
                if s:
                    self._gen_in_group(s, group="while")
            self._emit("WHILE_END",
                       comment="end while loop",
                       group="while")

        # ── Conditional ───────────────────────────────────────────────────────
        elif t == "WhenNode":
            cond = self._val(node.condition) if hasattr(node, "condition") else "condition"
            self._emit("IF",
                       arg1=cond,
                       comment=f"if {cond}",
                       group="when")
            for s in node.then_block:
                if s:
                    self._gen_in_group(s, group="when")
            if node.else_block:
                self._emit("ELSE",
                           comment="otherwise branch",
                           group="when")
                for s in node.else_block:
                    if s:
                        self._gen_in_group(s, group="when")
            self._emit("END_IF",
                       comment="end when/if block",
                       group="when")

        # ── Equation solver ───────────────────────────────────────────────────
        elif t == "SolveNode":
            self._emit("SOLVE",
                       arg1="equation",
                       result=node.var,
                       comment=f"solve equation for '{node.var}' — result stored in {node.var}",
                       group="math")

        # ── Math block ────────────────────────────────────────────────────────
        elif t == "MathBlockNode":
            self._emit("MATH_START",
                       comment="begin math block",
                       group="math")
            for s in node.body:
                if s:
                    self._gen_in_group(s, group="math")
            self._emit("MATH_END",
                       comment="end math block",
                       group="math")

        # ── Comment ───────────────────────────────────────────────────────────
        elif t == "CommentNode":
            self._emit("COMMENT",
                       arg1=f"-- {node.text}",
                       comment="source comment")

    def _gen_in_group(self, node, group: str):
        """Generate IR for a node and force all emitted rows into the given group.
        We do this by saving the current ir_log length, generating normally,
        then patching any newly added rows to carry the group label."""
        before = len(self.ir_log)
        self._gen(node)
        for row in self.ir_log[before:]:
            if not row.get("group"):
                row["group"] = group

    def _val(self, node) -> str:
        """Produce a human-readable string for any expression node —
        uses real variable names throughout, no temp registers."""
        if node is None:
            return "—"
        t = type(node).__name__
        if t == "LiteralNode":
            v = node.value
            if isinstance(v, str):
                return f'"{v}"'
            if isinstance(v, bool):
                return "true" if v else "false"
            return str(v)
        if t == "IdentNode":
            return node.name
        if t == "BinOpNode":
            l = self._val(node.left)
            r = self._val(node.right) if node.right else ""
            op_label = {
                "+": "+", "-": "-", "*": "×", "/": "÷",
                "%": "mod", "**": "^", "percent": "% of",
            }.get(node.op, node.op)
            return f"({l} {op_label} {r})"
        if t == "JoinedNode":
            return f'({self._val(node.left)} joined with {self._val(node.right)})'
        if t == "CollectionNode":
            items = ", ".join(self._val(i) for i in node.items)
            return f"[{items}]"
        if t == "UnaryOpNode":
            return f"{node.op} {self._val(node.operand)}"
        if t == "FormulaNode":
            kwargs = ", ".join(f"{k}={self._val(v)}" for k, v in node.kwargs.items())
            return f"{node.name}({kwargs})"
        if t == "UseExprNode":
            args = ", ".join(self._val(a) for a in node.args) if node.args else ""
            return f"{node.name}({args})"
        if t == "CompNode":
            op_label = {
                "==": "==", "!=": "!=", ">": ">", "<": "<",
                ">=": ">=", "<=": "<=", "and": "and", "or": "or",
                "is_true": "is true", "is_false": "is false",
                "is_empty": "is empty", "is_nothing": "is nothing",
            }.get(node.op, node.op)
            l = self._val(node.left)
            r = self._val(node.right) if node.right else ""
            if r:
                return f"{l} {op_label} {r}"
            return f"{l} {op_label}"
        return str(t)