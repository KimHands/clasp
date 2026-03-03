const { app, BrowserWindow, ipcMain, dialog, safeStorage } = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const { spawn } = require('child_process')

const isDev = process.env.NODE_ENV === 'development'

function getSettingsPath() {
  return path.join(app.getPath('userData'), 'clasp-settings.json')
}

// 암호화 저장 대상 키 목록
const ENCRYPTED_SETTING_KEYS = ['openai_api_key', 'gemini_api_key']

function loadSettings() {
  try {
    const settingsPath = getSettingsPath()
    if (fs.existsSync(settingsPath)) {
      const raw = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'))
      for (const key of ENCRYPTED_SETTING_KEYS) {
        const encKey = `${key}_encrypted`
        if (raw[encKey] && safeStorage.isEncryptionAvailable()) {
          try {
            raw[key] = safeStorage.decryptString(Buffer.from(raw[encKey], 'base64'))
          } catch (_) {
            raw[key] = null
          }
          delete raw[encKey]
        }
      }
      return raw
    }
  } catch (_) {}
  return {}
}

function saveSettings(data) {
  try {
    const settingsPath = getSettingsPath()
    fs.mkdirSync(path.dirname(settingsPath), { recursive: true })
    const toSave = { ...data }
    if (safeStorage.isEncryptionAvailable()) {
      for (const key of ENCRYPTED_SETTING_KEYS) {
        if (toSave[key]) {
          toSave[`${key}_encrypted`] = safeStorage.encryptString(toSave[key]).toString('base64')
          delete toSave[key]
        }
      }
    }
    fs.writeFileSync(settingsPath, JSON.stringify(toSave, null, 2), 'utf-8')
  } catch (e) {
    console.error('[Settings] 저장 실패:', e.message)
  }
}

let mainWindow = null
let backendProcess = null
let backendAlive = false

function startBackend() {
  if (backendProcess && backendAlive) return

  const settings = loadSettings()
  const extraEnv = {}
  if (settings.openai_api_key) {
    extraEnv.OPENAI_API_KEY = settings.openai_api_key
  }
  if (settings.gemini_api_key) {
    extraEnv.GEMINI_API_KEY = settings.gemini_api_key
  }

  if (isDev) {
    const backendDir = path.join(__dirname, '../../backend')
    backendProcess = spawn(
      path.join(backendDir, 'venv/bin/python'),
      ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'],
      { cwd: backendDir, stdio: 'pipe', env: { ...process.env, ...extraEnv } }
    )
    backendProcess.stdout.on('data', (d) => console.log('[Backend]', d.toString()))
    backendProcess.stderr.on('data', (d) => console.error('[Backend]', d.toString()))
  } else {
    const bundlePath = path.join(process.resourcesPath, 'backend', 'clasp-backend')
    backendProcess = spawn(bundlePath, [], {
      stdio: 'pipe',
      env: { ...process.env, ...extraEnv },
    })
  }

  backendAlive = true

  backendProcess.on('exit', (code) => {
    console.log(`[Backend] 종료 코드: ${code}`)
    backendAlive = false
    backendProcess = null
  })
}

function waitForBackend(maxRetries = 30, intervalMs = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0
    const check = () => {
      attempts++
      const req = http.get('http://127.0.0.1:8000/docs', (res) => {
        res.resume()
        if (res.statusCode === 200) {
          resolve()
        } else if (attempts < maxRetries) {
          setTimeout(check, intervalMs)
        } else {
          reject(new Error('백엔드 응답 없음'))
        }
      })
      req.on('error', () => {
        if (attempts < maxRetries) {
          setTimeout(check, intervalMs)
        } else {
          reject(new Error('백엔드 연결 실패'))
        }
      })
      req.end()
    }
    check()
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
const ALLOWED_ENV_KEYS = new Set(['OPENAI_API_KEY', 'GEMINI_API_KEY'])

// 각 env 키에 대응하는 백엔드 엔드포인트
const API_KEY_ENDPOINTS = {
  OPENAI_API_KEY: '/settings/api-key',
  GEMINI_API_KEY: '/settings/gemini-api-key',
}

function postApiKeyToBackend(endpoint, value) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ api_key: value || '' })
    const req = http.request(
      {
        hostname: '127.0.0.1', port: 8000, path: endpoint, method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      },
      (res) => { res.resume(); resolve() }
    )
    req.on('error', reject)
    req.write(body)
    req.end()
  })
}

// IPC: 환경변수 설정 (백엔드 HTTP 엔드포인트 + 설정 파일 저장)
ipcMain.handle('app:setEnv', async (_event, key, value) => {
  if (!ALLOWED_ENV_KEYS.has(key)) {
    return { success: false, reason: 'not_allowed' }
  }

  // 설정 파일에 저장 (앱 재시작 시에도 유지)
  const settings = loadSettings()
  const settingKey = key.toLowerCase()
  if (value) {
    settings[settingKey] = value
  } else {
    delete settings[settingKey]
  }
  saveSettings(settings)

  // 실행 중인 백엔드에 HTTP로 전달 (재시작 없이 즉시 적용)
  try {
    const endpoint = API_KEY_ENDPOINTS[key]
    if (endpoint) {
      await postApiKeyToBackend(endpoint, value)
    }
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

// 앱 시작 시 저장된 API 키를 백엔드에 주입 (개발 환경에서 백엔드를 별도 실행하는 경우 대비)
async function syncApiKeysToBackend() {
  const settings = loadSettings()
  const tasks = Object.entries(API_KEY_ENDPOINTS).map(([envKey, endpoint]) => {
    const value = settings[envKey.toLowerCase()] || ''
    return postApiKeyToBackend(endpoint, value).catch((e) => {
      console.warn(`[Settings] ${envKey} 백엔드 동기화 실패:`, e.message)
    })
  })
  await Promise.all(tasks)
}

app.whenReady().then(async () => {
  startBackend()
  try {
    await waitForBackend()
  } catch (e) {
    console.error('[Startup]', e.message)
  }
  // 백엔드 준비 완료 후 저장된 키 주입
  await syncApiKeysToBackend()
  createWindow()

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (!backendAlive) {
        startBackend()
        try { await waitForBackend() } catch (_) {}
        await syncApiKeysToBackend()
      }
      createWindow()
    }
  })
})

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
