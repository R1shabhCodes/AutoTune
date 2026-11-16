import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', // Use root pathing so SPA sub-routes (/console, /console/overview) resolve static assets cleanly
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
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/overview': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/experiments': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/integrations': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/trials': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/promotion': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/holdout_score': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/report': {
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
