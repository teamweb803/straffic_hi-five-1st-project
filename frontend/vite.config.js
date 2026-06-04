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
    host: '0.0.0.0',
    port: 5173,
    // 시연 / 개발 중 F5에 즉시 새 CSS·HTML이 반영되도록 dev 응답을 캐시하지 않음
    headers: {
      'Cache-Control': 'no-store'
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8585',
        changeOrigin: true
      },
      '/video': {
        target: process.env.VITE_VIDEO_TARGET || 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
