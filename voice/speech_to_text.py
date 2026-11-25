"""Speech-to-Text (STT) engine using Faster-Whisper with transparent status reporting."""

import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


class SpeechToTextEngine:
    """Lazy-loading Faster-Whisper transcription engine."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ) -> None:
        self.model_size = model_size or settings.whisper_model_size
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        self._model = None
        self.load_error: Optional[str] = None

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if self.load_error is not None:
            return False
        try:
            from faster_whisper import WhisperModel

            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    local_files_only=True,
                )
            except Exception:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            logger.info(
                "Loaded Faster-Whisper model='%s' (device=%s, compute=%s)",
                self.model_size,
                self.device,
                self.compute_type,
            )
            return True
        except Exception as exc:
            self.load_error = str(exc)
            logger.warning("Faster-Whisper unavailable: %s", exc)
            return False

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "recording.wav",
        language: Optional[str] = "en",
    ) -> Dict[str, Any]:
        """Transcribe uploaded/recorded audio bytes into text."""
        if not audio_bytes:
            return {
                "success": False,
                "mode": "empty_audio",
                "text": "",
                "language": None,
                "duration_sec": 0.0,
                "latency_ms": 0.0,
                "error": "No audio bytes provided.",
            }

        if not self._ensure_model():
            return {
                "success": False,
                "mode": "stt_unavailable",
                "text": "",
                "language": None,
                "duration_sec": 0.0,
                "latency_ms": 0.0,
                "error": (
                    f"Faster-Whisper model could not be loaded ({self.load_error}). "
                    "Please use the text chat input fallback."
                ),
            }

        suffix = Path(filename).suffix or ".wav"
        tmp_path = None
        t0 = time.perf_counter()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            segments, info = self._model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                vad_filter=True,
            )
            transcript = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            if not transcript:
                return {
                    "success": False,
                    "mode": "faster_whisper",
                    "text": "",
                    "language": getattr(info, "language", language),
                    "duration_sec": round(getattr(info, "duration", 0.0), 2),
                    "latency_ms": latency_ms,
                    "error": "No clear speech detected in the audio recording.",
                }

            return {
                "success": True,
                "mode": "faster_whisper",
                "text": transcript,
                "language": getattr(info, "language", language),
                "duration_sec": round(getattr(info, "duration", 0.0), 2),
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as exc:
            logger.exception("Whisper transcription failed")
            return {
                "success": False,
                "mode": "stt_error",
                "text": "",
                "language": None,
                "duration_sec": 0.0,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"Transcription error: {exc}",
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


stt_engine = SpeechToTextEngine()
