"""
shared/config.py
=================
VoxLang — Environment Configuration
Reads from .env file at project root.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────
GROQ_API_KEY     = os.getenv("GROQ_API_KEY",     "")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# ── Model settings ─────────────────────────────────────────────────────────
GROQ_MODEL   = os.getenv("GROQ_MODEL",   "llama-3.3-70b-versatile")
STT_PROVIDER = os.getenv("STT_PROVIDER", "deepgram")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS", "1024"))

# ── Voice settings ─────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
WAKE_WORD            = os.getenv("WAKE_WORD", "hey vox")

# ── Server settings ────────────────────────────────────────────────────────
HOST         = os.getenv("HOST", "0.0.0.0")
PORT         = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
if CORS_ORIGINS == "*":
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS.split(",")]


def validate() -> list[str]:
    """Return a list of config warnings. Empty = all good."""
    warnings = []
    if not GROQ_API_KEY:
        warnings.append("GROQ_API_KEY is not set — LLM features will fail")
    if not DEEPGRAM_API_KEY:
        warnings.append("DEEPGRAM_API_KEY is not set — voice input will fail")
    return warnings