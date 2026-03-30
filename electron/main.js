/**
 * electron/main.js
 *
 * Electron main process for Nova.
 *
 * Creates a frameless, transparent, fullscreen overlay window that is
 * click-through in the idle state. A WebSocket connection is maintained
 * to the Python backend (ws://localhost:8765). Messages received from
 * Python are forwarded to the renderer via IPC, and vice-versa.
 */

const { app, BrowserWindow, ipcMain, screen } = require('electron')
const path  = require('path')
const { WebSocket } = require('ws')
const { spawn } = require('child_process')

// ─── Constants ───────────────────────────────────────────────────────────────
const PYTHON_WS_URL   = 'ws://localhost:8765'
const RECONNECT_DELAY = 2000 // ms

let mainWindow = null
let pythonProcess = null
let wsClient = null

// ─── Python backend lifecycle ─────────────────────────────────────────────────
function startPythonBackend () {
  const backendEntry = path.join(__dirname, '..', 'backend', 'main.py')
  pythonProcess = spawn('python', [backendEntry], {
    cwd: path.join(__dirname, '..', 'backend'),
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  pythonProcess.stdout.on('data', (d) => process.stdout.write(`[Python] ${d}`))
  pythonProcess.stderr.on('data', (d) => process.stderr.write(`[Python ERR] ${d}`))

  pythonProcess.on('exit', (code) => {
    console.log(`[Electron] Python backend exited with code ${code}`)
  })
}

// ─── WebSocket bridge ─────────────────────────────────────────────────────────
function connectWebSocket () {
  wsClient = new WebSocket(PYTHON_WS_URL)

  wsClient.on('open', () => {
    console.log('[Electron] Connected to Python backend via WebSocket')
  })

  wsClient.on('message', (data) => {
    // Forward backend messages to renderer
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('nova:backend-message', data.toString())
    }
  })

  wsClient.on('close', () => {
    console.log('[Electron] WS closed, reconnecting…')
    setTimeout(connectWebSocket, RECONNECT_DELAY)
  })

  wsClient.on('error', () => {
    // Silence ECONNREFUSED noise while Python is starting up
    wsClient.terminate()
  })
}

// ─── IPC: renderer → Python ───────────────────────────────────────────────────
ipcMain.on('nova:frontend-message', (_, payload) => {
  if (wsClient && wsClient.readyState === WebSocket.OPEN) {
    wsClient.send(payload)
  }
})

// ─── Window helpers ───────────────────────────────────────────────────────────
/**
 * Toggle whether the window ignores mouse events (click-through).
 * In idle state Nova should be completely transparent AND click-through so
 * the user can interact with everything behind it normally.
 */
ipcMain.on('nova:set-clickthrough', (_, enable) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.setIgnoreMouseEvents(enable, { forward: true })
  }
})

// ─── Create main window ───────────────────────────────────────────────────────
function createWindow () {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize

  mainWindow = new BrowserWindow({
    width,
    height,
    x: 0,
    y: 0,
    fullscreen: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // Start in click-through mode (idle)
  mainWindow.setIgnoreMouseEvents(true, { forward: true })

  // Load the React app
  const isDev = !app.isPackaged
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
}

// ─── App lifecycle ────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  startPythonBackend()

  // Give Python a moment to start, then connect WebSocket
  setTimeout(connectWebSocket, 1500)

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (wsClient) wsClient.close()
  if (pythonProcess) pythonProcess.kill()
})
