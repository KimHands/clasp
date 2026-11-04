const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const crypto = require('crypto')
const http = require('http')
const net = require('net')
const path = require('path')
const { spawn } = require('child_process')

const isDev = process.env.NODE_ENV === 'development'
const VITE_PORT = process.env.CLASP_VITE_PORT || '5173'
const RENDERER_URL = `http://localhost:${VITE_PORT}`

let mainWindow = null
let backendProcess = null
let backendAlive = false
let backendPort = null
// 실행마다 새로 만드는 토큰. 이 값을 가진 요청만 백엔드가 받는다
const backendToken = crypto.randomBytes(32).toString('hex')

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.on('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
  })
}

function backendEnv() {
  return {
    ...process.env,
    CLASP_API_TOKEN: backendToken,
    CLASP_PORT: String(backendPort),
    CLASP_ALLOWED_ORIGIN: isDev ? RENDERER_URL : 'null',
  }
}

function spawnBackend() {
  if (isDev) {
    const backendDir = path.join(__dirname, '../../backend')
    const child = spawn(
      path.join(backendDir, 'venv/bin/python'),
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
      { cwd: backendDir, stdio: 'pipe', env: backendEnv() }
    )
    child.stdout.on('data', (d) => console.log('[Backend]', d.toString()))
    child.stderr.on('data', (d) => console.error('[Backend]', d.toString()))
    return child
  }
  const executable = process.platform === 'win32' ? 'clasp-backend.exe' : 'clasp-backend'
  const bundlePath = path.join(process.resourcesPath, 'backend', executable)
  return spawn(bundlePath, [], { stdio: 'ignore', env: backendEnv() })
}

async function startBackend() {
  if (backendProcess && backendAlive) return
  backendPort = backendPort || await findFreePort()
  backendProcess = spawnBackend()
  backendAlive = true

  backendProcess.on('error', (e) => {
    console.error('[Backend] 실행 실패:', e.message)
    backendAlive = false
    backendProcess = null
  })
  backendProcess.on('exit', (code) => {
    console.log(`[Backend] 종료 코드: ${code}`)
    backendAlive = false
    backendProcess = null
  })
}

function isClaspHealth(body) {
  try {
    return JSON.parse(body).service === 'clasp-backend'
  } catch (_) {
    return false
  }
}

function checkBackendOnce() {
  return new Promise((resolve) => {
    const req = http.get(
      {
        hostname: '127.0.0.1', port: backendPort, path: '/health',
        headers: { 'X-Clasp-Token': backendToken },
      },
      (res) => {
        let body = ''
        res.on('data', (chunk) => { body += chunk })
        res.on('end', () => resolve(res.statusCode === 200 && isClaspHealth(body)))
      }
    )
    req.on('error', () => resolve(false))
    req.end()
  })
}

async function waitForBackend(maxRetries = 120, intervalMs = 500) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    if (await checkBackendOnce()) return
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  throw new Error('백엔드 응답 없음')
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  // 파일 내용이 표시되는 창이 다른 사이트로 넘어가지 않게 막는다
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  mainWindow.webContents.on('will-navigate', (event, url) => {
    const allowed = isDev ? url.startsWith(`${RENDERER_URL}/`) : url.startsWith('file://')
    if (!allowed) event.preventDefault()
  })

  if (isDev) {
    mainWindow.loadURL(RENDERER_URL)
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

ipcMain.handle('backend:getConfig', () => ({
  baseUrl: `http://127.0.0.1:${backendPort}`,
  token: backendToken,
}))

async function startBackendAndWait() {
  await startBackend()
  try {
    await waitForBackend()
  } catch (e) {
    console.error('[Startup]', e.message)
  }
}

app.whenReady().then(async () => {
  await startBackendAndWait()
  createWindow()

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (!backendAlive) await startBackendAndWait()
      createWindow()
    }
  })
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => app.quit())
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
    backendAlive = false
  }
})
