"""Text-to-Speech (TTS) engine using Edge TTS with graceful offline fallback."""

import asyncio
import io
import logging
import re
import time
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


def _clean_for_speech(text: str) -> str:
    """Strip markdown symbols and source tags so spoken output sounds natural."""
    cleaned = re.sub(r"\[Source:[^\]]+\]", "", text)
    cleaned = re.sub(r"[*_`#>]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class TextToSpeechEngine:
    """Synthesizes natural conversational speech audio via Microsoft Edge TTS."""

    def __init__(self, voice: Optional[str] = None) -> None:
        self.voice = voice or settings.edge_tts_voice

    async def synthesize_async(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate MP3 audio bytes for the given response text."""
        spoken_text = _clean_for_speech(text)
        if not spoken_text:
            return {
                "success": False,
                "mode": "empty_text",
                "audio_bytes": b"",
                "mime_type": "audio/mpeg",
                "voice": voice or self.voice,
                "latency_ms": 0.0,
                "error": "No speakable text provided.",
            }

        target_voice = voice or self.voice
        t0 = time.perf_counter()
        try:
            import edge_tts

            communicate = edge_tts.Communicate(spoken_text, target_voice)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            audio_bytes = buffer.getvalue()
            if not audio_bytes:
                raise RuntimeError("Edge TTS returned empty audio stream.")

            return {
                "success": True,
                "mode": "edge_tts",
                "audio_bytes": audio_bytes,
                "mime_type": "audio/mpeg",
                "voice": target_voice,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": None,
            }
        except Exception as exc:
            logger.warning("Edge TTS synthesis failed (%s); falling back to text-only.", exc)
            return {
                "success": False,
                "mode": "tts_unavailable",
                "audio_bytes": b"",
                "mime_type": "audio/mpeg",
                "voice": target_voice,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"Edge TTS unavailable ({exc}). Displaying text response.",
            }

    def synthesize_sync(self, text: str, voice: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous helper safe to call from Streamlit or non-async workers."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(self.synthesize_async(text, voice))).result()
        return asyncio.run(self.synthesize_async(text, voice))


tts_engine = TextToSpeechEngine()
