# backend/audio/tts.py
"""
Text-to-Speech (TTS) with audio-amplitude streaming
────────────────────────────────────────────────────
Synthesises speech via Edge-TTS, saves to a temp file, plays it back
through pyaudio while streaming amplitude values to the caller.

The `speak()` coroutine:
  1. Synthesises the text with edge-tts.
  2. Plays the audio through pyaudio chunk-by-chunk.
  3. Calls the *on_amplitude* callback with a 0–1 float on each chunk so
     the frontend can drive the audio-reactive border animation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import struct
import tempfile
from typing import Callable, Awaitable

log = logging.getLogger(__name__)

# Amplitude callback type: receives a float 0-1
AmplitudeCallback = Callable[[float], Awaitable[None]]


async def speak(
    text: str,
    voice: str = "en-US-AriaNeural",
    on_amplitude: AmplitudeCallback | None = None,
) -> None:
    """
    Synthesise *text* and play it, calling *on_amplitude* repeatedly with
    the current loudness level so the UI border can react.
    """
    if not text:
        return

    # ── Step 1: Synthesise with edge-tts ─────────────────────────────────────
    mp3_path = await _synthesise(text, voice)
    if mp3_path is None:
        log.error("TTS synthesis failed; falling back to pyttsx3")
        await _speak_pyttsx3(text)
        return

    # ── Step 2: Convert MP3 → PCM via pydub, then play with pyaudio ──────────
    try:
        from pydub import AudioSegment   # type: ignore
        import pyaudio                   # type: ignore

        # 22 050 Hz mono 16-bit: good balance of quality and CPU usage
        _SAMPLE_RATE = 22_050
        # 1024 samples ≈ 46 ms at 22 050 Hz; small enough for responsive amplitude updates
        _CHUNK_SAMPLES = 1024

        segment = AudioSegment.from_mp3(mp3_path)
        # Normalise to mono 16-bit at the target sample rate
        segment = segment.set_channels(1).set_sample_width(2).set_frame_rate(_SAMPLE_RATE)
        raw_data = segment.raw_data

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=_SAMPLE_RATE,
            output=True,
        )

        max_int16 = float(2**15)

        for i in range(0, len(raw_data), _CHUNK_SAMPLES * 2):
            chunk = raw_data[i : i + _CHUNK_SAMPLES * 2]
            stream.write(chunk)

            # Compute RMS amplitude for this chunk (0–1)
            if on_amplitude and len(chunk) >= 2:
                samples = struct.unpack_from(f"{len(chunk)//2}h", chunk)
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                amplitude = min(1.0, rms / max_int16)
                await on_amplitude(amplitude)
                # Yield to the event loop so the amplitude callback reaches
                # the WebSocket broadcast before the next audio chunk plays.
                await asyncio.sleep(0)

        stream.stop_stream()
        stream.close()
        pa.terminate()

    except ImportError as exc:
        log.warning("pydub/pyaudio not available (%s); using pyttsx3 fallback", exc)
        await _speak_pyttsx3(text)
    except Exception as exc:  # noqa: BLE001
        log.error("TTS playback error: %s", exc)
    finally:
        try:
            os.unlink(mp3_path)
        except OSError:
            pass


async def _synthesise(text: str, voice: str) -> str | None:
    """Synthesise text with edge-tts and save to a temp .mp3 file."""
    try:
        import edge_tts  # type: ignore

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)
        log.debug("TTS saved to %s", path)
        return path
    except ImportError:
        log.warning("edge-tts not installed; run: pip install edge-tts")
    except Exception as exc:  # noqa: BLE001
        log.error("edge-tts synthesis error: %s", exc)
    return None


async def _speak_pyttsx3(text: str) -> None:
    """Synchronous pyttsx3 fallback, run in a thread."""
    try:
        import pyttsx3  # type: ignore

        def _run() -> None:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()

        await asyncio.to_thread(_run)
    except ImportError:
        log.error("pyttsx3 not installed; no TTS fallback available")
    except Exception as exc:  # noqa: BLE001
        log.error("pyttsx3 error: %s", exc)
