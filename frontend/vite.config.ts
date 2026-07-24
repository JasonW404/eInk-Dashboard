import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const appVersion = readFileSync(resolve(__dirname, '../VERSION'), 'utf-8').trim()

export default defineConfig({
  base: './',
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    rolldownOptions: {
      input: {
        web: 'index.html',
        eink: 'eink.html',
        text: 'text.html',
      },
    },
  },
})
