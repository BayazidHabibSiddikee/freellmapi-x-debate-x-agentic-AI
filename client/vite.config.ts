import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '')
  // Proxy to freellmapi on :3001 by default; override with SWORD_BACKEND_PORT env var.
  const serverPort = Number(process.env.SWORD_BACKEND_PORT || env.PORT || 3001)

  return {
    plugins: [react(), tailwindcss()],
    base: process.env.VITE_BASE ?? '/',
    envDir: path.resolve(__dirname, '..'),
    define: {
      __SERVER_PORT__: JSON.stringify(String(serverPort)),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: Number(process.env.SWORD_WEB_PORT ?? 3002),
      strictPort: true,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${serverPort}`,
          changeOrigin: true,
        },
        '/v1': {
          target: `http://127.0.0.1:${serverPort}`,
          changeOrigin: true,
        },
        '/health': {
          target: `http://127.0.0.1:${serverPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
