"""
shared/optimizer.py
====================
VoxLang — Phase 5: Code Optimization

Three passes over the TAC instruction list:
  1. Constant Folding      — LOAD_CONST + STORE → direct STORE
  2. Dead Store Elimination — STORE to var never read downstream → flagged
  3. Redundant Load Elim.  — duplicate LOAD_VAR of same var → reuse temp
"""

from .codegen import TACInstruction


class Optimizer:
    def __init__(self):
        self.opt_log: list[dict] = []

    def optimize(self, instructions: list[TACInstruction]) -> list[TACInstruction]:
        self.opt_log = []
        after = self._constant_folding(instructions)
        after = self._dead_store_elim(after)
        after = self._redundant_load_elim(after)
        return after

    # ── Pass 1: Constant Folding ──────────────────────────────────────────
    def _constant_folding(self, instrs):
        result, i, folded = [], 0, 0
        while i < len(instrs):
            ins = instrs[i]
            if (ins.op == "LOAD_CONST"
                    and i + 1 < len(instrs)
                    and instrs[i+1].op == "STORE"
                    and instrs[i+1].arg1 == ins.result):
                store = instrs[i+1]
                folded_ins = TACInstruction(
                    op="STORE", arg1=ins.arg1, result=store.result
                )
                folded_ins._folded = True
                result.append(folded_ins)
                self.opt_log.append({
                    "pass":   "Constant Folding",
                    "action": "folded",
                    "detail": (f"Eliminated temp '{ins.result}': "
                               f"LOAD_CONST({ins.arg1}) + STORE "
                               f"→ STORE {ins.arg1} → {store.result}")
                })
                folded += 1
                i += 2
                continue
            result.append(ins)
            i += 1

        if folded == 0:
            self.opt_log.append({
                "pass": "Constant Folding", "action": "kept",
                "detail": "No constant-folding opportunities found."
            })
        return result

    # ── Pass 2: Dead Store Elimination ───────────────────────────────────
    def _dead_store_elim(self, instrs):
        read_vars = set()
        for ins in instrs:
            if ins.op in ("LOAD_VAR", "OUTPUT", "FOREACH") and ins.arg1:
                read_vars.add(str(ins.arg1))
            if ins.op == "FOREACH" and ins.arg2:
                read_vars.add(str(ins.arg2))
            if ins.op == "CALL" and ins.arg1:
                read_vars.add(str(ins.arg1))

        result, found_dead = [], False
        for ins in instrs:
            if ins.op == "STORE" and str(ins.result) not in read_vars:
                ins._dead = True
                found_dead = True
                self.opt_log.append({
                    "pass":   "Dead Store Elimination",
                    "action": "dead",
                    "detail": (f"'{ins.result}' is stored but never queried — "
                               f"flagged as dead (kept for symbol table integrity)")
                })
            result.append(ins)

        if not found_dead:
            self.opt_log.append({
                "pass": "Dead Store Elimination", "action": "kept",
                "detail": "All stored variables are used — nothing to eliminate."
            })
        return result

    # ── Pass 3: Redundant Load Elimination ───────────────────────────────
    def _redundant_load_elim(self, instrs):
        result, last_load, eliminated = [], {}, 0
        for ins in instrs:
            if ins.op == "STORE":
                last_load.pop(str(ins.result), None)
                result.append(ins)
                continue
            if ins.op == "LOAD_VAR":
                key = str(ins.arg1)
                if key in last_load:
                    reuse = last_load[key]
                    self.opt_log.append({
                        "pass":   "Redundant Load Elimination",
                        "action": "redundant",
                        "detail": (f"LOAD_VAR '{ins.arg1}' → '{ins.result}' is redundant — "
                                   f"'{reuse}' already holds the value. Reusing.")
                    })
                    for f in instrs:
                        if f.arg1 == ins.result: f.arg1 = reuse
                        if f.result == ins.result: f.result = reuse
                    eliminated += 1
                    continue
                last_load[key] = ins.result
            result.append(ins)

        if eliminated == 0:
            self.opt_log.append({
                "pass": "Redundant Load Elimination", "action": "kept",
                "detail": "No redundant loads detected."
            })
        return result