import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Vite's dev server needs inline scripts, so the policy applies to production builds only
const PRODUCTION_CSP = [
  "default-src 'self'",
  "connect-src http://127.0.0.1:*",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
].join('; ')

const contentSecurityPolicy = {
  name: 'clasp-content-security-policy',
  apply: 'build',
  transformIndexHtml: () => [{
    tag: 'meta',
    attrs: { 'http-equiv': 'Content-Security-Policy', content: PRODUCTION_CSP },
    injectTo: 'head-prepend',
  }],
}

export default defineConfig({
  plugins: [react(), tailwindcss(), contentSecurityPolicy],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Electron 환경에서 로컬 파일 로드 지원
  base: './',
  server: {
    port: Number(process.env.CLASP_VITE_PORT || 5173),
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['@radix-ui/react-slot', 'lucide-react'],
        },
      },
    },
  },
})
