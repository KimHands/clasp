import { api } from './client'

export async function getLocalLlm() {
  return api.get('/settings/local-llm')
}

export async function saveLocalLlm({ enabled, baseUrl, model }) {
  return api.post('/settings/local-llm', { enabled, base_url: baseUrl, model })
}

export async function testLocalLlm(baseUrl) {
  return api.post('/settings/local-llm/test', { base_url: baseUrl })
}

export async function getSensitiveKeywords() {
  return api.get('/settings/sensitive-keywords')
}

export async function createSensitiveKeyword(keyword) {
  return api.post('/settings/sensitive-keywords', { keyword })
}

export async function deleteSensitiveKeyword(keywordId) {
  return api.delete(`/settings/sensitive-keywords/${keywordId}`)
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
