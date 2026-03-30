"""
VoxLang Language Grammar & Parser
Every keyword sounds natural when spoken aloud.
"""

from dataclasses import dataclass
from typing import Any

TT_KEYWORD = "KEYWORD"
TT_IDENT   = "IDENT"
TT_NUMBER  = "NUMBER"
TT_STRING  = "STRING"
TT_BOOL    = "BOOL"
TT_OP      = "OP"
TT_EOF     = "EOF"

KEYWORDS = {
    "store","into","precisely","collection","remember","declare","assign","hold",
    "output","show","display","print","reveal","tell","me","what","is",
    "say","write","log","emit","speak","announce","echo",
    "ask","hear","question","then","save","prompt","listen","receive",
    "update","change","set","modify","to","replace","reassign","redefine","overwrite",
    "raise","increase","add","bump","up","by","increment","boost","grow","expand",
    "lower","decrease","subtract","drop","down","from","decrement","reduce","shrink","trim","cut",
    "when","if","suppose","check","otherwise","else","not","assuming","provided","given","unless",
    "elif","elseif",
    "do","this","repeat","cycle","loop","times","iterate","again",
    "go","walk","visit","step","through","every","in","each","for","scan","traverse",
    "keep","going","stay","continue","while","until","long",
    "build","create","make","craft","define","using","function","func","method",
    "procedure","routine","action","task","recipe",
    "use","call","trigger","run","activate","with","invoke","execute","perform",
    "apply","launch","fire","dispatch",
    "get","capture","result","of","grab","fetch","pull",
    "return","give","back","yield",
    "divided","plus","minus","times","squared","power","percent","square","root",
    "joined","multiplied","added","subtracted","mod","modulo","negate","absolute",
    "solve","where","equals","find",
    "bigger","smaller","than","equal","at","least","most","empty","true","false",
    "greater","less","above","below","between","within","outside",
    "and","or","nor","xor","both","either","neither",
    "math","block",
    "num","text","precise","bool","list","number","string","boolean","integer",
    "decimal","digit","word",
    "done","end","finish","close","stop","complete",
    "note","remark","comment","describe",
    "circle","area","radius","hypotenuse","a","b","volume","sphere","the",
    "triangle","rectangle","cylinder","cone","perimeter","circumference","diagonal",
    "split","upper","length","size","count","first","last","slice",
    "pop","append","remove","insert","sort","filter","map","index",
    "convert","cast","parse","format",
    "about","around","approximately","exactly",
    "let","be","as","taking","forget","know",
}

OUTPUT_KEYWORDS   = {"output","show","display","print","reveal","say","write","log","emit","speak","announce","echo"}
BLOCK_CLOSERS     = {"done","end","finish","close","stop","complete"}
OTHERWISE_WORDS   = {"otherwise","else","elif","elseif"}
CONDITION_OPENERS = {"when","if","suppose","assuming","provided","given"}
REPEAT_OPENERS    = {"do","repeat","cycle","loop","iterate"}
FOREACH_OPENERS   = {"go","walk","visit","step","scan","traverse"}
WHILE_OPENERS     = {"keep","stay","continue"}
FUNCDEF_OPENERS   = {"build","create","make","craft","define","function","func","method",
                     "procedure","routine","action","task","recipe"}
FUNCCALL_OPENERS  = {"use","call","trigger","run","activate","invoke","execute","perform",
                     "apply","launch","fire","dispatch"}
UPDATE_OPENERS    = {"update","change","set","modify","replace","reassign","redefine","overwrite"}
RAISE_OPENERS     = {"raise","increase","increment","boost","grow","expand"}
LOWER_OPENERS     = {"lower","decrease","decrement","reduce","shrink","trim","cut"}


@dataclass
class Token:
    type:  str
    value: Any
    line:  int = 0


