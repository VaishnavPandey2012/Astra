# backend/state_machine.py
"""
Nova State Machine
──────────────────
Manages the five states Nova can be in and enforces the follow-up listening
window after a response.

States
------
IDLE        – invisible overlay, wake-word listener active
LISTENING   – glowing border pulses, STT running
PROCESSING  – gradient swirls fast, Gemini request in-flight
SPEAKING    – border reacts to TTS amplitude
FOLLOWUP    – same UI as LISTENING but no wake-word needed
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto
from typing import Callable, Awaitable

log = logging.getLogger(__name__)


class State(str, Enum):
    IDLE       = "idle"
    LISTENING  = "listening"
    PROCESSING = "processing"
    SPEAKING   = "speaking"
    FOLLOWUP   = "followup"   # treated as "listening" by the frontend


# Type alias for async state-change callback
StateCallback = Callable[[State], Awaitable[None]]


class StateMachine:
    """Thread-safe asyncio state machine for Nova."""

    def __init__(self, on_state_change: StateCallback, followup_timeout: float = 5.0) -> None:
        self._state = State.IDLE
        self._on_change = on_state_change
        self._followup_timeout = followup_timeout
        self._followup_task: asyncio.Task | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    async def transition(self, new_state: State) -> None:
        """Transition to *new_state*, cancelling any pending follow-up timer."""
        if self._state == new_state:
            return

        log.info("State: %s → %s", self._state.value, new_state.value)
        self._cancel_followup()
        self._state = new_state
        await self._on_change(new_state)

    async def start_followup(self) -> None:
        """
        Transition to FOLLOWUP then automatically return to IDLE after
        FOLLOWUP_TIMEOUT seconds if no new command arrives.
        """
        await self.transition(State.FOLLOWUP)
        self._followup_task = asyncio.create_task(self._followup_timer())

    async def cancel_followup(self) -> None:
        """Manually cancel the follow-up window (e.g. a new command arrived)."""
        self._cancel_followup()
        await self.transition(State.IDLE)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _cancel_followup(self) -> None:
        if self._followup_task and not self._followup_task.done():
            self._followup_task.cancel()
            self._followup_task = None

    async def _followup_timer(self) -> None:
        try:
            await asyncio.sleep(self._followup_timeout)
            log.info("Follow-up window expired, returning to IDLE")
            await self.transition(State.IDLE)
        except asyncio.CancelledError:
            pass
