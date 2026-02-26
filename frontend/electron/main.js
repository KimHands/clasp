import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import path from 'path'
import fs from 'fs'
import http from 'node:http'
import { spawn } from 'child_process'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const isDev = process.env.NODE_ENV === 'development'

// 설정 파일 경로 (앱 준비 후 호출)
function getSettingsPath() {
  return path.join(app.getPath('userData'), 'clasp-settings.json')
}

function loadSettings() {
  try {
    const settingsPath = getSettingsPath()
    if (fs.existsSync(settingsPath)) {
      return JSON.parse(fs.readFileSync(settingsPath, 'utf-8'))
    }
  } catch (_) {}
  return {}
}

function saveSettings(data) {
  try {
    const settingsPath = getSettingsPath()
    fs.mkdirSync(path.dirname(settingsPath), { recursive: true })
    fs.writeFileSync(settingsPath, JSON.stringify(data, null, 2), 'utf-8')
  } catch (e) {
    console.error('[Settings] 저장 실패:', e.message)
  }
}

let mainWindow = null
let backendProcess = null

function startBackend() {
  const settings = loadSettings()
  // 저장된 API Key를 백엔드 자식 프로세스의 환경변수로 주입
  const extraEnv = {}
  if (settings.openai_api_key) {
    extraEnv.OPENAI_API_KEY = settings.openai_api_key
  }

  if (isDev) {
    // 개발 환경: uvicorn 직접 실행
    const backendDir = path.join(__dirname, '../../backend')
    backendProcess = spawn(
      path.join(backendDir, 'venv/bin/python'),
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'],
      { cwd: backendDir, stdio: 'pipe', env: { ...process.env, ...extraEnv } }
    )
    backendProcess.stdout.on('data', (d) => console.log('[Backend]', d.toString()))
    backendProcess.stderr.on('data', (d) => console.error('[Backend]', d.toString()))
  } else {
    // 프로덕션: PyInstaller 번들 실행
    const bundlePath = path.join(process.resourcesPath, 'backend', 'clasp-backend')
    backendProcess = spawn(bundlePath, [], {
      stdio: 'pipe',
      env: { ...process.env, ...extraEnv },
    })
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
      preload: path.join(__dirname, 'preload.cjs'),
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

// 허용된 설정 키 화이트리스트 (보안: 임의 env 설정 방지)
const ALLOWED_ENV_KEYS = new Set(['OPENAI_API_KEY'])

// IPC: 환경변수 설정 (백엔드 HTTP 엔드포인트 + 설정 파일 저장)
ipcMain.handle('app:setEnv', async (_event, key, value) => {
  if (!ALLOWED_ENV_KEYS.has(key)) {
    return { success: false, reason: 'not_allowed' }
  }

  // 1) 설정 파일에 저장 (앱 재시작 시에도 유지)
  const settings = loadSettings()
  const settingKey = key.toLowerCase()
  if (value) {
    settings[settingKey] = value
  } else {
    delete settings[settingKey]
  }
  saveSettings(settings)

  // 2) 실행 중인 백엔드에 HTTP로 전달 (재시작 없이 즉시 적용)
  try {
    const body = JSON.stringify({ api_key: value || '' })
    await new Promise((resolve, reject) => {
      const req = http.request(
        { hostname: '127.0.0.1', port: 8000, path: '/settings/api-key', method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } },
        (res) => { res.resume(); resolve() }
      )
      req.on('error', reject)
      req.write(body)
      req.end()
    })
  } catch (e) {
    console.error('[Settings] 백엔드 API Key 전달 실패:', e.message)
  }

  return { success: true }
})

// IPC: 저장된 환경변수 읽기
ipcMain.handle('app:getEnv', async (_event, key) => {
  if (!ALLOWED_ENV_KEYS.has(key)) return null
  const settings = loadSettings()
  return settings[key.toLowerCase()] || null
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
