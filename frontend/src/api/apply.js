import { api } from './client'

export async function getApplyPreview(scanId) {
  return api.get(`/apply/preview?scan_id=${encodeURIComponent(scanId)}`)
}

export async function applyOrganize({ scanId, conflictResolution }) {
  return api.post('/apply', { scan_id: scanId, conflict_resolution: conflictResolution })
}

export async function undoApply({ actionLogId }) {
  return api.post('/undo', { action_log_id: actionLogId })
}
