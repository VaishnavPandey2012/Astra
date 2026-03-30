import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * useNovaState
 *
 * Manages the connection to the Python backend and exposes the current
 * Nova state (idle | listening | processing | speaking), the latest
 * transcript text, and the current audio amplitude (0-1) so the UI can
 * react dynamically.
 *
 * Communication path:
 *   Python backend  →  WebSocket  →  Electron main.js  →  IPC  →  preload.js
 *   →  window.novaAPI.onBackendMessage()  →  this hook  →  React state
 */

export const NOVA_STATES = /** @type {const} */ ({
  IDLE:       'idle',
  LISTENING:  'listening',
  PROCESSING: 'processing',
  SPEAKING:   'speaking',
})

/** WebSocket URL used when running outside of Electron (dev / testing) */
const BACKEND_WS_URL = 'ws://localhost:8765'

/** @returns {{ state: string, transcript: string, response: string, amplitude: number, sendCommand: (cmd: object) => void }} */
export function useNovaState () {
  const [state,      setState]      = useState(NOVA_STATES.IDLE)
  const [transcript, setTranscript] = useState('')
  const [response,   setResponse]   = useState('')
  const [amplitude,  setAmplitude]  = useState(0)

  const amplitudeTimer = useRef(null)

  // ── Handle messages from the backend ──────────────────────────────────────
  const handleBackendMessage = useCallback((raw) => {
    let msg
    try { msg = JSON.parse(raw) } catch { return }

    const { type, payload } = msg

    switch (type) {
      case 'state':
        setState(payload)
        // When entering idle, enable click-through on the Electron window
        if (typeof window.novaAPI !== 'undefined') {
          window.novaAPI.setClickThrough(payload === NOVA_STATES.IDLE)
        }
        break

      case 'transcript':
        setTranscript(payload)
        break

      case 'response':
        setResponse(payload)
        break

      case 'amplitude': {
        // Amplitude is 0-1 float, reset to 0 after 150 ms of silence
        setAmplitude(Number(payload))
        if (amplitudeTimer.current) clearTimeout(amplitudeTimer.current)
        amplitudeTimer.current = setTimeout(() => setAmplitude(0), 150)
        break
      }

      default:
        break
    }
  }, [])

  // ── Subscribe to the Electron IPC bridge (or fall back to a plain WS) ─────
  useEffect(() => {
    let unsubscribe = null

    if (typeof window.novaAPI !== 'undefined') {
      // Running inside Electron
      unsubscribe = window.novaAPI.onBackendMessage(handleBackendMessage)
    } else {
      // Running in a plain browser (dev / testing)
      const ws = new WebSocket(BACKEND_WS_URL)
      ws.onmessage = (e) => handleBackendMessage(e.data)
      return () => ws.close()
    }

    return () => {
      if (unsubscribe) unsubscribe()
    }
  }, [handleBackendMessage])

  // ── Expose a way for the UI to send commands back to the backend ───────────
  const sendCommand = useCallback((cmd) => {
    const payload = JSON.stringify(cmd)
    if (typeof window.novaAPI !== 'undefined') {
      window.novaAPI.sendToBackend(payload)
    }
  }, [])

  return { state, transcript, response, amplitude, sendCommand }
}
