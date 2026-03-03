# Clasp Electron 실행 오류 디버깅 기록

## 환경

| 항목 | 버전 |
|------|------|
| Electron | 40.6.1 |
| Node.js (Electron 내장) | v24.13.1 |
| Vite | 7.3.1 |
| OS | macOS (darwin 25.2.0) |
| package.json `"type"` | `"module"` |

---

## 핵심 문제

`package.json`에 `"type": "module"`이 설정된 Electron 프로젝트에서, Electron 메인 프로세스가 `electron` 모듈을 올바르게 import하지 못하는 문제.

---

## 에러 히스토리 및 원인 분석

### 1차: ESM 파일에서 `require()` 사용

**파일**: `electron/main.js` (ESM으로 취급됨)

```
ReferenceError: require is not defined in ES module scope
```

**원인**: `"type": "module"` 설정으로 인해 `.js` 파일이 ESM으로 로드되어 `require()` 사용 불가.

---

### 2차: `.cjs` 파일로 변경 후 `app` undefined

**파일**: `electron/main.cjs` (CJS)

```
TypeError: Cannot read properties of undefined (reading 'getPath')
```

**원인**: `require('electron')`이 Electron API 객체 대신 npm 패키지의 stub(바이너리 경로 문자열)을 반환. 문자열을 destructuring하면 모든 속성이 `undefined`.

```js
// node_modules/electron/index.js 가 반환하는 것:
module.exports = getElectronPath()  // → "/path/to/electron/binary" (문자열)

// 문자열 destructuring 결과:
const { app, ipcMain } = "/path/to/electron"
// app = undefined, ipcMain = undefined
```

**당시 상황**: 포트 충돌 등 환경 문제가 겹쳐 Electron의 CJS 모듈 패치가 정상 동작하지 않는 것으로 오인.

---

### 3차: ESM named import 시도

**파일**: `electron/main.js` (ESM)

```
SyntaxError: The requested module 'electron' does not provide an export named 'BrowserWindow'
```

**원인**: Electron 40의 `electron` 모듈은 ESM named export를 제공하지 않음. default export만 존재.

```js
// ❌ 실패 — named export 미지원
import { app, BrowserWindow, ipcMain } from 'electron'

// ✅ 가능 — default export 사용
import electron from 'electron'
const { app, BrowserWindow, ipcMain } = electron
```

단, default import 방식도 Electron의 ESM 로더 등록 상태에 따라 불안정할 수 있음.

---

### 4차: `createRequire` 사용

**파일**: `electron/main.js` (ESM)

```js
import { createRequire } from 'module'
const require = createRequire(import.meta.url)
const { app, BrowserWindow, ipcMain } = require('electron')
```

```
TypeError: Cannot read properties of undefined (reading 'handle')
```

**원인**: `createRequire`로 생성된 `require`는 Node.js 표준 CJS 해석기를 사용. Electron이 내부적으로 패치한 `Module._resolveFilename`을 거치지 않고 npm 패키지(`node_modules/electron/index.js`)를 직접 로드하여 경로 문자열을 반환.

---

### 5차: 포트 충돌로 백엔드 미기동

```
ERROR: [Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
```

**원인**: 이전 실행의 백엔드 프로세스(uvicorn)가 종료되지 않고 포트 8000을 점유.

---

## 최종 해결

### 설정

| 항목 | 값 |
|------|------|
| `package.json` → `"main"` | `"electron/main.cjs"` |
| `package.json` → `"type"` | `"module"` (Vite용, 유지) |
| 메인 프로세스 파일 | `electron/main.cjs` (CJS) |
| Preload 스크립트 | `electron/preload.cjs` (CJS) |

### 동작 원리

```
Electron 바이너리 실행
  ↓
package.json의 "main": "electron/main.cjs" 읽음
  ↓
.cjs 확장자 → CJS 로더로 강제 로드
  ↓
Electron이 패치한 Module._resolveFilename 적용
  ↓
require('electron') → Electron 내부 API 객체 반환 (npm stub 아님)
  ↓
app, BrowserWindow, ipcMain 등 정상 사용 가능
```

### ESM vs CJS 역할 분리

```
frontend/
  ├── package.json          ← "type": "module" (Vite/React용)
  ├── src/                  ← ESM (.js/.jsx) — Vite가 처리
  ├── vite.config.js        ← ESM
  └── electron/
      ├── main.cjs          ← CJS — Electron 메인 프로세스
      └── preload.cjs       ← CJS — Electron preload 스크립트
```

- `src/` 내 React 코드: `"type": "module"`에 의해 ESM으로 동작 → Vite가 번들링
- `electron/` 내 파일: `.cjs` 확장자로 CJS 강제 → Electron의 `require('electron')` 패치 정상 동작

---

## 재발 방지 체크리스트

1. **Electron 메인/preload 파일은 반드시 `.cjs` 확장자 사용**
   - `"type": "module"` 환경에서 `.js`는 ESM으로 취급되어 `require('electron')`이 작동하지 않음
   - ESM `import from 'electron'`은 named export를 지원하지 않아 불안정

2. **`createRequire`로 `require('electron')` 호출 금지**
   - Electron의 내부 모듈 패치를 우회하여 npm stub(경로 문자열)을 반환

3. **Preload 스크립트도 `.cjs` 사용**
   - Electron sandbox 환경에서 ESM preload(`.mjs`)는 `contextBridge` 등록 실패
   - `window.electronAPI`가 undefined가 되어 IPC 통신 불가

4. **실행 전 포트 확인**
   ```bash
   lsof -ti:5173 -ti:8000 | xargs kill -9  # 잔여 프로세스 정리
   ```

5. **`package.json`의 `"main"` 필드가 `.cjs` 파일을 가리키는지 확인**
   ```json
   {
     "type": "module",
     "main": "electron/main.cjs"
   }
   ```

---

## 진단 방법

`main.cjs` 상단에 다음 코드를 추가하여 `require('electron')`의 반환값을 확인:

```js
const electronModule = require('electron')
console.log('type:', typeof electronModule)
// 정상: "object" + API 키 목록 출력
// 비정상: "string" (npm 패키지의 바이너리 경로)
console.log('keys:', typeof electronModule === 'object'
  ? Object.keys(electronModule)
  : electronModule)
```

정상 출력 예시:
```
type: object
keys: [ 'app', 'BrowserWindow', 'ipcMain', 'dialog', 'safeStorage', ... ]
```

비정상 출력 예시:
```
type: string
keys: /path/to/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron
```
