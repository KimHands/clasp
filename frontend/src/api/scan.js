import { api, BASE_URL } from './client'

export async function startScan(folderPath) {
  return api.post('/scan/start', { folder_path: folderPath })
}

/**
 * SSE로 스캔 진행 상황 수신
 * @param {string} scanId
 * @param {function} onMessage - { stage, message, total, completed, currentFile }
 * @param {function} onComplete
 * @param {function} onError
 * @returns {EventSource} - 연결 해제 시 .close() 호출
 */
export function connectProgress(scanId, onMessage, onComplete, onError) {
  const url = `${BASE_URL}/scan/progress?scan_id=${encodeURIComponent(scanId)}`
  const es = new EventSource(url)

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.stage === -1) {
        es.close()
        onError?.(new Error(data.message || '스캔 중 오류 발생'))
        return
      }
      onMessage(data)
      if (data.stage === 7) {
        es.close()
        onComplete?.()
      }
    } catch (e) {
      console.error('SSE 파싱 오류', e)
    }
  }

  es.onerror = (e) => {
    es.close()
    onError?.(e)
  }

  return es
}
