const BASE_URL = 'http://localhost:8000'

async function request(method, path, body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) {
    options.body = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, options)
  } catch (networkErr) {
    // 백엔드 미기동 또는 네트워크 단절 시 명확한 오류 메시지
    const err = new Error('백엔드 서버에 연결할 수 없습니다. 앱을 재시작해 주세요.')
    err.code = 'NETWORK_ERROR'
    throw err
  }

  let json
  try {
    json = await res.json()
  } catch {
    const err = new Error(`서버 응답 파싱 실패 (HTTP ${res.status})`)
    err.code = 'PARSE_ERROR'
    throw err
  }

  // FastAPI HTTPException은 { detail: { success, error, ... } } 형태로 응답
  const payload = json.detail ?? json

  if (!payload.success) {
    const err = new Error(payload.error?.message || '요청 실패')
    err.code = payload.error?.code
    throw err
  }

  return payload.data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
  delete: (path) => request('DELETE', path),
}

export { BASE_URL }
