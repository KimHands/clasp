import { api, getBackendConfig } from './client'

export async function startScan(folderPath) {
  return api.post('/scan/start', { folder_path: folderPath })
}

async function readEvents(response, onEvent) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop()
    for (const line of lines) {
      if (line.startsWith('data:')) onEvent(JSON.parse(line.slice(5)))
    }
  }
}

/**
 * 스캔 진행 상황 수신. 토큰을 URL에 남기지 않도록 EventSource 대신 fetch 스트림을 읽는다
 * @param {string} scanId
 * @param {function} onMessage - { stage, message, total, completed, current_file }
 * @param {function} onComplete
 * @param {function} onError
 * @returns {{ close: function }} - 연결 해제 시 .close() 호출
 */
export function connectProgress(scanId, onMessage, onComplete, onError) {
  const controller = new AbortController()
  let finished = false

  const handleEvent = (data) => {
    if (data.stage === -1) {
      finished = true
      controller.abort()
      onError?.(new Error(data.message || '스캔 중 오류 발생'))
      return
    }
    onMessage(data)
    if (data.stage === 7) {
      finished = true
      controller.abort()
      onComplete?.()
    }
  }

  const run = async () => {
    const { baseUrl, token } = await getBackendConfig()
    const response = await fetch(
      `${baseUrl}/scan/progress?scan_id=${encodeURIComponent(scanId)}`,
      { headers: { 'X-Clasp-Token': token }, signal: controller.signal }
    )
    if (!response.ok) throw new Error(`스캔 진행 조회 실패 (HTTP ${response.status})`)
    await readEvents(response, handleEvent)
    if (!finished) throw new Error('스캔 연결이 끊어졌습니다')
  }

  run().catch((e) => {
    if (!finished && e.name !== 'AbortError') onError?.(e)
  })

  return { close: () => { finished = true; controller.abort() } }
}
