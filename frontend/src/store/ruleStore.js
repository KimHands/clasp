import { create } from 'zustand'

function buildTree(flatRules) {
  const map = {}
  const tree = []
  for (const r of flatRules) {
    map[r.id] = { ...r, children: [] }
  }
  for (const r of flatRules) {
    const node = map[r.id]
    if (r.parent_id && map[r.parent_id]) {
      map[r.parent_id].children.push(node)
    } else {
      tree.push(node)
    }
  }
  return tree
}

function flattenTree(tree, parentId = null) {
  const result = []
  for (const node of tree) {
    result.push({ ...node, parent_id: parentId, children: undefined })
    if (node.children?.length) {
      result.push(...flattenTree(node.children, node.id))
    }
  }
  return result
}

const useRuleStore = create((set, get) => ({
  rules: [],
  tree: [],

  setRules: (rules) => set({ rules, tree: buildTree(rules) }),

  addRule: (rule) =>
    set((state) => {
      const rules = [...state.rules, rule]
      return { rules, tree: buildTree(rules) }
    }),

  updateRuleInStore: (updatedRule) =>
    set((state) => {
      const rules = state.rules.map((r) => (r.id === updatedRule.id ? updatedRule : r))
      return { rules, tree: buildTree(rules) }
    }),

  removeRule: (ruleId) =>
    set((state) => {
      const deleted = state.rules.find((r) => r.id === ruleId)
      const rules = state.rules
        .filter((r) => r.id !== ruleId)
        .map((r) => (r.parent_id === ruleId ? { ...r, parent_id: deleted?.parent_id ?? null } : r))
      return { rules, tree: buildTree(rules) }
    }),

  setTree: (tree) => {
    const flat = flattenTree(tree)
    set({ tree, rules: flat })
  },

  reorderRules: (rules) => set({ rules, tree: buildTree(rules) }),

  buildTree,
  flattenTree,
}))

export default useRuleStore
