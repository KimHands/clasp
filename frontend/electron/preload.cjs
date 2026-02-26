const { contextBridge, ipcRenderer } = require('electron')

// 렌더러 프로세스에 안전하게 노출할 API
contextBridge.exposeInMainWorld('electronAPI', {
  // UC-01: 폴더 선택 다이얼로그
  openFolderDialog: () => ipcRenderer.invoke('dialog:openFolder'),
  // 설정: 백엔드 환경변수 전달 (허용된 키만 처리)
  setEnv: (key, value) => ipcRenderer.invoke('app:setEnv', key, value),
  getEnv: (key) => ipcRenderer.invoke('app:getEnv', key),
})
