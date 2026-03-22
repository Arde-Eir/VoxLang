# VoxLang
### Voice-First Programming Language & IDE

VoxLang is a programming language designed to be spoken aloud. Every keyword and construct sounds natural in conversation. It comes with a full browser-based IDE that transcribes your voice, converts it to VoxLang code via Groq, and lets you type to fix anything the mic gets wrong.

---

## Quick Start

### 1. Clone & set up
```bash
git clone https://github.com/Arde-Eir/VoxLang.git
cd VoxLang
cp .env.example .env
# Edit .env — add your GROQ_API_KEY and DEEPGRAM_API_KEY
```

### 2. Run
```bash
chmod +x run.sh
./run.sh
```

Then open **http://localhost:8000** in your browser.

---

## Project Structure
```
VoxLang/
├── backend/
│   ├── __init__.py
│   ├── main.py        # FastAPI server (REST + WebSocket)
│   ├── stt.py         # Speech-to-text (Deepgram)
│   └── llm.py         # Groq integration
├── frontend/
│   ├── __init__.py
│   ├── index.html     # IDE UI
│   ├── reference.html # Language reference UI
│   ├── editor.js      # Monaco editor + voice integration
│   └── voice.js       # Mic capture, noise filter, STT pipeline
├── shared/
│   ├── __init__.py
│   ├── codegen.py     # Code generation
│   ├── config.py      # Environment config
│   ├── grammar.py     # VoxLang lexer + parser (produces AST)
│   ├── interpreter.py # VoxLang runtime / executor
│   ├── optimizer.py   # Code optimizer
│   ├── prompts.py     # All LLM system prompts
│   └── target.py      # Compilation targets
├── docs/
│   └── LANGUAGE.md    # Full language reference
├── .env.example
├── requirements.txt
└── run.sh
```

---

## API Keys Required

| Key                 | Where to get it                   | Used for        |
|---------------------|-----------------------------------|-----------------|
| `GROQ_API_KEY`      | https://console.groq.com          | Code generation |
| `DEEPGRAM_API_KEY`  | https://console.deepgram.com      | Voice STT       |

---

## How the Pipeline Works
```
Mic → noise filter → STT (Deepgram)
                  ↓
          confidence check
          < 0.75 → Groq corrects transcript
                  ↓
          Groq converts to VoxLang code
                  ↓
          Ghost text preview in Monaco
                  ↓
     Tab = accept │ Esc = dismiss │ type to override
                  ↓
          VoxLang Lexer → Parser → AST → Interpreter
                  ↓
              output console
```

---

## The VoxLang Language

See [docs/LANGUAGE.md](docs/LANGUAGE.md) for the full reference.

Quick taste:
```voxlang
note "Greet the user and count down"

ask "What is your name?" into name
say "Hello, " plus name

let count be 5
while count greater than 0
  say count
  set count to count minus 1
end

say "Blast off!"
```

---

## License

MIT