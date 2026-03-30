# backend/config.py
"""
Central configuration for the Nova backend.
Copy this file to config_local.py and fill in real API keys – never commit
real secrets to version control.
"""

import os

# ── API Keys ──────────────────────────────────────────────────────────────────
# Set via environment variables or override directly here (dev only).
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# PicoVoice / Porcupine wake-word access key
PORCUPINE_ACCESS_KEY: str = os.environ.get("PORCUPINE_ACCESS_KEY", "")

# ── Wake Word ─────────────────────────────────────────────────────────────────
WAKE_WORD: str = "hey nova"
# Path to a custom .ppn model file; leave empty to use the built-in keyword
PORCUPINE_KEYWORD_PATH: str = os.environ.get("PORCUPINE_KEYWORD_PATH", "")

# ── WebSocket server ──────────────────────────────────────────────────────────
WS_HOST: str = "localhost"
WS_PORT: int = 8765

# ── TTS voice ─────────────────────────────────────────────────────────────────
# Edge-TTS voice name.  Run `edge-tts --list-voices` to see options.
TTS_VOICE: str = "en-US-AriaNeural"

# ── State machine ─────────────────────────────────────────────────────────────
# How long (seconds) Nova stays in "follow-up listening" after responding
FOLLOWUP_TIMEOUT: float = 5.0

# ── Audio ─────────────────────────────────────────────────────────────────────
# Microphone sample rate expected by Porcupine (must be 16 000)
MIC_SAMPLE_RATE: int = 16_000
MIC_FRAME_LENGTH: int = 512   # Porcupine frame length in samples