class Lexer:
    def __init__(self, source: str):
        self.source = source.strip()
        self.pos    = 0
        self.line   = 1
        self.tokens = []

    def peek(self, n=0):
        p = self.pos + n
        return self.source[p] if p < len(self.source) else ""

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
        return ch

    def skip_ws(self):
        while self.pos < len(self.source) and self.source[self.pos] in " \t\r\n":
            self.advance()

    def read_string(self):
        self.advance()
        s = ""
        while self.pos < len(self.source) and self.source[self.pos] != '"':
            s += self.advance()
        if self.pos >= len(self.source):
            raise SyntaxError(f"Line {self.line}: Unclosed string — add a closing quote.")
        self.advance()
        return Token(TT_STRING, s, self.line)

    def read_number(self):
        s = ""
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            s += self.advance()
        if (self.pos < len(self.source)
                and self.source[self.pos] == "."
                and self.pos + 1 < len(self.source)
                and self.source[self.pos + 1].isdigit()):
            s += self.advance()
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                s += self.advance()
        return Token(TT_NUMBER, float(s) if "." in s else int(s), self.line)

    def read_word(self):
        s = ""
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            s += self.advance()
        low = s.lower()
        if low == "true":  return Token(TT_BOOL, True, self.line)
        if low == "false": return Token(TT_BOOL, False, self.line)
        if low in KEYWORDS: return Token(TT_KEYWORD, low, self.line)
        return Token(TT_IDENT, s, self.line)

    def skip_comment(self):
        while self.pos < len(self.source) and self.source[self.pos] != "\n":
            self.pos += 1

    def tokenize(self):
        while self.pos < len(self.source):
            self.skip_ws()
            if self.pos >= len(self.source):
                break
            ch = self.source[self.pos]
            if ch == "-" and self.peek(1) == "-":
                self.skip_comment()
            elif ch == '"':
                self.tokens.append(self.read_string())
            elif ch.isdigit():
                self.tokens.append(self.read_number())
            elif ch.isalpha() or ch == "_":
                self.tokens.append(self.read_word())
            elif ch in "+-*/%=[](),<>!&|^~":
                self.tokens.append(Token(TT_OP, ch, self.line))
                self.advance()
            else:
                self.advance()
        self.tokens.append(Token(TT_EOF, None, self.line))
        return self.tokens


# AST Nodes
@dataclass
class StoreNode:
    name: str; value: Any; precise: bool = False; line: int = 0

@dataclass
class UpdateNode:
    name: str; value: Any; line: int = 0

@dataclass
class RaiseNode:
    name: str; amount: Any; line: int = 0

@dataclass
class LowerNode:
    name: str; amount: Any; line: int = 0

@dataclass
class OutputNode:
    value: Any; line: int = 0

@dataclass
class InputNode:
    prompt: str; into: str; line: int = 0

@dataclass
class BuildNode:
    name: str; params: list; body: list; line: int = 0

@dataclass
class UseNode:
    name: str; args: list; line: int = 0

@dataclass
class CaptureNode:
    name: str; func: str; args: list; line: int = 0

@dataclass
class DoThisNode:
    count: Any; body: list; line: int = 0

@dataclass
class GoThroughNode:
    var: str; iterable: str; body: list; line: int = 0

@dataclass
class KeepGoingNode:
    condition: Any; body: list; line: int = 0

@dataclass
class WhenNode:
    condition: Any; then_block: list; else_block: list; line: int = 0

@dataclass
class ReturnNode:
    value: Any; line: int = 0

@dataclass
class SolveNode:
    var: str; lhs_tokens: list; rhs: Any; line: int = 0

@dataclass
class MathBlockNode:
    body: list; line: int = 0

@dataclass
class AddToNode:
    collection: str; value: Any; line: int = 0

@dataclass
class RemoveFromNode:
    collection: str; value: Any; line: int = 0

@dataclass
class CommentNode:
    text: str; line: int = 0

@dataclass
class BinOpNode:
    left: Any; op: str; right: Any

