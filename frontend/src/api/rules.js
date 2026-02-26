import { api } from './client'

export async function getRules() {
  return api.get('/rules')
}

export async function createRule({ priority, type, value, folderName, parentId = null }) {
  return api.post('/rules', {
    priority,
    type,
    value,
    folder_name: folderName,
    parent_id: parentId,
  })
}

export async function updateRule(ruleId, { priority, folderName, parentId } = {}) {
  const body = {}
  if (priority !== undefined) body.priority = priority
  if (folderName !== undefined) body.folder_name = folderName
  // parentId: undefined = 변경 안 함(-1), null = 루트로, 숫자 = 해당 부모
  if (parentId !== undefined) body.parent_id = parentId === null ? null : parentId
  else body.parent_id = -1
  return api.patch(`/rules/${ruleId}`, body)
}

export async function deleteRule(ruleId) {
  return api.delete(`/rules/${ruleId}`)
}
