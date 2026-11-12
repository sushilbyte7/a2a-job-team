import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The UI talks to the Coordinator (:8000) through /api so the browser never
// hits a cross-origin URL directly — no CORS setup needed for the demo.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
