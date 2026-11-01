import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // Production base: the built app is served by Django under /static/
  // (whitenoise), keeping everything on one origin.
  base: '/static/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
