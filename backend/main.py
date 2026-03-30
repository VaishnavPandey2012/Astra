# backend/main.py
"""
Nova – Python Backend
─────────────────────
Entry point for the Nova voice assistant backend.

Responsibilities:
  1. Start an asyncio WebSocket server on localhost:8765 that the Electron
     main process connects to.
  2. Manage the state machine (IDLE → LISTENING → PROCESSING → SPEAKING →
     FOLLOWUP → IDLE).
  3. Run wake-word detection in a background thread.
  4. Orchestrate the audio pipeline: STT → Gemini AI → TTS.
  5. Dispatch OS-level actions returned by Gemini.
  6. Stream state changes and amplitude values to all connected frontends.

IPC message format (JSON over WebSocket)
─────────────────────────────────────────
Backend → Frontend:
  { "type": "state",      "payload": "listening" }
  { "type": "transcript", "payload": "Set the volume to 50" }
  { "type": "response",   "payload": "Done! Volume set to 50%." }
  { "type": "amplitude",  "payload": 0.42 }

Frontend → Backend:
  { "type": "command", "payload": "..." }   (manual text command, future use)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Set

import websockets  # type: ignore
from websockets.server import WebSocketServerProtocol

import config
from ai.gemini import GeminiClient
from audio.stt import listen_once
from audio.tts import speak
from audio.wake_word import WakeWordDetector
from os_control import apps, brightness, volume
from state_machine import State, StateMachine

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("nova.main")

# ── Globals ───────────────────────────────────────────────────────────────────
_connected_clients: Set[WebSocketServerProtocol] = set()
_conversation_history: list[dict[str, str]] = []
_wake_event: asyncio.Event

# Maximum number of messages (user + model) retained in history (= 10 turns)
_MAX_HISTORY_MESSAGES = 20


# ── Conversation helpers ──────────────────────────────────────────────────────

def _append_history(user_text: str, model_text: str) -> None:
    """Append a user/model turn and trim to the rolling window."""
    global _conversation_history
    _conversation_history.append({"role": "user",  "content": user_text})
    _conversation_history.append({"role": "model", "content": model_text})
    _conversation_history = _conversation_history[-_MAX_HISTORY_MESSAGES:]


# ── Broadcast helpers ─────────────────────────────────────────────────────────

async def broadcast(msg_type: str, payload) -> None:
    """Send a JSON message to all connected WebSocket clients."""
    if not _connected_clients:
        return
    message = json.dumps({"type": msg_type, "payload": payload})
    await asyncio.gather(
        *[client.send(message) for client in list(_connected_clients)],
        return_exceptions=True,
    )


async def send_state(state: State) -> None:
    # Map FOLLOWUP → listening so the frontend renders the listening animation
    frontend_state = "listening" if state == State.FOLLOWUP else state.value
    await broadcast("state", frontend_state)


# ── Action dispatcher ─────────────────────────────────────────────────────────

DESTRUCTIVE_ACTIONS = {"close_app"}

async def dispatch_actions(actions: list[dict], state_machine: StateMachine) -> str | None:
    """
    Execute OS actions returned by Gemini.
    For destructive actions, broadcast a confirmation request and wait for
    a 'confirm' message from the frontend before proceeding.

    Returns a confirmation text to speak, or None.
    """
    results = []

    for action in actions:
        action_type = action.get("type", "")

        if action_type == "volume":
            val = int(action.get("value", 50))
            ok = await asyncio.to_thread(volume.set_volume, val)
            results.append(f"Volume {'set to ' + str(val) + '%' if ok else 'change failed'}.")

        elif action_type == "brightness":
            val = int(action.get("value", 50))
            ok = await asyncio.to_thread(brightness.set_brightness, val)
            results.append(f"Brightness {'set to ' + str(val) + '%' if ok else 'change failed'}.")

        elif action_type == "open_app":
            name = action.get("name", "")
            ok = await asyncio.to_thread(apps.open_app, name)
            results.append(f"{'Opened' if ok else 'Could not open'} {name}.")

        elif action_type == "close_app":
            # Destructive – confirm first
            name = action.get("name", "")
            confirmed = await _request_confirmation(
                f"Are you sure you want to close {name}?",
                state_machine,
            )
            if confirmed:
                ok = await asyncio.to_thread(apps.close_app, name)
                results.append(f"{'Closed' if ok else 'Could not close'} {name}.")
            else:
                results.append(f"Okay, I won't close {name}.")

        elif action_type == "search_web":
            query = action.get("query", "")
            await asyncio.to_thread(apps.search_web, query)
            results.append(f"Searching the web for {query}.")

        else:
            log.warning("Unknown action type: %s", action_type)

    return " ".join(results) if results else None


async def _request_confirmation(prompt: str, state_machine: StateMachine) -> bool:
    """
    Ask the user for verbal confirmation.
    Speak the prompt, enter LISTENING state, wait for yes/no.
    """
    await state_machine.transition(State.SPEAKING)
    await broadcast("response", prompt)
    await speak(prompt, voice=config.TTS_VOICE)

    await state_machine.transition(State.LISTENING)
    answer = await asyncio.to_thread(listen_once, timeout=6.0, phrase_time_limit=4.0)
    if answer and any(w in answer.lower() for w in ("yes", "yeah", "sure", "confirm", "do it")):
        return True
    return False


# ── Core assistant loop ───────────────────────────────────────────────────────

async def run_assistant(state_machine: StateMachine) -> None:
    """
    Main coroutine that drives the voice pipeline after the wake word fires.
    """
    global _conversation_history

    gemini = GeminiClient(api_key=config.GEMINI_API_KEY)

    while True:
        # ── Wait for wake word (or follow-up) ──────────────────────────────
        log.info("Waiting for wake word…")
        await state_machine.transition(State.IDLE)
        await _wake_event.wait()
        _wake_event.clear()

        # ── STT ────────────────────────────────────────────────────────────
        await state_machine.transition(State.LISTENING)
        log.info("Listening for command…")
        text = await asyncio.to_thread(
            listen_once,
            timeout=8.0,
            phrase_time_limit=12.0,
        )

        if not text:
            log.info("No speech detected, returning to idle")
            continue

        await broadcast("transcript", text)
        log.info("User said: %r", text)

        # ── Gemini ─────────────────────────────────────────────────────────
        await state_machine.transition(State.PROCESSING)
        response = await gemini.chat(text, history=_conversation_history)

        reply   = response.get("reply", "")
        actions = response.get("actions", [])

        # Update conversation history (keep last 10 turns = 20 messages to avoid token overflow)
        _append_history(text, reply)

        # ── Dispatch OS actions ────────────────────────────────────────────
        action_summary = await dispatch_actions(actions, state_machine)
        if action_summary:
            reply = reply + " " + action_summary if reply else action_summary

        # ── TTS ────────────────────────────────────────────────────────────
        await state_machine.transition(State.SPEAKING)
        await broadcast("response", reply)

        async def on_amplitude(amp: float) -> None:
            await broadcast("amplitude", round(amp, 3))

        await speak(reply, voice=config.TTS_VOICE, on_amplitude=on_amplitude)

        # ── Follow-up window ───────────────────────────────────────────────
        log.info("Entering follow-up listening window (%.1fs)…", config.FOLLOWUP_TIMEOUT)
        await state_machine.start_followup()

        # Listen for a follow-up command within the window
        follow_text = await asyncio.to_thread(
            listen_once,
            timeout=config.FOLLOWUP_TIMEOUT,
            phrase_time_limit=12.0,
        )

        if follow_text:
            log.info("Follow-up command: %r", follow_text)
            # Cancel the follow-up timer and feed the text back into the loop
            await state_machine.cancel_followup()
            _wake_event.set()
            # Patch: schedule the follow-up through the same loop by
            # temporarily storing the text so `listen_once` is bypassed.
            # We do this by re-triggering after transition to LISTENING.
            await state_machine.transition(State.LISTENING)
            await broadcast("transcript", follow_text)

            await state_machine.transition(State.PROCESSING)
            response2 = await gemini.chat(follow_text, history=_conversation_history)
            reply2   = response2.get("reply", "")
            actions2 = response2.get("actions", [])

            _append_history(follow_text, reply2)

            action_summary2 = await dispatch_actions(actions2, state_machine)
            if action_summary2:
                reply2 = reply2 + " " + action_summary2 if reply2 else action_summary2

            await state_machine.transition(State.SPEAKING)
            await broadcast("response", reply2)
            await speak(reply2, voice=config.TTS_VOICE, on_amplitude=on_amplitude)

        # Return to idle; the loop restarts, waiting for the wake word
        await state_machine.transition(State.IDLE)


# ── WebSocket server ──────────────────────────────────────────────────────────

async def ws_handler(websocket: WebSocketServerProtocol) -> None:
    """Handle a single WebSocket connection from the Electron frontend."""
    _connected_clients.add(websocket)
    log.info("Frontend connected (%d total)", len(_connected_clients))
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                if msg.get("type") == "command":
                    # Future: allow the UI to inject text commands manually
                    log.info("Frontend command: %s", msg.get("payload"))
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _connected_clients.discard(websocket)
        log.info("Frontend disconnected (%d total)", len(_connected_clients))


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    global _wake_event
    _wake_event = asyncio.Event()

    loop = asyncio.get_running_loop()

    # Set up state machine
    state_machine = StateMachine(
        on_state_change=send_state,
        followup_timeout=config.FOLLOWUP_TIMEOUT,
    )

    # Set up wake-word detector
    def on_wake_word() -> None:
        log.info("Wake word callback fired")
        _wake_event.set()

    detector = WakeWordDetector(
        access_key=config.PORCUPINE_ACCESS_KEY,
        keyword_path=config.PORCUPINE_KEYWORD_PATH,
        on_detected=on_wake_word,
        loop=loop,
    )
    detector.start()

    # Start the WebSocket server
    log.info("Starting WebSocket server on ws://%s:%d", config.WS_HOST, config.WS_PORT)
    async with websockets.serve(ws_handler, config.WS_HOST, config.WS_PORT):
        log.info("Nova backend ready. Say 'Hey Nova' to begin.")
        await run_assistant(state_machine)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Nova backend stopped.")
