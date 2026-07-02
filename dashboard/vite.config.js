import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Use relative pathing so it resolves nicely when served by FastAPI
  server: {
    port: 5173,
    proxy: {
      '/run': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/iterations': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/best': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})
