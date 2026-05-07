<script setup>
const stacks = [
  { layer: 'Edge AI', items: ['YOLOv8', 'OpenCV', 'OCR', 'Jetson Nano'] },
  { layer: 'Telemetry', items: ['Pico 2 W', 'NEO-7M GPS', 'HTTP POST', 'GPS Geofence'] },
  { layer: 'Backend', items: ['Spring Boot', 'JPA', 'PostgreSQL', 'BCrypt'] },
  { layer: 'Frontend', items: ['Vue 3', 'Pinia', 'Vue Router', 'Vite'] }
]
</script>

<template>
  <section class="tech-page">
    <div class="max-w-7xl mx-auto px-6">
      <p class="eyebrow">TECHNOLOGY</p>
      <h1>Edge에서 판단하고 Spring에서 확정합니다.</h1>
      <div class="architecture">
        <article v-for="stack in stacks" :key="stack.layer">
          <h2>{{ stack.layer }}</h2>
          <ul>
            <li v-for="item in stack.items" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
    </div>
  </section>

  <section class="metric-strip">
    <div class="max-w-7xl mx-auto px-6">
      <div><strong>실시간</strong><span>GPS/OCR 이벤트 수집</span></div>
      <div><strong>BCrypt</strong><span>계정 비밀번호 해시 보호</span></div>
      <div><strong>Geofence</strong><span>4개 꼭지점 과금 구간 판정</span></div>
    </div>
  </section>
</template>

<style scoped>
.tech-page{padding:104px 0;background:#050914;color:white}
.eyebrow{font-family:monospace;font-size:12px;letter-spacing:.28em;color:#38bef5;font-weight:800}
h1{max-width:850px;margin-top:14px;font-size:56px;line-height:1.05;font-weight:900}
.architecture{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:54px}
.architecture article{padding:24px;border:1px solid rgba(56,190,245,.22);background:linear-gradient(180deg,rgba(56,190,245,.12),rgba(255,255,255,.03))}
.architecture h2{font-size:20px;font-weight:900}.architecture ul{margin:20px 0 0;padding:0;list-style:none;display:grid;gap:10px}
.architecture li{padding:9px 10px;border-radius:8px;background:rgba(255,255,255,.07);color:rgba(255,255,255,.78);font-size:13px}
.metric-strip{padding:42px 0;background:#38bef5;color:#06111f}.metric-strip>div{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.metric-strip strong{display:block;font-size:30px;font-weight:900}.metric-strip span{font-weight:700}
</style>
