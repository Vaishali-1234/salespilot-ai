"""Speech-to-Text (STT) engine using Faster-Whisper with transparent status reporting."""

import io
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, Optional
import wave

import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


def _decode_audio_to_16k_mono(audio_bytes: bytes, filename: str = "recording.wav") -> np.ndarray:
    """Decode WAV or container audio into a 16kHz mono float32 numpy array without PyAV metadata_errors."""
    # Fast path: standard PCM WAV (what st.audio_input records in browsers)
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        if sampwidth == 2:
            samples = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            samples = np.frombuffer(raw_frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        elif sampwidth == 1:
            samples = (np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sampwidth}")

        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        if framerate != 16000 and len(samples) > 0:
            target_len = int(round(len(samples) * 16000 / framerate))
            x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
            samples = np.interp(x_new, x_old, samples).astype(np.float32)

        return np.ascontiguousarray(samples, dtype=np.float32)
    except wave.Error:
        pass

    # Fallback path: decode WebM/MP3/OGG via PyAV without deprecated metadata_errors kwarg
    import av

    suffix = Path(filename).suffix or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
        chunks = []
        with av.open(tmp_path, mode="r") as container:
            for frame in container.decode(audio=0):
                for resampled in resampler.resample(frame):
                    arr = resampled.to_ndarray().reshape(-1).astype(np.float32) / 32768.0
                    chunks.append(arr)
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.ascontiguousarray(np.concatenate(chunks), dtype=np.float32)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


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

        t0 = time.perf_counter()
        try:
            audio_array = _decode_audio_to_16k_mono(audio_bytes, filename=filename)
            if len(audio_array) == 0:
                return {
                    "success": False,
                    "mode": "empty_audio",
                    "text": "",
                    "language": None,
                    "duration_sec": 0.0,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "error": "Decoded audio is empty.",
                }

            segments, info = self._model.transcribe(
                audio_array,
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


stt_engine = SpeechToTextEngine()
