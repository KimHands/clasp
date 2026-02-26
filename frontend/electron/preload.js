const { contextBridge, ipcRenderer } = require('electron')

// 렌더러 프로세스에 안전하게 노출할 API
contextBridge.exposeInMainWorld('electronAPI', {
  // UC-01: 폴더 선택 다이얼로그
  openFolderDialog: () => ipcRenderer.invoke('dialog:openFolder'),
})
