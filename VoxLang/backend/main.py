"""
VoxLang – FastAPI Backend
==========================
Full 6-phase compiler pipeline.
Phases 1-3 use the original Lexer, Parser, and Interpreter unchanged.
Phases 4-6 add IR generation, optimization, and target code on top.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from shared.config      import CORS_ORIGINS, HOST, PORT, validate
from shared.grammar     import Lexer, Parser
from shared.interpreter import Interpreter, InputNeeded
from shared.codegen     import CodeGenerator
from shared.optimizer   import Optimizer
from shared.target      import TargetGenerator
from backend.stt import transcribe
from backend.llm import (
    voice_to_code, correct_transcript,
    explain_code, suggest_completion, chat_about_voxlang,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    errors = validate()
    if errors:
        print("⚠️  Config warnings:")
        for e in errors:
            print(f"   • {e}")
    else:
        print("✅  VoxLang backend ready — full 6-phase compiler")
    yield


app = FastAPI(title="VoxLang API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
)


class TranscribeRequest(BaseModel):
    audio_b64: str
    mime_type: str = "audio/webm"

class GenerateRequest(BaseModel):
    transcript: str
    context:    str = ""

class RunRequest(BaseModel):
    code:         str
    input_values: list = []

class ExplainRequest(BaseModel):
    code: str

class SuggestRequest(BaseModel):
    partial_code: str

class ChatMessage(BaseModel):
    role:    str
    content: str

class ChatRequest(BaseModel):
    question:     str
    code_context: str = ""
    history:      list[ChatMessage] = []


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "language": "VoxLang"}


@app.post("/reset")
async def reset_session():
    return {"status": "reset", "message": "Session reset."}


@app.post("/transcribe")
async def transcribe_audio(req: TranscribeRequest):
    try:
        audio_bytes = base64.b64decode(req.audio_b64)
        result      = await transcribe(audio_bytes, req.mime_type)
        return {
            "transcript":      result.text,
            "confidence":      result.confidence,
            "low_confidence":  result.low_confidence,
            "provider":        result.provider,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate")
async def generate_code(req: GenerateRequest):
    try:
        code = voice_to_code(req.transcript, req.context)
        return {"code": code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/correct")
async def correct_stt(req: GenerateRequest):
    try:
        corrected = correct_transcript(req.transcript)
        return {"corrected": corrected}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run")
async def run_code(req: RunRequest):
    try:
        # ── PHASE 1: LEXICAL ANALYSIS ─────────────────────────────────────────
        lexer  = Lexer(req.code)
        tokens = lexer.tokenize()

        token_log = []
        for t in tokens:
            if t.type != "EOF":
                cat, label, sub, width = _classify_token(t)
                token_log.append({
                    "cat":   cat,
                    "kilos": label,
                    "sub":   sub,
                    "value": str(t.value),
                    "line":  getattr(t, "line", "—"),
                    "width": width,
                })

        # ── PHASE 2: SYNTAX ANALYSIS ──────────────────────────────────────────
        parser     = Parser(tokens)
        ast        = parser.parse()
        syntax_log = _build_syntax_log(ast)

        # ── PHASE 3: SEMANTIC ANALYSIS + EXECUTION ────────────────────────────
        interp      = Interpreter()
        input_queue = list(req.input_values)
        input_index = [0]

        def input_hook(prompt: str, var_name: str) -> str:
            idx = input_index[0]
            if idx < len(input_queue):
                input_index[0] += 1
                return input_queue[idx]
            raise InputNeeded(prompt, var_name)

        interp.input_hook = input_hook

        try:
            output = interp.run(ast)
        except InputNeeded as inp:
            return {
                "needs_input":  True,
                "input_prompt": inp.prompt,
                "input_var":    inp.var_name,
                "output":       interp.output_log,
                "success":      None,
                "token_log":    token_log,
                "syntax_log":   syntax_log,
                "semantic_log": _build_semantic_log(interp),
                "trace_log":    interp.trace_log,
                "ir_log":       [],
                "opt_log":      [],
                "target_log":   [],
            }

        # ── PHASE 4: INTERMEDIATE CODE GENERATION ─────────────────────────────
        ir_log = []
        opt_log = []
        target_log = []
        try:
            cg = CodeGenerator()
            ir = cg.generate(ast)
            ir_log = cg.ir_log
        except Exception:
            ir = []

        # ── PHASE 5: OPTIMIZATION ─────────────────────────────────────────────
        try:
            opt    = Optimizer()
            opt_ir = opt.optimize(ir)
            opt_log = opt.opt_log
        except Exception:
            opt_ir = ir

        # ── PHASE 6: TARGET CODE GENERATION ──────────────────────────────────
        try:
            sym_map = _build_sym_map(interp)
            tg = TargetGenerator(sym_map)
            tg.generate(opt_ir)
            target_log = tg.target_log
        except Exception:
            pass

        return {
            "needs_input":  False,
            "output":       output,
            "success":      True,
            "token_log":    token_log,
            "syntax_log":   syntax_log,
            "semantic_log": _build_semantic_log(interp),
            "trace_log":    interp.trace_log,
            "ir_log":       ir_log,
            "opt_log":      opt_log,
            "target_log":   target_log,
        }

    except SyntaxError as e:
        return {
            "needs_input":  False,
            "output":       [str(e)],
            "success":      False,
            "error":        "syntax",
            "token_log":    [],
            "syntax_log":   {
                "nodes": [{"rule": "SYNTAX ERROR", "line": "—", "detail": str(e), "status": f"✗ {e}"}],
                "recovery": [{"line": "—", "message": f"Syntax error: {e}", "recovery": "parsing halted"}],
            },
            "semantic_log": [],
            "trace_log":    [],
            "ir_log":       [],
            "opt_log":      [],
            "target_log":   [],
        }
    except Exception as e:
        return {
            "needs_input":  False,
            "output":       [str(e)],
            "success":      False,
            "error":        "runtime",
            "token_log":    [],
            "syntax_log":   {"nodes": [], "recovery": []},
            "semantic_log": [],
            "trace_log":    [f"❌ {e}"],
            "ir_log":       [],
            "opt_log":      [],
            "target_log":   [],
        }


@app.post("/explain")
async def explain(req: ExplainRequest):
    try:
        explanation = explain_code(req.code)
        return {"explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/suggest")
async def suggest(req: SuggestRequest):
    try:
        suggestion = suggest_completion(req.partial_code)
        return {"suggestion": suggestion}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        answer  = chat_about_voxlang(
            question=req.question,
            code_context=req.code_context,
            history=history if history else None,
        )
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/voice")
async def voice_pipeline(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "audio":
                audio_b64 = msg.get("data",   "")
                mime_type = msg.get("mime",    "audio/webm")
                context   = msg.get("context", "")
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    result      = await transcribe(audio_bytes, mime_type)
                    await ws.send_json({
                        "type":           "transcript",
                        "text":           result.text,
                        "confidence":     result.confidence,
                        "low_confidence": result.low_confidence,
                    })
                    if not result.text.strip():
                        continue
                    transcript = result.text
                    if result.low_confidence:
                        transcript = correct_transcript(transcript)
                    code = voice_to_code(transcript, context)
                    await ws.send_json({"type": "code", "code": code})
                except Exception as e:
                    await ws.send_json({"type": "error", "message": str(e)})
            elif msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

# ── KILOS token classification ────────────────────────────────────────────────
_KW_OPERATORS = {
    "is", "not", "bigger", "smaller", "than", "equal", "at", "least", "most",
    "and", "or", "also", "either", "plus", "minus", "times", "divided",
    "modulo", "mod", "remainder", "joined",
}
_KW_SEPARATORS = {
    "then", "done", "with", "using", "in", "from", "to", "by", "of",
    "into", "every",
}
_SEP_VALUES = {"(", ")", "[", "]", "{", "}", ",", ";", ":"}
_OP_VALUES  = {"+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="}


def _classify_token(t):
    tp  = t.type
    val = str(t.value).lower()
    if tp == "NUMBER":
        if isinstance(t.value, int):
            return "L", "Literal", "Integer", "int-32"
        return "L", "Literal", "Float", "float-64"
    if tp == "STRING":
        return "L", "Literal", "String", f"str-{len(str(t.value))*8}b"
    if tp == "BOOL":
        return "L", "Literal", "Boolean", "bool-1"
    if tp == "IDENT":
        return "I", "Identifier", "ID", f"{len(str(t.value))*8}b"
    if tp == "OP":
        if str(t.value) in _SEP_VALUES:
            return "S", "Separator", str(t.value), "—"
        return "O", "Operator", str(t.value), "—"
    if tp == "KEYWORD":
        if val in _KW_OPERATORS:
            return "O", "Operator", val, "—"
        if val in _KW_SEPARATORS:
            return "S", "Separator", val, "—"
        if val in ("true", "false", "nothing"):
            return "L", "Literal", "Boolean", "bool-1"
        return "K", "Keyword", "KW", "—"
    if str(t.value) in _SEP_VALUES:
        return "S", "Separator", str(t.value), "—"
    if str(t.value) in _OP_VALUES:
        return "O", "Operator", str(t.value), "—"
    return "K", "Keyword", str(tp), "—"


def _token_width(t):
    _, _, _, w = _classify_token(t)
    return w


# ── Syntax log ────────────────────────────────────────────────────────────────
_NODE_HUMAN = {
    "StoreNode":      "Store (variable assign)",
    "UpdateNode":     "Update (reassign)",
    "RaiseNode":      "Raise (increment)",
    "LowerNode":      "Lower (decrement)",
    "OutputNode":     "Output (print)",
    "InputNode":      "Input (ask/hear)",
    "BuildNode":      "Build (function def)",
    "UseNode":        "Use (function call)",
    "CaptureNode":    "Capture (call → var)",
    "DoThisNode":     "Do This (counted loop)",
    "GoThroughNode":  "Go Through (foreach)",
    "KeepGoingNode":  "Keep Going (while loop)",
    "WhenNode":       "When (if / elif / else)",
    "ReturnNode":     "Return",
    "SolveNode":      "Solve (equation)",
    "MathBlockNode":  "Math Block",
    "AddToNode":      "Add To (collection)",
    "RemoveFromNode": "Remove From (collection)",
}


def _node_detail(node) -> str:
    name = type(node).__name__
    if name in ("StoreNode", "UpdateNode", "RaiseNode", "LowerNode"):
        return f"→ {getattr(node, 'name', '?')}"
    if name == "BuildNode":
        params = getattr(node, "params", [])
        return f"{getattr(node,'name','?')}({', '.join(params)})"
    if name == "UseNode":
        return f"{getattr(node,'name','?')}()"
    if name == "CaptureNode":
        return f"{getattr(node,'name','?')} ← {getattr(node,'func','?')}()"
    if name == "InputNode":
        return f"→ {getattr(node,'into','?')}"
    if name == "SolveNode":
        return f"→ {getattr(node,'var','?')}"
    if name == "GoThroughNode":
        return f"{getattr(node,'var','?')} in {getattr(node,'iterable','?')}"
    if name == "DoThisNode":
        body = getattr(node, "body", [])
        return f"{len(body)} stmt{'s' if len(body) != 1 else ''}"
    if name == "KeepGoingNode":
        body = getattr(node, "body", [])
        return f"{len(body)} stmt{'s' if len(body) != 1 else ''}"
    if name == "WhenNode":
        then = len(getattr(node, "then_block", []))
        els  = len(getattr(node, "else_block", []))
        return f"then:{then} else:{els}"
    return ""


def _build_syntax_log(ast) -> dict:
    log      = []
    recovery = []
    for i, node in enumerate(ast or []):
        if node is None:
            recovery.append({
                "line":     i + 1,
                "message":  f"Unparseable statement at position {i+1} — panic mode recovery triggered",
                "recovery": "skipped token(s), resumed parsing",
            })
            continue
        name   = type(node).__name__
        label  = _NODE_HUMAN.get(name, name)
        detail = _node_detail(node)
        log.append({
            "rule":   label,
            "line":   getattr(node, "line", "—"),
            "detail": detail,
            "status": "✓ valid",
        })
    return {"nodes": log, "recovery": recovery}


# ── Scope helpers ─────────────────────────────────────────────────────────────
def _scope_level(scope_name: str) -> int:
    """Convert a scope name to a nesting depth integer.
    global=0, function:X=1, loop/when/foreach=2+
    """
    if scope_name == "global":
        return 0
    if scope_name.startswith("function:"):
        return 1
    parts = scope_name.split(":")
    return min(len(parts), 4)


# ── Byte size helpers ─────────────────────────────────────────────────────────
def _type_bytes(entry) -> int:
    from decimal import Decimal
    v = entry.value
    if isinstance(v, bool):    return 1
    if isinstance(v, Decimal): return 8
    if isinstance(v, int):     return 4
    if isinstance(v, float):   return 4
    if isinstance(v, str):     return max(1, len(v))
    if isinstance(v, list):    return len(v) * 8
    return 4


def _type_width_label(entry) -> str:
    from decimal import Decimal
    v = entry.value
    if isinstance(v, bool):    return "1 B  (bool)"
    if isinstance(v, Decimal): return "8 B  (double)"
    if isinstance(v, int):     return "4 B  (int)"
    if isinstance(v, float):   return "4 B  (float)"
    if isinstance(v, str):
        n = max(1, len(v))
        return f"{n} B  (char[{n}])"
    if isinstance(v, list):
        n = len(v) * 8
        return f"{n} B  (ptr[{len(v)}])"
    return "4 B  (unknown)"


def _estimate_from_type(vtype: str, value_str: str) -> tuple:
    """Estimate byte size and label for a local variable that no longer
    exists in the live environment. Uses only the type string and the
    display value — no hardcoded language assumptions."""
    if vtype == "bool":
        return 1, "1 B  (bool)"
    if vtype == "precise":
        return 8, "8 B  (double)"
    if vtype == "num":
        if "." in str(value_str):
            return 4, "4 B  (float)"
        return 4, "4 B  (int)"
    if vtype == "text":
        n = max(1, len(str(value_str)))
        return n, f"{n} B  (char[{n}])"
    if vtype == "collection":
        try:
            s = str(value_str).strip()
            count = s.count(",") + 1 if s not in ("[]", "", "nothing") else 0
            n = count * 8
            return n, f"{n} B  (ptr[{count}])"
        except Exception:
            return 8, "8 B  (collection)"
    return 4, "4 B  (unknown)"


# Scope memory budgets (bytes)
_SCOPE_BUDGET = {
    0: 1024,
    1: 512,
    2: 256,
    3: 128,
    4: 64,
}


# ── Semantic log ──────────────────────────────────────────────────────────────
def _build_semantic_log(interp) -> list:
    """Build the semantic log from interp._symbol_log_list — the persistent
    log that captures ALL variables including locals inside functions and loops
    that are destroyed after execution. Offsets reset independently per scope."""
    from shared.grammar import BuildNode

    rows          = []
    scope_offsets = {}   # scope_name → running offset (resets per scope)
    scope_used    = {}   # scope_name → total bytes used

    for sym in interp._symbol_log_list:
        # sym keys: name, type, value, scope, scope_level, line
        scope_key = sym["scope"]
        vtype     = sym["type"]

        # Try to get accurate byte size from the live global entry first.
        # Local variables (functions/loops) are gone by now — fall back to
        # estimation from type string. Either way nothing is hardcoded to
        # the language's specific types.
        live_entry = interp.global_env.get_entry(sym["name"])
        if live_entry and not isinstance(live_entry.value, BuildNode):
            nbytes = _type_bytes(live_entry)
            label  = _type_width_label(live_entry)
        else:
            nbytes, label = _estimate_from_type(vtype, sym.get("value", ""))

        # Offset counter resets to 0 for each new scope
        if scope_key not in scope_offsets:
            scope_offsets[scope_key] = 0

        rows.append({
            "name":        sym["name"],
            "type":        vtype,
            "width":       label,
            "value":       sym["value"],
            "scope":       scope_key,
            "scope_level": sym["scope_level"],
            "offset":      scope_offsets[scope_key],
            "line":        sym["line"],
        })

        scope_offsets[scope_key] += nbytes
        scope_used[scope_key] = scope_used.get(scope_key, 0) + nbytes

    # ── Per-scope memory summary ──────────────────────────────────────────────
    scope_summary = []
    for scope_name, used in sorted(scope_used.items()):
        level  = _scope_level(scope_name)
        budget = _SCOPE_BUDGET.get(level, 128)
        free   = max(0, budget - used)
        scope_summary.append({
            "scope":  scope_name,
            "level":  level,
            "used":   used,
            "budget": budget,
            "free":   free,
            "pct":    round((used / budget) * 100, 1) if budget else 0,
        })

    result = [{
        "header":        ["Name", "Type", "Width", "Offset", "Scope", "Level", "Value", "Line"],
        "rows":          rows,
        "scope_summary": scope_summary,
        "total_bytes":   sum(scope_used.values()),
    }]

    if interp.warnings:
        result.append({"warnings": interp.warnings})
    return result


# ── Symbol map for target generator ──────────────────────────────────────────
def _build_sym_map(interp: Interpreter) -> dict:
    """Convert the interpreter's global symbol table into the simple dict
    that TargetGenerator expects."""
    from shared.grammar import BuildNode
    symbols = interp.global_env.all_symbols()
    result  = {}
    offset  = 0
    for name, entry in symbols.items():
        if isinstance(entry.value, BuildNode):
            continue
        result[name] = _SymProxy(entry.vtype, offset, entry.value, entry.width)
        offset += 4
    return result


class _SymProxy:
    def __init__(self, dtype, offset, value, width):
        self.dtype  = dtype
        self.offset = offset
        self._value = value
        self.width  = width

    def display(self):
        if isinstance(self._value, list):
            return "[" + ", ".join(str(v) for v in self._value) + "]"
        return str(self._value) if self._value is not None else "nothing"


# ── Static file serving ───────────────────────────────────────────────────────
if os.path.exists(frontend_dir):
    reference_file = os.path.join(frontend_dir, "reference.html")

    @app.get("/reference", include_in_schema=False)
    async def reference_page():
        if os.path.exists(reference_file):
            return FileResponse(reference_file, media_type="text/html")
        return FileResponse(
            os.path.join(frontend_dir, "index.html"), media_type="text/html"
        )

    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)