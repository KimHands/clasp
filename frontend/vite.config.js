import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Electron 환경에서 로컬 파일 로드 지원
  base: './',
  server: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
  },
})
