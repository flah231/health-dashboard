const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  openDataDir: () => ipcRenderer.invoke('open-data-dir'),
})