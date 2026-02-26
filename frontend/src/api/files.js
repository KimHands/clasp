import { api } from './client'

export async function getFiles({ scanId, category, tag, minConfidence, unclassified, search, page = 1, pageSize = 50 }) {
  const params = new URLSearchParams({ scan_id: scanId, page, page_size: pageSize })
  if (category) params.set('category', category)
  if (tag) params.set('tag', tag)
  if (minConfidence != null) params.set('min_confidence', minConfidence)
  if (unclassified) params.set('unclassified', 'true')
  if (search) params.set('search', search)
  return api.get(`/files?${params}`)
}

export async function updateFile(fileId, { category, tag }) {
  return api.patch(`/files/${fileId}`, { category, tag })
}

export async function getSimilarFiles(fileId) {
  return api.get(`/files/${fileId}/similar`)
}
