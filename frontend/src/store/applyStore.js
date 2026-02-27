import { create } from 'zustand'

const useApplyStore = create((set) => ({
  preview: null,
  lastActionLogId: null,
  applyResult: null,
  undoResult: null,
  actionHistory: [],

  setPreview: (preview) => set({ preview }),
  setLastActionLogId: (id) => set({ lastActionLogId: id }),
  setApplyResult: (result) => set({ applyResult: result }),
  setUndoResult: (result) => set({ undoResult: result }),
  setActionHistory: (history) => set({ actionHistory: history }),

  markHistoryUndone: (actionLogId) =>
    set((state) => ({
      actionHistory: state.actionHistory.map((h) =>
        h.action_log_id === actionLogId ? { ...h, is_undone: true } : h
      ),
    })),

  reset: () => set({
    preview: null,
    lastActionLogId: null,
    applyResult: null,
    undoResult: null,
  }),
}))

export default useApplyStore
