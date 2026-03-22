"""
VoxLang – Speech-to-Text (STT)
================================
Deepgram Nova-2 transcription with multi-format fallback.
Returns TranscriptResult with text + confidence score.
"""

import httpx
from dataclasses import dataclass
from shared.config import DEEPGRAM_API_KEY, CONFIDENCE_THRESHOLD


@dataclass
class TranscriptResult:
    text:           str
    confidence:     float
    provider:       str
    low_confidence: bool = False

    def __post_init__(self):
        self.low_confidence = self.confidence < CONFIDENCE_THRESHOLD


async def transcribe(audio_bytes: bytes, mime_type: str = "audio/webm") -> TranscriptResult:
    formats_to_try = [
        (mime_type, {}),
        ("audio/webm", {}),
        ("audio/wav",  {}),
        ("audio/ogg",  {}),
    ]
    last_error = None
    for content_type, extra_params in formats_to_try:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={
                        "Authorization": f"Token {DEEPGRAM_API_KEY}",
                        "Content-Type":  content_type,
                    },
                    params={
                        "model":        "nova-2",
                        "language":     "en",
                        "smart_format": "true",
                        **extra_params,
                    },
                    content=audio_bytes,
                )
            if response.status_code == 200:
                data = response.json()
                try:
                    alt  = data["results"]["channels"][0]["alternatives"][0]
                    text = alt.get("transcript", "").strip()
                    conf = alt.get("confidence", 0.8)
                except (KeyError, IndexError):
                    text = ""
                    conf = 0.0
                return TranscriptResult(
                    text=text,
                    confidence=conf,
                    provider="deepgram",
                )
            last_error = f"Deepgram error {response.status_code}: {response.text}"
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(f"All audio formats failed. Last error: {last_error}")