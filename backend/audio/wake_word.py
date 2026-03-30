# backend/audio/wake_word.py
"""
Wake-Word Detector
──────────────────
Runs PicoVoice Porcupine in a dedicated daemon thread, emitting an asyncio
Event when "Hey Nova" is detected.

If Porcupine is not installed or the access key is missing, the module
falls back to a simple keyword search via SpeechRecognition so the rest of
the pipeline can still be developed / tested without a paid Porcupine key.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import threading
from typing import Callable

log = logging.getLogger(__name__)


# ── Porcupine wrapper ─────────────────────────────────────────────────────────

class WakeWordDetector:
    """
    Listens for the wake word on a background daemon thread.

    Parameters
    ----------
    access_key:       PicoVoice access key (ignored in fallback mode).
    keyword_path:     Path to a .ppn file; uses built-in "Hey Nova" if empty.
    on_detected:      Async callback – called (thread-safely) when wake word fires.
    loop:             The running asyncio event loop.
    """

    def __init__(
        self,
        access_key: str,
        keyword_path: str,
        on_detected: Callable[[], None],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._access_key   = access_key
        self._keyword_path = keyword_path
        self._on_detected  = on_detected
        self._loop         = loop
        self._running      = False
        self._thread: threading.Thread | None = None
        self._use_fallback = False

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="wake-word")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            self._run_porcupine()
        except Exception as exc:  # noqa: BLE001
            log.warning("Porcupine unavailable (%s) – falling back to SpeechRecognition", exc)
            self._run_fallback()

    def _run_porcupine(self) -> None:
        import pvporcupine  # type: ignore
        import pyaudio      # type: ignore

        keyword = self._keyword_path if self._keyword_path else "hey nova"

        if self._keyword_path:
            porcupine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=[self._keyword_path],
            )
        else:
            porcupine = pvporcupine.create(
                access_key=self._access_key,
                keywords=[keyword],
            )

        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )

        log.info("Wake-word detector running (Porcupine, keyword=%s)", keyword)
        try:
            while self._running:
                raw = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * porcupine.frame_length, raw)
                result = porcupine.process(pcm)
                if result >= 0:
                    log.info("Wake word detected!")
                    self._fire()
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            porcupine.delete()

    def _run_fallback(self) -> None:
        """
        Fallback: use SpeechRecognition with Google STT to detect a phrase
        containing 'nova'. Much higher latency – only for development.
        """
        import speech_recognition as sr  # type: ignore

        recogniser = sr.Recognizer()
        mic = sr.Microphone()

        log.info("Wake-word detector running (SpeechRecognition fallback)")
        with mic as source:
            recogniser.adjust_for_ambient_noise(source, duration=1)

        while self._running:
            try:
                with mic as source:
                    audio = recogniser.listen(source, timeout=5, phrase_time_limit=4)
                text = recogniser.recognize_google(audio).lower()
                log.debug("Fallback heard: %s", text)
                if "nova" in text:
                    log.info("Wake word detected (fallback)!")
                    self._fire()
            except Exception:  # noqa: BLE001
                pass  # timeout / recognition errors are expected

    def _fire(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self._async_fire(), self._loop
        )

    async def _async_fire(self) -> None:
        self._on_detected()
