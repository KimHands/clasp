import { create } from 'zustand'

const STORAGE_KEY = 'clasp_theme'

function getSystemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function getInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  return 'system'
}

function applyTheme(mode) {
  const resolved = mode === 'system' ? getSystemTheme() : mode
  document.documentElement.classList.toggle('dark', resolved === 'dark')
  return resolved
}

const useThemeStore = create((set, get) => {
  const initial = getInitialTheme()
  const resolved = applyTheme(initial)

  // 시스템 테마 변경 감지
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (get().mode === 'system') {
      const newResolved = applyTheme('system')
      set({ resolvedTheme: newResolved })
    }
  })

  return {
    mode: initial,
    resolvedTheme: resolved,

    setTheme: (mode) => {
      localStorage.setItem(STORAGE_KEY, mode)
      const resolved = applyTheme(mode)
      set({ mode, resolvedTheme: resolved })
    },

    toggleTheme: () => {
      const current = get().resolvedTheme
      const next = current === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, next)
      const resolved = applyTheme(next)
      set({ mode: next, resolvedTheme: resolved })
    },
  }
})

export default useThemeStore
