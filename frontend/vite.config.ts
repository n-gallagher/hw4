import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // FastAPI backend (backend/main.py) runs on port 8000; override with API_PORT in frontend/.env.local.
  const env = loadEnv(mode, import.meta.dirname, '')
  const api = `http://127.0.0.1:${env.API_PORT || 8000}`

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': api,
        '/images': api,
      },
    },
  }
})
