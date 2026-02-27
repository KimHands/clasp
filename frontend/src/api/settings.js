import { api } from './client'

export async function getLlmStatus() {
  return api.get('/settings/llm-status')
}

export async function setOpenaiApiKey(apiKey) {
  return api.post('/settings/api-key', { api_key: apiKey })
}

export async function setGeminiApiKey(apiKey) {
  return api.post('/settings/gemini-api-key', { api_key: apiKey })
}

export async function getExtensions() {
  return api.get('/settings/extensions')
}

export async function createExtension({ extension, category }) {
  return api.post('/settings/extensions', { extension, category })
}

export async function deleteExtension(extId) {
  return api.delete(`/settings/extensions/${extId}`)
}

export async function getCategories() {
  return api.get('/settings/categories')
}

export async function createCategory({ name, keywords }) {
  return api.post('/settings/categories', { name, keywords })
}

export async function deleteCategory(catId) {
  return api.delete(`/settings/categories/${catId}`)
}
