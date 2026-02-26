import { create } from 'zustand'

const useFileStore = create((set) => ({
  files: [],
  total: 0,
  page: 1,
  pageSize: 50,
  filters: {
    category: '',
    tag: '',
    minConfidence: null,
    unclassified: false,
    search: '',
  },
  selectedFile: null,
  unclassifiedCount: 0,

  setFiles: (files, total) => set({ files, total }),

  setPage: (page) => set({ page }),

  setFilters: (filters) => set((state) => ({ filters: { ...state.filters, ...filters } })),

  setSelectedFile: (file) => set({ selectedFile: file }),

  updateFile: (updatedFile) =>
    set((state) => ({
      files: state.files.map((f) => (f.id === updatedFile.id ? updatedFile : f)),
      selectedFile: state.selectedFile?.id === updatedFile.id ? updatedFile : state.selectedFile,
    })),

  setUnclassifiedCount: (count) => set({ unclassifiedCount: count }),

  reset: () =>
    set({
      files: [],
      total: 0,
      page: 1,
      selectedFile: null,
      unclassifiedCount: 0,
    }),
}))

export default useFileStore
