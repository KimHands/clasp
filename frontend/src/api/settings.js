import { api } from './client'

export async function getExtensions() {
  return api.get('/settings/extensions')
}

export async function createExtension({ extension, category }) {
  return api.post('/settings/extensions', { extension, category })
}

export async function deleteExtension(extId) {
  return api.delete(`/settings/extensions/${extId}`)
}
