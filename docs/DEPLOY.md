# VoxLang — Deployment Guide

## Local Development

```bash
# 1. Copy env file
cp .env.example .env
# Fill in GROQ_API_KEY and DEEPGRAM_API_KEY

# 2. Install deps
pip install -r requirements.txt

# 3. Start
bash run.sh
# IDE:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

---

## Deploy to Vercel

VoxLang uses **FastAPI + @vercel/python** for the backend and static files for the frontend.
The `vercel.json` routes all `/api` calls to the Python serverless function and serves the
frontend directly.

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "initial voxlang"
git remote add origin https://github.com/YOUR_USER/voxlang.git
git push -u origin main
```

### Step 2 — Import on Vercel

1. Go to **vercel.com** → **Add New Project**
2. Import your GitHub repo
3. Framework Preset: **Other**
4. Root Directory: `.` (leave as default)
5. Click **Deploy** — it will likely fail on the first attempt (no env vars yet)

### Step 3 — Add Environment Variables

In your Vercel project → **Settings → Environment Variables**, add:

| Name               | Value                        | Environment         |
|--------------------|------------------------------|---------------------|
| `GROQ_API_KEY`     | `gsk_...`                    | Production, Preview |
| `DEEPGRAM_API_KEY` | `...`                        | Production, Preview |
| `GROQ_MODEL`       | `llama-3.3-70b-versatile`    | Production, Preview |
| `STT_PROVIDER`     | `deepgram`                   | Production, Preview |
| `CORS_ORIGINS`     | `*`                          | Production, Preview |

### Step 4 — Redeploy

Go to **Deployments** → click the latest → **Redeploy**.

### Step 5 — Update the frontend API base

Once deployed, the frontend automatically uses the same origin (empty `API_BASE`),
so no config needed. The Settings modal lets users override with a custom URL.

---

## Vercel Project Structure

```
VoxLang/
├── api/
│   └── index.py          ← Vercel serverless entry (imports backend.main:app)
├── backend/
│   ├── main.py           ← FastAPI app
│   ├── llm.py            ← Groq LLM calls
│   └── stt.py            ← Deepgram STT
├── frontend/
│   ├── index.html        ← IDE (served as static)
│   ├── reference.html    ← Language reference
│   ├── editor.js         ← Monaco editor module
│   └── voice.js          ← VoiceCapture module
├── shared/
│   ├── grammar.py        ← Lexer + Parser
│   ├── interpreter.py    ← Phase 3 executor
│   ├── codegen.py        ← Phase 4 IR/TAC
│   ├── optimizer.py      ← Phase 5 optimizer
│   ├── target.py         ← Phase 6 target codegen
│   ├── config.py         ← Env config
│   └── prompts.py        ← LLM system prompts
├── vercel.json           ← Vercel routing config
└── requirements.txt
```

---

## Notes

- **WebSockets** (`/ws/voice`) are **not supported** on Vercel's serverless platform.
  The IDE automatically falls back to the HTTP `/transcribe` + `/generate` flow — voice
  input still works fully via the HTTP pipeline.
- Vercel's free tier has a **10-second function timeout**. LLM calls (chat, explain) may
  hit this. Upgrade to Pro for 60s, or use the Vercel Edge Runtime (requires rewrite to
  Next.js API routes).
- Cold starts on the free tier can take 2–4 seconds on the first request.