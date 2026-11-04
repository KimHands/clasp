import { api } from './client'

export async function getApplyPreview(scanId, folderPath) {
  const query = `scan_id=${encodeURIComponent(scanId)}&folder_path=${encodeURIComponent(folderPath)}`
  return api.get(`/apply/preview?${query}`)
}

export async function applyOrganize({ scanId, conflictResolution, folderPath }) {
  return api.post('/apply', {
    scan_id: scanId,
    conflict_resolution: conflictResolution,
    folder_path: folderPath,
  })
}

export async function undoApply({ actionLogId }) {
  return api.post('/undo', { action_log_id: actionLogId })
}

export async function getActionHistory(folderPath) {
  return api.get(`/apply/history?folder_path=${encodeURIComponent(folderPath)}`)
}
