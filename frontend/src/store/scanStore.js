import { create } from 'zustand'

const useScanStore = create((set, get) => ({
  // 선택된 폴더 경로
  selectedFolder: null,
  // 현재 스캔 ID
  scanId: null,
  // 스캔 상태: idle | scanning | completed | error
  scanStatus: 'idle',
  // SSE 진행 상황
  progress: {
    stage: 0,
    message: '',
    total: 0,
    completed: 0,
    currentFile: '',
  },
  // 최근 스캔 폴더 목록 (최대 5개)
  recentFolders: [],

  setSelectedFolder: (path) => {
    const recent = get().recentFolders
    const updated = [path, ...recent.filter((p) => p !== path)].slice(0, 5)
    set({ selectedFolder: path, recentFolders: updated })
  },

  setScanId: (id) => set({ scanId: id }),

  setScanStatus: (status) => set({ scanStatus: status }),

  setProgress: (progress) => set({ progress }),

  resetScan: () =>
    set({
      scanId: null,
      scanStatus: 'idle',
      progress: { stage: 0, message: '', total: 0, completed: 0, currentFile: '' },
    }),
}))

export default useScanStore
