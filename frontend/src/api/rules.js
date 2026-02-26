import { api } from './client'

export async function getRules() {
  return api.get('/rules')
}

export async function createRule({ priority, type, value, folderName }) {
  return api.post('/rules', { priority, type, value, folder_name: folderName })
}

export async function updateRule(ruleId, { priority, folderName }) {
  return api.patch(`/rules/${ruleId}`, { priority, folder_name: folderName })
}

export async function deleteRule(ruleId) {
  return api.delete(`/rules/${ruleId}`)
}
