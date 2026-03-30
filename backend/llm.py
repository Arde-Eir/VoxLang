"""
VoxLang – LLM Layer (Groq)
===========================
All Groq API calls for VoxLang pipeline.
"""

import httpx
from shared.config import GROQ_API_KEY, GROQ_MODEL, MAX_TOKENS
from shared.prompts import (
    VOICE_TO_VOXLANG_SYSTEM,
    VOICE_CORRECTION_SYSTEM,
    EXPLAIN_SYSTEM,
    SUGGEST_SYSTEM,
    CHAT_SYSTEM,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call(system: str, user: str, max_tokens: int = None) -> str:
    """Single-turn call with a system prompt and one user message."""
    with httpx.Client(timeout=30) as client:
        response = client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":      GROQ_MODEL,
                "max_tokens": max_tokens or MAX_TOKENS,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")
    return response.json()["choices"][0]["message"]["content"].strip()


def _call_with_history(system: str, history: list[dict], max_tokens: int = None) -> str:
    """
    Multi-turn call that preserves conversation history.
    history = [{"role": "user"|"assistant", "content": "..."}]
    """
    messages = [{"role": "system", "content": system}] + history
    with httpx.Client(timeout=30) as client:
        response = client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":      GROQ_MODEL,
                "max_tokens": max_tokens or MAX_TOKENS,
                "messages":   messages,
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")
    return response.json()["choices"][0]["message"]["content"].strip()


def voice_to_code(spoken_text: str, context: str = "") -> str:
    user_prompt = spoken_text
    if context.strip():
        user_prompt = (
            f"Current editor context:\n```\n{context[-500:]}\n```\n\n"
            f"Voice command: {spoken_text}"
        )
    return _call(VOICE_TO_VOXLANG_SYSTEM, user_prompt)


def correct_transcript(raw_transcript: str) -> str:
    return _call(VOICE_CORRECTION_SYSTEM, raw_transcript)


def explain_code(code: str) -> str:
    return _call(EXPLAIN_SYSTEM, code, max_tokens=600)


def suggest_completion(partial_code: str) -> str:
    return _call(SUGGEST_SYSTEM, partial_code, max_tokens=80)


def chat_about_voxlang(
    question: str,
    code_context: str = "",
    history: list[dict] | None = None,
) -> str:
    """
    Chat with Vox, the VoxLang AI tutor.

    Supports:
    - Multi-turn conversation via `history`
    - Injecting the user's current editor code as context
    - Informal / slang / vague questions
    - The dedicated CHAT_SYSTEM prompt (separate from voice-to-code)

    Args:
        question:     The user's latest message (any wording).
        code_context: The current code in the editor (optional).
        history:      List of prior turns: [{"role": "user"|"assistant", "content": "..."}]
                      Pass the full conversation so far for multi-turn awareness.
    """
    # Build the final user message — prepend editor code if present
    user_msg = question.strip()
    if code_context.strip():
        user_msg = (
            f"[My current VoxLang code]\n```\n{code_context.strip()}\n```\n\n"
            f"{user_msg}"
        )

    if history:
        # Multi-turn: append the new user message to existing history
        full_history = list(history) + [{"role": "user", "content": user_msg}]
        return _call_with_history(CHAT_SYSTEM, full_history, max_tokens=800)
    else:
        # Single-turn fallback
        return _call(CHAT_SYSTEM, user_msg, max_tokens=800)