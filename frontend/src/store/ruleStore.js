import { create } from 'zustand'

const useRuleStore = create((set) => ({
  rules: [],

  setRules: (rules) => set({ rules }),

  addRule: (rule) => set((state) => ({ rules: [...state.rules, rule] })),

  updateRule: (updatedRule) =>
    set((state) => ({
      rules: state.rules.map((r) => (r.id === updatedRule.id ? updatedRule : r)),
    })),

  removeRule: (ruleId) =>
    set((state) => ({
      rules: state.rules.filter((r) => r.id !== ruleId),
    })),

  reorderRules: (rules) => set({ rules }),
}))

export default useRuleStore
