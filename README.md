# Nova – AI-Powered Desktop Voice Assistant

Nova is a next-generation, standalone PC voice assistant with an Apple
Intelligence–style animated overlay UI. It runs as a transparent, fullscreen
Electron window on top of your desktop and listens for "Hey Nova" to activate.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│  Electron (overlay window)                       │
│  ┌────────────────────────────────────────────┐  │
│  │  React + Tailwind + Framer Motion (UI)     │  │
│  │  - NovaOverlay: glowing border animation   │  │
│  │  - useNovaState: backend state consumer    │  │
│  └────────────────────────────────────────────┘  │
│              IPC (contextBridge)                  │
│  ┌────────────────────────────────────────────┐  │
│  │  electron/main.js (WebSocket bridge)       │  │
│  └────────────────────────────────────────────┘  │
└─────────────────────┬────────────────────────────┘
                 WebSocket (ws://localhost:8765)
┌─────────────────────▼────────────────────────────┐
│  Python Backend (asyncio)                        │
│  - Wake-word detection (PicoVoice Porcupine)     │
│  - STT (SpeechRecognition)                       │
│  - Gemini AI (google-generativeai)               │
│  - TTS (edge-tts / pyttsx3)                      │
│  - OS controls (volume, brightness, apps)        │
│  - State machine (IDLE→LISTENING→PROCESSING→     │
│                   SPEAKING→FOLLOWUP)             │
└──────────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Node.js | ≥ 18 |
| npm | ≥ 9 |
| Python | ≥ 3.10 |
| pip | latest |

---

## Quick Start

### 1. Clone & Install JS Dependencies

```bash
git clone <repo-url>
cd nova
npm install
```

### 2. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

> **Note:** `pyaudio` may require additional system libraries:
> - **Windows:** download the matching `.whl` from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
> - **macOS:** `brew install portaudio && pip install pyaudio`
> - **Linux:** `sudo apt install portaudio19-dev python3-dev && pip install pyaudio`

### 3. Configure API Keys

Open `backend/config.py` and set your keys, **or** export environment variables:

```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key"

# Optional (enables proper wake-word detection)
export PORCUPINE_ACCESS_KEY="your-porcupine-access-key"
```

Get a free Gemini API key at https://aistudio.google.com/
Get a free Porcupine access key at https://console.picovoice.ai/

> ⚠️ **Never commit real API keys** to version control. Use environment
> variables or a local `backend/config_local.py` (already git-ignored).

### 4. Run in Development Mode

```bash
# Terminal 1 – Python backend
cd backend && python main.py

# Terminal 2 – Electron + React
npm run dev
```

Or start everything with one command (requires both Python and Node in PATH):

```bash
npm run dev
```

---

## Visual States

| State | UI Behaviour |
|-------|-------------|
| **Idle** | Window is fully transparent and click-through |
| **Listening** | Screen edges glow and pulse with a multicolour gradient |
| **Processing** | Gradient swirls rapidly around the screen edges |
| **Speaking** | Glowing border reacts dynamically to TTS amplitude |

---

## Supported Voice Commands (examples)

| Command | Action |
|---------|--------|
| "Set volume to 70" | Sets master volume to 70% |
| "Increase brightness to 80" | Sets display brightness to 80% |
| "Open Notepad" | Launches Notepad |
| "Open Chrome" | Launches Google Chrome |
| "Close Spotify" | Closes Spotify (asks for confirmation) |
| "Search for Python tutorials" | Opens browser with Google search |
| Anything else | Natural conversation via Gemini AI |

---

## Project Structure

```
nova/
├── electron/
│   ├── main.js          # Electron main process (transparent window + WS bridge)
│   └── preload.js       # Secure IPC bridge via contextBridge
├── src/
│   ├── App.jsx
│   ├── main.jsx
│   ├── index.css        # Tailwind + glow strip keyframes
│   ├── components/
│   │   └── NovaOverlay.jsx   # Framer Motion animated glowing border
│   └── hooks/
│       └── useNovaState.js   # Backend state consumer hook
├── backend/
│   ├── main.py          # asyncio WebSocket server + voice pipeline
│   ├── config.py        # Centralised configuration
│   ├── state_machine.py # State machine (IDLE/LISTENING/PROCESSING/SPEAKING/FOLLOWUP)
│   ├── audio/
│   │   ├── wake_word.py # Porcupine wake-word detector (+ SR fallback)
│   │   ├── stt.py       # Speech-to-text (SpeechRecognition)
│   │   └── tts.py       # Text-to-speech (edge-tts + amplitude streaming)
│   ├── ai/
│   │   └── gemini.py    # Google Gemini API integration
│   ├── os_control/
│   │   ├── volume.py    # Volume control (pycaw/osascript/amixer)
│   │   ├── brightness.py # Brightness control (sbc/wmi/xrandr)
│   │   └── apps.py      # App launch/close + web search
│   └── requirements.txt
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

---

## Building for Distribution

```bash
npm run electron:preview   # local preview
npm run build              # build React only
```

Use [electron-builder](https://www.electron.build/) for full installers:

```bash
npx electron-builder
```

---

## License

MIT