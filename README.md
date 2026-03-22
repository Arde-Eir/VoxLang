# Utter
### Voice-First Programming Language & IDE

Utter is a programming language designed to be spoken aloud. Every keyword and construct sounds natural in conversation. It comes with a full browser-based IDE that transcribes your voice, converts it to Utter code via Claude, and lets you type to fix anything the mic gets wrong.

---

## Quick Start

### 1. Clone & set up

```bash
git clone <your-repo>
cd utter
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and OPENAI_API_KEY
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
utter/
├── backend/
│   ├── main.py        # FastAPI server (REST + WebSocket)
│   ├── stt.py         # Speech-to-text (Whisper / Deepgram)
│   └── llm.py         # Claude integration
├── frontend/
│   ├── index.html     # IDE UI
│   ├── editor.js      # Monaco editor + voice integration
│   └── voice.js       # Mic capture, noise filter, STT pipeline
├── shared/
│   ├── grammar.py     # Utter lexer + parser (produces AST)
│   ├── interpreter.py # Utter runtime / executor
│   ├── prompts.py     # All LLM system prompts
│   └── config.py      # Environment config
├── docs/
│   ├── README.md      # This file
│   └── LANGUAGE.md    # Full language reference
├── .env.example
├── requirements.txt
└── run.sh
```

---

## API Keys Required

| Key                  | Where to get it                        | Used for           |
|----------------------|----------------------------------------|--------------------|
| `ANTHROPIC_API_KEY`  | https://console.anthropic.com          | Code generation    |
| `OPENAI_API_KEY`     | https://platform.openai.com/api-keys   | Whisper STT        |
| `DEEPGRAM_API_KEY`   | https://console.deepgram.com           | Deepgram STT (opt) |

---

## How the Pipeline Works

```
Mic → noise filter → STT (Whisper/Deepgram)
                  ↓
          confidence check
          < 0.75 → Claude corrects transcript
                  ↓
          Claude converts to Utter code
                  ↓
          Ghost text preview in Monaco
                  ↓
     Tab = accept │ Esc = dismiss │ type to override
                  ↓
          Utter Lexer → Parser → AST → Interpreter
                  ↓
              output console
```

---

## The Utter Language

See [docs/LANGUAGE.md](LANGUAGE.md) for the full reference.

Quick taste:

```utter
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

## API Endpoints

| Method | Path         | Description                          |
|--------|--------------|--------------------------------------|
| POST   | `/transcribe`| Audio → transcript + confidence      |
| POST   | `/generate`  | Transcript → Utter code (Claude)     |
| POST   | `/run`       | Utter code → execution output        |
| POST   | `/explain`   | Code → plain English explanation     |
| POST   | `/suggest`   | Partial code → completion suggestion |
| POST   | `/chat`      | Freeform question about Utter        |
| GET    | `/health`    | Health check                         |
| WS     | `/ws/voice`  | Full voice pipeline over WebSocket   |

Interactive docs: **http://localhost:8000/docs**

---

## Day-by-Day Build Plan

| Day | Goal |
|-----|------|
| 1 | STT working — mic → text in browser |
| 2 | LLM layer — text → Utter code via Claude |
| 3 | Monaco editor — voice + keyboard hybrid |
| 4 | Voice commands — undo, delete, run, go to line |
| 5 | Polish — test 10 programs, fix prompts |

---

## License

MIT
