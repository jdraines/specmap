import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'https://localhost:8080',
        secure: false,
      },
      '/healthz': {
        target: 'https://localhost:8080',
        secure: false,
      },
    },
  },
})
