const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow = null
let backendProcess = null

function startBackend() {
  if (isDev) {
    // 개발 환경: uvicorn 직접 실행
    const backendDir = path.join(__dirname, '../../backend')
    backendProcess = spawn(
      path.join(backendDir, 'venv/bin/python'),
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'],
      { cwd: backendDir, stdio: 'pipe' }
    )
    backendProcess.stdout.on('data', (d) => console.log('[Backend]', d.toString()))
    backendProcess.stderr.on('data', (d) => console.error('[Backend]', d.toString()))
  } else {
    // 프로덕션: PyInstaller 번들 실행
    const bundlePath = path.join(process.resourcesPath, 'backend', 'clasp-backend')
    backendProcess = spawn(bundlePath, [], { stdio: 'pipe' })
  }

  backendProcess.on('exit', (code) => {
    console.log(`[Backend] 종료 코드: ${code}`)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// IPC: 폴더 선택 다이얼로그 (UC-01)
ipcMain.handle('dialog:openFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: '정리할 폴더를 선택하세요',
  })
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  return result.filePaths[0]
})

app.whenReady().then(() => {
  startBackend()
  // 백엔드 기동 대기 후 윈도우 생성
  setTimeout(createWindow, isDev ? 1500 : 3000)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
})
