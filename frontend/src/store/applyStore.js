import { create } from 'zustand'

const useApplyStore = create((set) => ({
  preview: null,
  lastActionLogId: null,
  applyResult: null,
  undoResult: null,

  setPreview: (preview) => set({ preview }),
  setLastActionLogId: (id) => set({ lastActionLogId: id }),
  setApplyResult: (result) => set({ applyResult: result }),
  setUndoResult: (result) => set({ undoResult: result }),

  reset: () => set({
    preview: null,
    applyResult: null,
    undoResult: null,
  }),
}))

export default useApplyStore
