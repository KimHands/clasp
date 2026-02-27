import { create } from 'zustand'
import {
  getExtensions, createExtension, deleteExtension,
  getCategories, createCategory, deleteCategory,
} from '@/api/settings'

const useExtensionStore = create((set, get) => ({
  extensions: [],
  categories: [],
  customCategories: [],
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

  fetchCategories: async () => {
    try {
      const data = await getCategories()
      set({ customCategories: data.categories })
    } catch (e) {
      console.error('카테고리 목록 로드 실패:', e)
    }
  },

  addCategory: async ({ name, keywords }) => {
    const newCat = await createCategory({ name, keywords })
    set((state) => ({
      customCategories: [...state.customCategories, newCat],
    }))
    return newCat
  },

  removeCategory: async (catId) => {
    await deleteCategory(catId)
    set((state) => ({
      customCategories: state.customCategories.filter((c) => c.id !== catId),
    }))
  },
}))

export default useExtensionStore
