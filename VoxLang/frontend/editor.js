/**
 * VoxLang – Editor Module
 * ========================
 * Monaco editor with full VoxLang language support.
 * Grammar: voice-first natural language programming.
 *   store/into/remember/declare — variable declaration
 *   output/show/tell me/say/log  — output aliases
 *   build/create/func/method     — function definition
 *   when/if/suppose/assuming     — conditions
 *   done/end/finish/close/stop   — block closers
 *   otherwise/else/elif          — else branches
 */

export class VoxLangEditor {
  constructor(containerId, opts = {}) {
    this.containerId        = containerId;
    this.editor             = null;
    this.monaco             = null;
    this.pendingCode        = null;
    this._lastCommandStatus = null;
    this.onRunRequest       = opts.onRunRequest || (() => {});
    this.onCodeChange       = opts.onCodeChange || (() => {});
  }

  async init() {
    return new Promise((resolve) => {
      require.config({ paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" } });
      require(["vs/editor/editor.main"], (monaco) => {
        this.monaco = monaco;
        this._registerVoxLangLanguage(monaco);
        this.editor = monaco.editor.create(document.getElementById(this.containerId), {
          language:                   "voxlang",
          theme:                      "voxlang-dark",
          fontSize:                   15,
          lineHeight:                 24,
          fontFamily:                 "'JetBrains Mono', 'Fira Code', monospace",
          fontLigatures:              true,
          minimap:                    { enabled: false },
          scrollbar:                  { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
          padding:                    { top: 20, bottom: 20 },
          wordWrap:                   "on",
          renderLineHighlight:        "gutter",
          cursorBlinking:             "smooth",
          cursorSmoothCaretAnimation: "on",
          automaticLayout:            true,
          value:                      this._sampleProgram(),
        });

        this.editor.onDidChangeModelContent(() => {
          this.onCodeChange(this.getCode());
        });

        this.editor.addCommand(
          monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
          () => this.onRunRequest(this.getCode())
        );

        this.editor.addCommand(
          monaco.KeyCode.Tab,
          () => {
            if (this.pendingCode !== null) this.acceptGhost();
            else this.editor.trigger("keyboard", "tab", {});
          }
        );

        this.editor.addCommand(
          monaco.KeyCode.Escape,
          () => { if (this.pendingCode !== null) this.dismissGhost(); }
        );

        resolve(this.editor);
      });
    });
  }

  getCode() { return this.editor ? this.editor.getValue() : ""; }
  setCode(code) { if (!this.editor) return; this.editor.setValue(code); }

  // ── Ghost text ─────────────────────────────────────────────────────────────
  showGhost(code) {
    this.dismissGhost();
    this.pendingCode = code;
    const position = this.editor.getPosition();
    const lines    = code.split("\n");
    const preview  = lines.slice(0, 3).join(" | ") + (lines.length > 3 ? " …" : "");
    this._removeGhostDecoration();
    this._ghostDecorationIds = this.editor.deltaDecorations([], [{
      range: new this.monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
      options: { after: { content: `  ← ${preview}  [Tab to accept]`, inlineClassName: "voxlang-ghost-text" } }
    }]);
  }

  acceptGhost() {
    if (this.pendingCode === null) return;
    const code = this.pendingCode;
    this.dismissGhost();
    this._insertAtCursor(code);
  }

  dismissGhost() {
    this.pendingCode = null;
    this._removeGhostDecoration();
  }

  _removeGhostDecoration() {
    if (this._ghostDecorationIds) {
      this.editor.deltaDecorations(this._ghostDecorationIds, []);
      this._ghostDecorationIds = null;
    }
  }

  _insertAtCursor(code) {
    const position   = this.editor.getPosition();
    const model      = this.editor.getModel();
    const lineText   = model.getLineContent(position.lineNumber);
    const insertText = lineText.trim() !== "" ? "\n" + code : code;
    this.editor.executeEdits("voice", [{
      range: new this.monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
      text:  insertText,
    }]);
    const newLines = insertText.split("\n");
    const newLine  = position.lineNumber + newLines.length - 1;
    const newCol   = newLines[newLines.length - 1].length + 1;
    this.editor.setPosition({ lineNumber: newLine, column: newCol });
    this.editor.revealPositionInCenter({ lineNumber: newLine, column: newCol });
  }

  // ── Voice command handler ──────────────────────────────────────────────────
  handleVoiceCommand(command) {
    if (!this.editor) return false;
    this._lastCommandStatus = null;
    const cmd = command.toLowerCase().trim().replace(/[.!?]+$/, "");

    if (cmd.includes("negative") || (cmd.includes("minus") && cmd.includes("line"))) {
      this._showError("Line numbers must be 1 or higher.");
      return true;
    }

    if (cmd === "undo" || cmd === "undo that" || cmd === "undo last") {
      this.editor.trigger("voice", "undo", {});
      this._showSuccess("Undo applied.");
      return true;
    }
    if (cmd === "redo" || cmd === "redo that") {
      this.editor.trigger("voice", "redo", {});
      this._showSuccess("Redo applied.");
      return true;
    }
    if (cmd === "clear" || cmd === "clear all" || cmd === "clear editor" || cmd === "clear the editor") {
      if (this.editor.getValue().trim() === "") {
        this._showError("Editor is already empty.");
      } else {
        this.setCode("");
        this._showSuccess("Editor cleared.");
      }
      return true;
    }
    if (cmd.includes("delete line") || cmd.includes("remove line")) {
      const model   = this.editor.getModel();
      const pos     = this.editor.getPosition();
      const maxLine = model.getLineCount();
      if (maxLine === 1 && model.getLineContent(1).trim() === "") {
        this._showError("Nothing to delete — editor is already empty.");
        return true;
      }
      const digitMatch = cmd.match(/\d+/);
      if (digitMatch) {
        const targetLine = parseInt(digitMatch[0]);
        if (targetLine < 1 || targetLine > maxLine) {
          this._showError(`Cannot delete line ${targetLine} — file only has ${maxLine} line(s).`);
          return true;
        }
        const range = targetLine === 1
          ? new this.monaco.Range(1, 1, 2, 1)
          : new this.monaco.Range(targetLine - 1, model.getLineMaxColumn(targetLine - 1), targetLine, model.getLineMaxColumn(targetLine));
        this.editor.executeEdits("voice", [{ range, text: "" }]);
        this._showSuccess(`Line ${targetLine} deleted.`);
        return true;
      }
      const line  = pos.lineNumber;
      const range = line === 1
        ? new this.monaco.Range(1, 1, 2, 1)
        : new this.monaco.Range(line - 1, model.getLineMaxColumn(line - 1), line, model.getLineMaxColumn(line));
      this.editor.executeEdits("voice", [{ range, text: "" }]);
      this._showSuccess(`Line ${line} deleted.`);
      return true;
    }
    if (cmd.includes("go to line") || cmd.includes("jump to line") || cmd.includes("navigate to line")) {
      const maxLine    = this.editor.getModel().getLineCount();
      const digitMatch = cmd.match(/\d+/);
      if (digitMatch) {
        const n = parseInt(digitMatch[0]);
        if (n < 1) { this._showError("Line numbers start at 1."); return true; }
        if (n > maxLine) { this._showError(`Line ${n} does not exist — file only has ${maxLine} line(s).`); return true; }
        this.editor.revealLineInCenter(n);
        this.editor.setPosition({ lineNumber: n, column: 1 });
        this._showSuccess(`Moved to line ${n}.`);
        return true;
      }
      const n = this._parseWordNumber(cmd.replace(/go to line|jump to line|navigate to line/g, "").trim());
      if (n === null) { this._showError("Could not understand the line number."); return true; }
      if (n < 1) { this._showError("Line numbers start at 1."); return true; }
      if (n > maxLine) { this._showError(`Line ${n} does not exist — file only has ${maxLine} line(s).`); return true; }
      this.editor.revealLineInCenter(n);
      this.editor.setPosition({ lineNumber: n, column: 1 });
      this._showSuccess(`Moved to line ${n}.`);
      return true;
    }
    if (cmd.includes("go to top") || cmd.includes("go to start") || cmd === "top") {
      this.editor.revealLine(1);
      this.editor.setPosition({ lineNumber: 1, column: 1 });
      this._showSuccess("Moved to top.");
      return true;
    }
    if (cmd.includes("go to bottom") || cmd.includes("go to end") || cmd === "bottom") {
      const last = this.editor.getModel().getLineCount();
      this.editor.revealLine(last);
      this.editor.setPosition({ lineNumber: last, column: 1 });
      this._showSuccess(`Moved to bottom (line ${last}).`);
      return true;
    }
    if (cmd === "select all" || cmd === "select everything") {
      this.editor.trigger("voice", "selectAll", {});
      this._showSuccess("All code selected.");
      return true;
    }
    if (cmd === "run" || cmd === "run it" || cmd === "run the code" ||
        cmd === "execute" || cmd === "execute the code" || cmd === "run program" || cmd === "run my code") {
      if (this.editor.getValue().trim() === "") { this._showError("Nothing to run — editor is empty."); return true; }
      this.onRunRequest(this.getCode());
      this._showSuccess("Running…");
      return true;
    }
    if (cmd === "save" || cmd === "save file") {
      this._showError("Auto-save is always on. Your code is preserved in the editor.");
      return true;
    }

    return false;
  }

  _showSuccess(msg) {
    const output = document.getElementById("console-output");
    if (output) {
      const div = document.createElement("div");
      div.className   = "out-info";
      div.textContent = `✓ ${msg}`;
      output.innerHTML = "";
      output.appendChild(div);
    }
    this._lastCommandStatus = { ok: true, msg };
  }

  _showError(msg) {
    const output = document.getElementById("console-output");
    if (output) {
      const div = document.createElement("div");
      div.className   = "out-error";
      div.textContent = `✗ ${msg}`;
      output.innerHTML = "";
      output.appendChild(div);
    }
    this._lastCommandStatus = { ok: false, msg };
  }

  _parseWordNumber(text) {
    const wordMap = {
      'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,
      'six':6,'seven':7,'eight':8,'nine':9,'ten':10,
      'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,
      'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,
      'twenty':20,'thirty':30,'forty':40,'fifty':50,
      'sixty':60,'seventy':70,'eighty':80,'ninety':90,
    };
    const words = text.trim().split(/\s+/);
    let total = 0, temp = 0, found = false;
    for (const word of words) {
      const val = wordMap[word];
      if (val !== undefined) {
        found = true;
        if (val >= 10) { total += val; temp = 0; }
        else           { temp  += val; }
      }
    }
    if (!found) return null;
    return total + temp;
  }

  // ── VoxLang syntax highlighting ────────────────────────────────────────────
  _registerVoxLangLanguage(monaco) {
    monaco.languages.register({ id: "voxlang" });

    monaco.languages.setMonarchTokensProvider("voxlang", {
      keywords: [
        // ── Declaration ──────────────────────────────────────────────────────
        "store","into","precisely","collection",
        "remember","declare","assign","hold",
        // ── Output ───────────────────────────────────────────────────────────
        "output","show","display","print","reveal","tell","me","what","is",
        "say","write","log","emit","speak","announce","echo",
        // ── Input ────────────────────────────────────────────────────────────
        "ask","hear","question","then","save","prompt","listen","receive",
        // ── Update ───────────────────────────────────────────────────────────
        "update","change","set","modify","to",
        "replace","reassign","redefine","overwrite",
        // ── Raise ────────────────────────────────────────────────────────────
        "raise","increase","increment","boost","grow","expand",
        "add","bump","up","by",
        // ── Lower ────────────────────────────────────────────────────────────
        "lower","decrease","decrement","reduce","shrink","trim","cut",
        "subtract","drop","down","from",
        // ── Conditions ───────────────────────────────────────────────────────
        "when","if","suppose","check","otherwise","else","not","elif","elseif",
        "assuming","provided","given","unless",
        // ── Loops ────────────────────────────────────────────────────────────
        "do","this","repeat","cycle","loop","times","iterate",
        "go","walk","visit","step","scan","traverse","through","every","each","in",
        "keep","going","stay","continue","while","until","long",
        // ── Functions ────────────────────────────────────────────────────────
        "build","create","make","craft","define","using",
        "function","func","method","procedure","routine","action","task","recipe",
        "use","call","trigger","run","activate","with",
        "invoke","execute","perform","apply","launch","fire","dispatch",
        "get","capture","result","of","grab","fetch","pull",
        "return","give","back","yield",
        // ── Math ─────────────────────────────────────────────────────────────
        "divided","plus","minus","times","squared","power","percent",
        "square","root","joined","solve","where","equals","find",
        "multiplied","added","subtracted","mod","modulo","negate","absolute",
        // ── Comparisons ──────────────────────────────────────────────────────
        "bigger","smaller","than","equal","at","least","most",
        "greater","less","above","below","between","within","outside",
        "empty","true","false","nothing",
        "and","or","nor","xor","both","either","neither",
        // ── Math block ───────────────────────────────────────────────────────
        "math","block",
        // ── Types ────────────────────────────────────────────────────────────
        "num","text","precise","bool","list",
        "number","string","boolean","integer","decimal","digit","word",
        // ── Block closers ────────────────────────────────────────────────────
        "done","end","finish","close","stop","complete",
        // ── Comments ─────────────────────────────────────────────────────────
        "note","remark","comment","describe",
      ],
      tokenizer: {
        root: [
          // Comments (-- style)
          [/--.*$/,                          "comment"],
          // Strings
          [/"([^"\\]|\\.)*"/,                "string"],
          // Numbers
          [/\b\d+(\.\d+)?\b/,               "number"],
          // Booleans / special values
          [/\b(true|false|empty|nothing)\b/, "keyword.boolean"],
          // Declaration keywords
          [/\b(store|into|precisely|collection|remember|declare|assign|hold)\b/, "keyword.declaration"],
          // Output keywords
          [/\b(output|display|print|reveal|emit|speak|announce|echo|say|write|log)\b/, "keyword.output"],
          [/\b(what\s+is|show|tell\s+me)\b/i, "keyword.output"],
          // Call keywords
          [/\b(use|call|trigger|activate|invoke|execute|perform|apply|launch|fire|dispatch)\b/, "keyword.call"],
          // Function def keywords
          [/\b(build|create|make|craft|define|function|func|method|procedure|routine|action|task|recipe|using)\b/, "keyword.function"],
          // Result/return keywords
          [/\b(get|capture|result|of|grab|fetch|pull|return|give|back|yield)\b/, "keyword.call"],
          // Control keywords
          [/\b(when|if|suppose|check|otherwise|else|elif|elseif|assuming|provided|given|unless|not)\b/, "keyword.control"],
          [/\b(do|this|repeat|cycle|loop|times|iterate|again)\b/, "keyword.control"],
          [/\b(go|walk|visit|step|scan|traverse|through|every|each|in|for)\b/, "keyword.control"],
          [/\b(keep|going|stay|continue|while|until|long)\b/, "keyword.control"],
          [/\b(done|end|finish|close|stop|complete)\b/, "keyword.control"],
          // Math keywords
          [/\b(solve|find|where|equals|math|block)\b/, "keyword.math"],
          [/\b(divided|plus|minus|times|squared|power|percent|square|root|joined|multiplied|added|subtracted|mod|modulo|negate|absolute)\b/, "keyword.operator"],
          // Comparison keywords
          [/\b(bigger|smaller|greater|less|above|below|than|equal|at|least|most|between|within|outside|is)\b/, "keyword.comparison"],
          [/\b(and|or|nor|xor|both|either|neither)\b/, "keyword.comparison"],
          // Type keywords
          [/\b(num|text|precise|bool|list|number|string|boolean|integer|decimal|digit|word)\b/, "keyword.type"],
          // Raise/lower keywords
          [/\b(raise|increase|increment|boost|grow|expand|add|bump|up|by)\b/, "keyword.operator"],
          [/\b(lower|decrease|decrement|reduce|shrink|trim|cut|subtract|drop|down|from)\b/, "keyword.operator"],
          // Update keywords
          [/\b(update|change|set|modify|replace|reassign|redefine|overwrite|to)\b/, "keyword.declaration"],
          // Input keywords
          [/\b(ask|hear|question|prompt|listen|receive|then|save)\b/, "keyword.declaration"],
          // Comment keywords
          [/\b(note|remark|comment|describe)\b/, "comment"],
          // Identifiers
          [/[a-zA-Z_]\w*/,                   "identifier"],
          [/\s+/,                            "white"],
        ]
      }
    });

    monaco.editor.defineTheme("voxlang-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment",             foreground: "5C6370", fontStyle: "italic" },
        { token: "keyword.type",        foreground: "CF9FFF", fontStyle: "bold" },
        { token: "keyword.declaration", foreground: "FF9D6C", fontStyle: "bold" },
        { token: "keyword.output",      foreground: "4ADE80", fontStyle: "bold" },
        { token: "keyword.operator",    foreground: "FFB86C" },
        { token: "keyword.call",        foreground: "A78BFA", fontStyle: "bold" },
        { token: "keyword.control",     foreground: "F28B82", fontStyle: "bold" },
        { token: "keyword.function",    foreground: "81C995", fontStyle: "bold" },
        { token: "keyword.math",        foreground: "FBBF24", fontStyle: "bold" },
        { token: "keyword.comparison",  foreground: "93C5FD" },
        { token: "keyword.boolean",     foreground: "CF9FFF" },
        { token: "string",              foreground: "A8FF78" },
        { token: "number",              foreground: "FF9D6C" },
        { token: "identifier",          foreground: "E8E6E3" },
      ],
      colors: {
        "editor.background":              "#0F1117",
        "editor.foreground":              "#E8E6E3",
        "editorLineNumber.foreground":    "#3D4050",
        "editorCursor.foreground":        "#5B73FF",
        "editor.selectionBackground":     "#2A3050",
        "editor.lineHighlightBackground": "#161820",
        "editorGutter.background":        "#0F1117",
      }
    });
  }

  // ── Sample program — aligned to TN35 spec ─────────────────────────────────
 _sampleProgram() {
  return `-- Welcome to VoxLang — voice-first programming

store "World" into name
output "Hello " joined with name

-- Define a function
build greet using person
  output "Nice to meet you, " joined with person
done

use greet with "Alice"

-- Lists and loops
store collection 1 and 2 and 3 and 4 and 5 into numbers
go through every num in numbers
  output num
done

-- Math
store circle area with radius 7 into area
solve x where 2 times x plus 3 equals 15
output "Circle area: " joined with area
output "x = " joined with x

-- Condition
when x is bigger than 5 then
  output "x is big"
otherwise
  output "x is small"
done
`;
}
}