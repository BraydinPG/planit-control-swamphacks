import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Auth0 only accepts the registered callback URLs (http://localhost:5173), so fail
    // instead of silently moving to another port. See auth/SETUP.md.
    port: 5173,
    strictPort: true,
    // Generated browser profiles contain locked Windows files; never watch test output.
    watch: { ignored: ['**/.shell-check/**'] },
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
