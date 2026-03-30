# backend/audio/stt.py
"""
Speech-to-Text (STT)
────────────────────
Records a single utterance from the default microphone and returns the
transcribed text.

Primary engine: SpeechRecognition (Google Web Speech API).
The function is designed to be called from an asyncio context via
asyncio.to_thread() so it doesn't block the event loop.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def listen_once(
    *,
    timeout: float = 8.0,
    phrase_time_limit: float = 12.0,
    energy_threshold: int | None = None,
) -> str | None:
    """
    Block until the user speaks and return the transcribed text, or None
    on failure.

    Parameters
    ----------
    timeout:           Seconds to wait for speech to start.
    phrase_time_limit: Maximum seconds allowed for a single phrase.
    energy_threshold:  Override the dynamic energy threshold if set.
    """
    try:
        import speech_recognition as sr  # type: ignore
    except ImportError:
        log.error("SpeechRecognition not installed; run: pip install SpeechRecognition pyaudio")
        return None

    recogniser = sr.Recognizer()
    recogniser.dynamic_energy_threshold = True
    if energy_threshold is not None:
        recogniser.energy_threshold = energy_threshold

    mic = sr.Microphone()

    try:
        with mic as source:
            log.debug("Adjusting for ambient noise…")
            recogniser.adjust_for_ambient_noise(source, duration=0.5)
            log.debug("Listening for speech (timeout=%ss, max=%ss)…", timeout, phrase_time_limit)
            audio = recogniser.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )

        log.debug("Recognising…")
        text = recogniser.recognize_google(audio)
        log.info("STT result: %r", text)
        return text

    except sr.WaitTimeoutError:
        log.debug("STT: no speech detected within timeout")
        return None
    except sr.UnknownValueError:
        log.debug("STT: speech was unintelligible")
        return None
    except sr.RequestError as exc:
        log.error("STT request failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        log.error("STT unexpected error: %s", exc)
        return None
