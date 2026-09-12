"""backend/voice/asr_client.py — ASR client wrapper around faster-whisper.

SAMPLE RATE & AUDIO FORMAT ASSUMPTION:
--------------------------------------
This module expects raw PCM16 mono audio at a 16,000 Hz (16 kHz) sample rate
(2 bytes per sample, signed 16-bit little-endian). This format matches the
browser Web Audio API pipeline used by the VIGIL frontend audio capture.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import AsyncIterator, Any

import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)

_model_instance: Any = None


def get_model() -> Any:
    """Return singleton instance of WhisperModel, loading lazily on first access."""
    global _model_instance
    if _model_instance is None:
        try:
            from faster_whisper import WhisperModel
            logger.info("Initializing faster-whisper model '%s' on CPU (int8)...", settings.ASR_MODEL)
            _model_instance = WhisperModel(
                settings.ASR_MODEL,
                device="cpu",
                compute_type="int8",
            )
        except Exception as ex:
            logger.warning("faster-whisper model unavailable (%s). Falling back to mock transcription.", ex)
            return None
    return _model_instance


def has_speech_energy(audio_chunk: bytes, threshold: float = 500.0) -> bool:
    """Fast RMS amplitude calculation on raw PCM16 bytes.

    Used by barge-in / interruption handlers to detect voice activity quickly.

    Args:
        audio_chunk: Raw PCM16 audio bytes.
        threshold: RMS energy threshold above which speech is detected.

    Returns:
        True if RMS amplitude >= threshold, False otherwise.
    """
    if len(audio_chunk) < 2:
        return False

    # Convert bytes to 16-bit signed integer samples
    samples = np.frombuffer(audio_chunk, dtype=np.int16)
    if samples.size == 0:
        return False

    # RMS = sqrt(mean(samples^2))
    sum_squares = np.sum(samples.astype(np.float64) ** 2)
    mean_square = sum_squares / samples.size
    rms = math.sqrt(mean_square)

    return rms >= threshold


def _pcm16_to_float32(pcm16_bytes: bytes) -> np.ndarray:
    """Convert raw PCM16 bytes into normalized float32 numpy array in range [-1.0, 1.0]."""
    samples = np.frombuffer(pcm16_bytes, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


def _sync_transcribe(
    audio: np.ndarray | str | bytes,
    model_override: Any | None = None,
) -> str:
    """Synchronous transcribe helper designed to run inside a thread executor."""
    model = model_override or get_model()
    if model is None:
        return ""

    if isinstance(audio, bytes):
        audio = _pcm16_to_float32(audio)

    try:
        segments, _ = model.transcribe(
            audio,
            beam_size=1,
            language="en",
            condition_on_previous_text=False,
        )
        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(texts)
    except Exception as exc:
        logger.warning("ASR transcription error: %s", exc)
        return ""


async def transcribe_utterance(audio_bytes: bytes | str) -> str:
    """Transcribe a complete audio utterance non-blockingly using a thread executor.

    Args:
        audio_bytes: Raw PCM16 audio bytes or file path (str).

    Returns:
        Transcribed text string.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_transcribe, audio_bytes)


async def transcribe_stream(
    audio_chunks: AsyncIterator[bytes],
    end_of_utterance: asyncio.Event | None = None,
) -> AsyncIterator[str]:
    """Buffer raw PCM16 audio chunks and yield transcribed text segments periodically.

    Offloads blocking Whisper calls to a thread executor to ensure the asyncio
    event loop is never stalled.

    Args:
        audio_chunks: Async iterator yielding PCM16 audio bytes.
        end_of_utterance: Optional event signalling speech end.

    Yields:
        Transcribed text segments as produced.
    """
    buffer = bytearray()
    loop = asyncio.get_running_loop()

    # Flush every ~1.5s of 16kHz PCM16 audio = 16000 samples * 2 bytes * 1.5s = 48000 bytes
    flush_size = 48000

    async for chunk in audio_chunks:
        buffer.extend(chunk)

        is_end = end_of_utterance.is_set() if end_of_utterance else False
        if len(buffer) >= flush_size or is_end:
            if len(buffer) > 0:
                audio_data = bytes(buffer)
                buffer.clear()
                text = await loop.run_in_executor(None, _sync_transcribe, audio_data)
                if text:
                    yield text

        if is_end:
            break

    if len(buffer) > 0:
        audio_data = bytes(buffer)
        buffer.clear()
        text = await loop.run_in_executor(None, _sync_transcribe, audio_data)
        if text:
            yield text
