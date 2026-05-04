import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// HiFive 프론트엔드 빌드 설정
// 백엔드(Spring Boot) 는 8080, FastAPI 엣지는 8000 으로 가정.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8585',
        changeOrigin: true
      }
    }
  }
})