@dataclass
class UnaryOpNode:
    op: str; operand: Any

@dataclass
class CompNode:
    left: Any; op: str; right: Any

@dataclass
class CollectionNode:
    items: list

@dataclass
class UseExprNode:
    name: str; args: list

@dataclass
class CaptureExprNode:
    func: str; args: list

@dataclass
class IdentNode:
    name: str; line: int = 0

@dataclass
class LiteralNode:
    value: Any

@dataclass
class FormulaNode:
    name: str; kwargs: dict

@dataclass
class JoinedNode:
    left: Any; right: Any

@dataclass
class IndexNode:
    collection: str; index: Any; line: int = 0


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos    = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect_kw(self, *values):
        t = self.advance()
        if t.value not in values:
            got      = t.value if t.value is not None else t.type
            expected = " or ".join(f"'{v}'" for v in values)
            raise SyntaxError(
                f"Line {t.line}: Expected {expected} but got '{got}'.\n"
                f"  Tip: Check your spelling or add the missing keyword."
            )
        return t

    def expect_ident(self):
        t = self.advance()
        if t.type not in (TT_IDENT, TT_KEYWORD):
            raise SyntaxError(
                f"Line {t.line}: Expected a name but got '{t.value}'.\n"
                f"  Tip: Names can only contain letters, numbers, and underscores."
            )
        return Token(TT_IDENT, t.value, t.line)

    def match(self, *values):
        return self.peek().value in values

    def match_type(self, *types):
        return self.peek().type in types

    def match_set(self, s):
        return self.peek().value in s

    def parse(self):
        stmts = []
        while self.peek().type != TT_EOF:
            s = self.parse_statement()
            if s:
                stmts.append(s)
        return stmts

    def parse_block(self):
        stmts = []
        while (self.peek().type != TT_EOF
               and not self.match_set(BLOCK_CLOSERS)
               and not self.match_set(OTHERWISE_WORDS)):
            s = self.parse_statement()
            if s:
                stmts.append(s)
        return stmts

    def parse_statement(self):
        t  = self.peek()
        ln = t.line
        if t.type == TT_EOF:
            return None
        v = t.value

        if v in OUTPUT_KEYWORDS:
            return self.parse_output()
        if v == "tell":
            self.advance()
            if self.match("me"): self.advance()
            return OutputNode(self.parse_expr(), ln)
        if v == "what":
            self.advance()
            if self.match("is"): self.advance()
            return OutputNode(self.parse_expr(), ln)
        if v in ("ask","hear","question","prompt","listen","receive"):
            return self.parse_input()
        if v in ("store","remember","declare","assign","hold"):
            return self.parse_store()
        if v in UPDATE_OPENERS:
            return self.parse_update()
        if v in RAISE_OPENERS:
            return self.parse_raise()
        if v == "add":
            return self.parse_add()
        if v == "bump":
            return self.parse_bump()
        if v in LOWER_OPENERS:
            return self.parse_lower()
        if v == "subtract":
            return self.parse_subtract()
        if v == "drop":
            return self.parse_drop()
        if v == "append":
            return self.parse_add_to()
        if v == "remove":
            return self.parse_remove_from()
        if v in CONDITION_OPENERS:
            return self.parse_when()
        if v in ("check","unless","assuming","provided","given"):
            self.advance()
            if self.match("if"): self.advance()
            return self._parse_when_body(ln)
        # "repeat while" → while loop, not count loop
        if v == "repeat" and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].value == "while":
            return self.parse_keepgoing()
        if v in REPEAT_OPENERS:
            return self.parse_dothis()
        if v in FOREACH_OPENERS:
            return self.parse_gothrough()
        if v in WHILE_OPENERS:
            return self.parse_keepgoing()
        if v in FUNCDEF_OPENERS:
            return self.parse_build()
        if v in FUNCCALL_OPENERS:
            return self.parse_use_stmt()
        if v in ("get","capture","grab","fetch","pull"):
            return self.parse_capture_stmt()
        if v in ("solve","find"):
            return self.parse_solve()
        if v == "math":
            return self.parse_math_block()
        if v in ("return","give","yield","back"):
            self.advance()
            if v == "give" and self.match("back"): self.advance()
            return ReturnNode(self.parse_expr(), ln)
        if v in ("note","remark","comment","describe"):
            self.advance()
            text = ""
            if self.peek().type == TT_STRING:
                text = self.advance().value
            else:
                while self.peek().type not in (TT_EOF,) and self.peek().line == ln:
                    text += " " + str(self.advance().value)
            return CommentNode(text.strip(), ln)
        if v == "let":    return self.parse_let_legacy()
        if v == "set":    return self.parse_set_legacy()
        if v == "say":    return self.parse_say_legacy()
        if v == "define": return self.parse_define_legacy()
        if v == "call":   return self.parse_call_legacy()
        if v in ("num","text","precise","digit","word","integer","decimal","number","string","boolean","bool"):
            return self.parse_typed_legacy()

        self.advance()
        return None

    def parse_output(self):
        ln = self.peek().line
        self.advance()
        return OutputNode(self.parse_expr(), ln)

    def parse_input(self):
        ln = self.peek().line
        self.advance()
        prompt_words = []
        while not self.match("then","save") and self.peek().type != TT_EOF:
            if self.peek().type == TT_STRING:
                prompt_words.append(self.advance().value)
            else:
                prompt_words.append(str(self.advance().value))
        prompt = " ".join(prompt_words)
        if self.match("then"): self.advance()
        if self.match("save"): self.advance()
        if self.match("into"): self.advance()
        name = self.expect_ident().value
        return InputNode(prompt, name, ln)

    def parse_store(self):
        ln = self.peek().line
        self.advance()

        # store result of func with args into var
        if (self.match("result")
                and self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].value == "of"):
            self.advance(); self.advance()
            func = self.expect_ident().value
            args = []
            if self.match("with"):
                self.advance()
                args = self.parse_arglist()
            if self.match("into"): self.advance()
            name = self.expect_ident().value
            return CaptureNode(name, func, args, ln)

        # store collection 1 and 2 ... into name
        if self.match("collection"):
            self.advance()
            items = []
            while not self.match("into") and self.peek().type != TT_EOF:
                if self.match("and"):
                    self.advance()
                    continue
                items.append(self.parse_primary())
            if self.match("into"): self.advance()
            name = self.expect_ident().value
            return StoreNode(name, CollectionNode(items), False, ln)

        val = self.parse_expr()
        precise = False
        if self.match("into"): self.advance()
        name = self.expect_ident().value
        if self.match("precisely"):
            self.advance()
            precise = True
        return StoreNode(name, val, precise, ln)

    def parse_update(self):
        ln = self.peek().line
        self.advance()
        name = self.expect_ident().value
        self.expect_kw("to","is")
        return UpdateNode(name, self.parse_expr(), ln)

    def parse_raise(self):
        ln = self.peek().line
        self.advance()
        name = self.expect_ident().value
        self.expect_kw("by")
        return RaiseNode(name, self.parse_expr(), ln)

    def parse_add(self):
        ln = self.peek().line
        self.advance()
        # "add X to Y" — check if next token could be an expression followed by "to"
        # peek ahead to distinguish from "add to collection" meaning append
        amt  = self.parse_primary()
        self.expect_kw("to")
        name = self.expect_ident().value
        return RaiseNode(name, amt, ln)

    def parse_bump(self):
        ln = self.peek().line
        self.advance()
        if self.match("up"): self.advance()
        name = self.expect_ident().value
        self.expect_kw("by")
        return RaiseNode(name, self.parse_expr(), ln)

    def parse_lower(self):
        ln = self.peek().line
        self.advance()
        name = self.expect_ident().value
        self.expect_kw("by")
        return LowerNode(name, self.parse_expr(), ln)

    def parse_subtract(self):
        ln = self.peek().line
        self.advance()
        amt  = self.parse_primary()
        self.expect_kw("from")
        name = self.expect_ident().value
        return LowerNode(name, amt, ln)

    def parse_drop(self):
        ln = self.peek().line
        self.advance()
        if self.match("down"): self.advance()
        name = self.expect_ident().value
        self.expect_kw("by")
        return LowerNode(name, self.parse_expr(), ln)

    def parse_add_to(self):
        # append VALUE to COLLECTION
        ln = self.peek().line
        self.advance()
        val = self.parse_expr()
        self.expect_kw("to")
        name = self.expect_ident().value
        return AddToNode(name, val, ln)

    def parse_remove_from(self):
        ln = self.peek().line
        self.advance()
        val = self.parse_expr()
        self.expect_kw("from")
        name = self.expect_ident().value
        return RemoveFromNode(name, val, ln)

    def parse_when(self):
        ln = self.peek().line
        self.advance()
        return self._parse_when_body(ln)

    def _parse_when_body(self, ln, _is_elif=False):
        cond       = self.parse_condition()
        self.expect_kw("then")
        then_block = self.parse_block()
        else_block = []
        if self.match_set(OTHERWISE_WORDS):
            ow = self.peek().value
            self.advance()
            if ow in ("elif","elseif"):
                inner = self._parse_when_body(self.peek().line, _is_elif=True)
                else_block = [inner]
            elif ow in ("else","otherwise") and self.match("if"):
                self.advance()
                if self.match("not"): self.advance()
                inner = self._parse_when_body(self.peek().line, _is_elif=True)
                else_block = [inner]
            else:
                else_block = self.parse_block()
        if not _is_elif:
            self._consume_block_closer()
        return WhenNode(cond, then_block, else_block, ln)

    def parse_dothis(self):
        ln = self.peek().line
        self.advance()
        if self.match("this"): self.advance()
        count = self.parse_primary()
        self.expect_kw("times")
        body = self.parse_block()
        self._consume_block_closer()
        return DoThisNode(count, body, ln)

    def parse_gothrough(self):
        ln = self.peek().line
        self.advance()
        if self.match("through"): self.advance()
        self.expect_kw("every","each")
        var      = self.expect_ident().value
        self.expect_kw("in")
        iterable = self.expect_ident().value
        body     = self.parse_block()
        self._consume_block_closer()
        return GoThroughNode(var, iterable, body, ln)

    def parse_keepgoing(self):
        ln = self.peek().line
        self.advance()
        if self.match("going"): self.advance()
        if self.match("as"):
            self.advance()
            if self.match("long"): self.advance()
            if self.match("as"):   self.advance()
        if self.peek().value in ("while","until"): self.advance()
        cond = self.parse_condition()
        body = self.parse_block()
        self._consume_block_closer()
        return KeepGoingNode(cond, body, ln)

    def parse_build(self):
        ln = self.peek().line
        self.advance()
        name   = self.expect_ident().value
        params = []
        if self.match("using","with","taking","accepting","receiving","needing","requiring","having","given"):
            self.advance()
            params.append(self.expect_ident().value)
            while self.match("and"):
                self.advance()
                params.append(self.expect_ident().value)
        body = self.parse_block()
        self._consume_block_closer()
        return BuildNode(name, params, body, ln)

    def parse_use_stmt(self):
        ln = self.peek().line
        self.advance()
        name = self.expect_ident().value
        args = []
        if self.match("with"):
            self.advance()
            args = self.parse_arglist()
        return UseNode(name, args, ln)

    def parse_capture_stmt(self):
        ln = self.peek().line
        self.advance()
        if self.match("result"): self.advance()
        if self.match("of"):     self.advance()
        func = self.expect_ident().value
        args = []
        if self.match("with"):
            self.advance()
            args = self.parse_arglist()
        if self.match("into"): self.advance()
        name = self.expect_ident().value
        return CaptureNode(name, func, args, ln)

    def parse_solve(self):
        ln = self.peek().line
        self.advance()
        var = self.expect_ident().value
        self.expect_kw("where","in")
        lhs_tokens = []
        while not self.match_type(TT_EOF) and self.peek().value not in ("=","equals"):
            lhs_tokens.append(self.advance())
        if self.peek().value in ("=","equals"): self.advance()
        rhs = self.parse_expr()
        return SolveNode(var, lhs_tokens, rhs, ln)

    def parse_math_block(self):
        ln = self.peek().line
        self.advance()
        if self.match("block"): self.advance()
        body = self.parse_block()
        self._consume_block_closer()
        return MathBlockNode(body, ln)

    def parse_arglist(self):
        args = [self.parse_expr()]
        while self.match("and"):
            self.advance()
            args.append(self.parse_expr())
        return args

    def parse_condition(self):
        left = self._parse_single_condition()
        while self.match("and","or"):
            op    = self.peek().value
            self.advance()
            right = self._parse_single_condition()
            left  = CompNode(left, op, right)
        return left

    def _parse_single_condition(self):
        left = self.parse_expr()
        comp_map = {
            ("is","bigger","than"):           ">",
            ("is","greater","than"):          ">",
            ("is","above"):                   ">",
            ("is","more","than"):             ">",
            ("is","over"):                    ">",
            ("is","smaller","than"):          "<",
            ("is","less","than"):             "<",
            ("is","below"):                   "<",
            ("is","under"):                   "<",
            ("is","not","equal","to"):        "!=",
            ("is","not","the","same","as"):   "!=",
            ("is","different","from"):        "!=",
            ("is","not"):                     "!=",
            ("is","equal","to"):              "==",
            ("is","the","same","as"):         "==",
            ("is","exactly"):                 "==",
            ("is","at","least"):              ">=",
            ("is","no","less","than"):        ">=",
            ("is","at","most"):               "<=",
            ("is","no","more","than"):        "<=",
            ("is",):                          "==",
            ("equals",):                      "==",
        }
        for kw_seq, op in comp_map.items():
            if self.peek().value == kw_seq[0]:
                saved   = self.pos
                matched = True
                for kw in kw_seq:
                    if self.peek().value == kw:
                        self.advance()
                    else:
                        matched = False
                        self.pos = saved
                        break
                if matched:
                    if op == "==" and self.match("empty","true","false","nothing","null","zero"):
                        q = self.advance().value
                        if q in ("nothing","null"): q = "empty"
                        elif q == "zero": return CompNode(left, "==", LiteralNode(0))
                        return CompNode(left, "is_" + q, None)
                    right = self.parse_expr()
                    return CompNode(left, op, right)
        return left

    # Full PEMDAS expression parsing
    def parse_expr(self):
        return self.parse_additive()

    def parse_additive(self):
        left = self.parse_multiplicative()
        while True:
            if self.peek().type == TT_OP and self.peek().value == "+":
                self.advance(); right = self.parse_multiplicative()
                left = BinOpNode(left, "+", right)
            elif self.peek().type == TT_OP and self.peek().value == "-":
                self.advance(); right = self.parse_multiplicative()
                left = BinOpNode(left, "-", right)
            elif self.match("plus"):
                self.advance(); right = self.parse_multiplicative()
                left = BinOpNode(left, "+", right)
            elif self.match("minus"):
                self.advance(); right = self.parse_multiplicative()
                left = BinOpNode(left, "-", right)
            else:
                break
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while True:
            if self.peek().type == TT_OP and self.peek().value == "*":
                self.advance(); right = self.parse_unary()
                left = BinOpNode(left, "*", right)
            elif self.peek().type == TT_OP and self.peek().value == "/":
                self.advance(); right = self.parse_unary()
                left = BinOpNode(left, "/", right)
            elif self.peek().type == TT_OP and self.peek().value == "%":
                self.advance(); right = self.parse_unary()
                left = BinOpNode(left, "%", right)
            elif self.match("times"):
                saved = self.pos
                self.advance()
                nxt = self.peek().value
                block_starters = (
                    OUTPUT_KEYWORDS | CONDITION_OPENERS | REPEAT_OPENERS |
                    FOREACH_OPENERS | WHILE_OPENERS | FUNCDEF_OPENERS |
                    FUNCCALL_OPENERS | UPDATE_OPENERS | RAISE_OPENERS |
                    LOWER_OPENERS | BLOCK_CLOSERS |
                    {"store","ask","hear","question","solve","math","return",
                     "note","remark","add","bump","subtract","drop","check",
                     "get","capture","tell","what","num","text","precise",
                     "let","set","say","define","call","append","remove"}
                )
                if nxt in block_starters or self.peek().type == TT_EOF:
                    self.pos = saved; break
                right = self.parse_unary()
                left  = BinOpNode(left, "*", right)
            elif self.match("divided"):
                self.advance()
                if self.match("by"): self.advance()
                right = self.parse_unary()
                left  = BinOpNode(left, "/", right)
            elif self.match("mod"):
                self.advance(); right = self.parse_unary()
                left = BinOpNode(left, "%", right)
            elif self.match("squared"):
                self.advance()
                left = BinOpNode(left, "**", LiteralNode(2))
            elif self.match("to"):
                saved = self.pos
                self.advance()
                if self.match("the"): self.advance()
                if self.match("power"):
                    self.advance()
                    if self.match("of"): self.advance()
                    right = self.parse_unary()
                    left  = BinOpNode(left, "**", right)
                else:
                    self.pos = saved; break
            elif self.match("percent"):
                self.advance()
                if self.match("of"): self.advance()
                right = self.parse_unary()
                left  = BinOpNode(left, "percent", right)
            elif self.match("shift"):
                self.advance()
                direction = self.advance().value
                right     = self.parse_unary()
                op        = "<<" if direction == "left" else ">>"
                left      = BinOpNode(left, op, right)
            elif self.match("joined"):
                self.advance()
                if self.match("with"): self.advance()
                right = self.parse_unary()
                left  = JoinedNode(left, right)
            else:
                break
        return left

    def parse_unary(self):
        if self.peek().type == TT_OP and self.peek().value == "-":
            self.advance()
            return UnaryOpNode("-", self.parse_primary())
        if self.match("not"):
            self.advance()
            return UnaryOpNode("not", self.parse_primary())
        return self.parse_primary()

    def parse_primary(self):
        t = self.peek()

        if t.type == TT_OP and t.value == "(":
            self.advance()
            expr = self.parse_expr()
            if self.peek().type == TT_OP and self.peek().value == ")":
                self.advance()
            return expr

        if t.type == TT_OP and t.value == "[":
            return self.parse_bracket_list()

        if t.value == "square":
            self.advance()
            if self.match("root"): self.advance()
            if self.match("of"):   self.advance()
            return FormulaNode("sqrt", {"x": self.parse_primary()})

        if t.value == "circle":   return self.parse_formula_circle()
        if t.value == "hypotenuse": return self.parse_formula_hyp()
        if t.value == "volume":   return self.parse_formula_volume()

        if t.value in FUNCCALL_OPENERS:
            self.advance()
            name = self.expect_ident().value
            args = []
            if self.match("with"):
                self.advance()
                args = self.parse_arglist()
            return UseExprNode(name, args)

        if t.value in ("get","capture"):
            self.advance()
            if self.match("result"): self.advance()
            if self.match("of"):     self.advance()
            name = self.expect_ident().value
            args = []
            if self.match("with"):
                self.advance()
                args = self.parse_arglist()
            return UseExprNode(name, args)

        # "result of funcname" — only when 'of' follows immediately
        if t.value == "result" and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].value == "of":
            self.advance(); self.advance()
            name = self.expect_ident().value
            args = []
            if self.match("with"):
                self.advance()
                args = self.parse_arglist()
            return UseExprNode(name, args)

        if t.type == TT_NUMBER: self.advance(); return LiteralNode(t.value)
        if t.type == TT_STRING: self.advance(); return LiteralNode(t.value)
        if t.type == TT_BOOL:   self.advance(); return LiteralNode(t.value)
        if t.type == TT_KEYWORD and t.value in ("true","false"):
            self.advance(); return LiteralNode(t.value == "true")

        if t.type in (TT_IDENT, TT_KEYWORD):
            self.advance()
            # collection[index] subscript syntax
            if self.peek().type == TT_OP and self.peek().value == "[":
                self.advance()
                idx = self.parse_expr()
                if self.peek().type == TT_OP and self.peek().value == "]":
                    self.advance()
                return IndexNode(t.value, idx, t.line)
            return IdentNode(t.value, t.line)

        self.advance()
        return LiteralNode(None)

    def parse_bracket_list(self):
        self.advance()
        items = []
        while not self.match_type(TT_EOF) and self.peek().value != "]":
            items.append(self.parse_expr())
            if self.peek().value == ",": self.advance()
        if self.peek().value == "]": self.advance()
        return CollectionNode(items)

    def parse_formula_circle(self):
        self.advance()
        if self.match("area"):        self.advance()
        if self.match("with","of"):   self.advance()
        if self.match("radius"):      self.advance()
        return FormulaNode("circle", {"radius": self.parse_primary()})

    def parse_formula_hyp(self):
        self.advance()
        if self.match("with"): self.advance()
        if self.match("a"):    self.advance()
        a = self.parse_primary()
        if self.match("and"):  self.advance()
        if self.match("b"):    self.advance()
        b = self.parse_primary()
        return FormulaNode("hypotenuse", {"a": a, "b": b})

    def parse_formula_volume(self):
        self.advance()
        if self.match("of"):   self.advance()
        shape = self.advance().value
        if self.match("with"): self.advance()
        if self.match("radius"): self.advance()
        return FormulaNode(f"volume_{shape}", {"radius": self.parse_primary()})

    def _consume_block_closer(self):
        if self.match_set(BLOCK_CLOSERS):
            self.advance()

    def parse_let_legacy(self):
        ln = self.peek().line; self.advance()
        name = self.expect_ident().value
        self.expect_kw("be","is")
        return StoreNode(name, self.parse_expr(), False, ln)

    def parse_set_legacy(self):
        ln = self.peek().line; self.advance()
        name = self.expect_ident().value
        self.expect_kw("to","is")
        return UpdateNode(name, self.parse_expr(), ln)

    def parse_say_legacy(self):
        ln = self.peek().line; self.advance()
        return OutputNode(self.parse_expr(), ln)

    def parse_define_legacy(self):
        ln = self.peek().line; self.advance()
        name = self.expect_ident().value
        params = []
        if self.match("taking","using","with"):
            self.advance()
            params.append(self.expect_ident().value)
            while self.match("and"):
                self.advance()
                params.append(self.expect_ident().value)
        self.expect_kw("as")
        body = self.parse_block()
        self._consume_block_closer()
        return BuildNode(name, params, body, ln)

    def parse_call_legacy(self):
        ln = self.peek().line; self.advance()
        name = self.expect_ident().value
        args = []
        if self.match("with"):
            self.advance()
            args = self.parse_arglist()
        return UseNode(name, args, ln)

    def parse_typed_legacy(self):
        ln = self.peek().line
        precise = False
        if self.match("precise"):
            self.advance(); precise = True
        if self.match("num","text"): self.advance()
        name = self.expect_ident().value
        self.expect_kw("is","be")
        return StoreNode(name, self.parse_expr(), precise, ln)