import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    allowedHosts: ['argument-debugger.loca.lt'],
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  preview: { port: 5173 }
})
