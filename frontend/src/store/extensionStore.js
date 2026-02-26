import { create } from 'zustand'
import { getExtensions, createExtension, deleteExtension } from '@/api/settings'

const useExtensionStore = create((set, get) => ({
  extensions: [],
  categories: [],
  loading: false,

  fetchExtensions: async () => {
    set({ loading: true })
    try {
      const data = await getExtensions()
      set({ extensions: data.extensions, categories: data.categories })
    } catch (e) {
      console.error('확장자 목록 로드 실패:', e)
    } finally {
      set({ loading: false })
    }
  },

  addExtension: async ({ extension, category }) => {
    const newExt = await createExtension({ extension, category })
    set((state) => ({
      extensions: [...state.extensions, { ...newExt, is_default: false }],
    }))
    return newExt
  },

  removeExtension: async (extId) => {
    await deleteExtension(extId)
    set((state) => ({
      extensions: state.extensions.filter((e) => e.id !== extId),
    }))
  },

  getAllExtensionOptions: () => {
    const { extensions } = get()
    const grouped = {}
    for (const ext of extensions) {
      if (!grouped[ext.category]) grouped[ext.category] = []
      grouped[ext.category].push(ext.extension)
    }
    return grouped
  },
}))

export default useExtensionStore
