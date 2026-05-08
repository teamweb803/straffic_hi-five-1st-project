import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// HiFive 프론트엔드 빌드 설정
// Vue는 Spring Boot REST API만 호출한다. Python Ingress는 브라우저에서 직접 호출하지 않는다.
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
