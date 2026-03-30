/**
 * electron/preload.js
 *
 * Exposes a safe, narrow IPC bridge to the React renderer.
 * All communication passes through contextBridge so the renderer has
 * NO direct access to Node.js APIs.
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('novaAPI', {
  /**
   * Subscribe to messages pushed from the Python backend.
   * @param {(message: string) => void} callback
   * @returns {() => void} unsubscribe function
   */
  onBackendMessage (callback) {
    const handler = (_, message) => callback(message)
    ipcRenderer.on('nova:backend-message', handler)
    return () => ipcRenderer.removeListener('nova:backend-message', handler)
  },

  /**
   * Send a raw JSON string to the Python backend.
   * @param {string} payload
   */
  sendToBackend (payload) {
    ipcRenderer.send('nova:frontend-message', payload)
  },

  /**
   * Enable or disable click-through mode on the overlay window.
   * Pass true when idle so the user can click through the overlay.
   * @param {boolean} enable
   */
  setClickThrough (enable) {
    ipcRenderer.send('nova:set-clickthrough', enable)
  },
})
