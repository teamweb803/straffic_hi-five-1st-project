<script setup>
const steps = [
  { title: '현장 좌표 측정', desc: '시연 차로 또는 실제 지점의 과금 구간 네 꼭지점 GPS 좌표를 확보합니다.' },
  { title: '단말/카메라 연결', desc: 'Pico 2 W GPS 단말과 OCR Edge 장비가 같은 지점 ID로 이벤트를 보냅니다.' },
  { title: '관리자 매핑', desc: '마스터 관리자에서 회원 계정이 접근할 관제 대시보드를 지정합니다.' },
  { title: '시범 운영', desc: 'GPS 로그와 번호판 이벤트가 함께 들어올 때만 과금 이력이 생성되는지 확인합니다.' }
]
</script>

<template>
  <section class="guide-hero">
    <div class="max-w-7xl mx-auto px-6">
      <p class="eyebrow">ADOPTION GUIDE</p>
      <h1>시연에서 운영까지, 필요한 순서만 남겼습니다.</h1>
    </div>
  </section>
  <section class="guide-steps">
    <div class="max-w-7xl mx-auto px-6">
      <article v-for="(step, index) in steps" :key="step.title">
        <span>{{ String(index + 1).padStart(2, '0') }}</span>
        <div>
          <h2>{{ step.title }}</h2>
          <p>{{ step.desc }}</p>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.guide-hero{padding:100px 0 80px;background:white}
.eyebrow{font-family:monospace;font-size:12px;letter-spacing:.28em;color:#1b3be8;font-weight:800}
h1{max-width:780px;margin-top:14px;color:#080c18;font-size:54px;line-height:1.08;font-weight:900}
.guide-steps{padding:80px 0;background:#e8effe}
.guide-steps>div{display:grid;gap:18px}
article{display:grid;grid-template-columns:110px 1fr;align-items:center;padding:28px;border-radius:18px;background:white;border:1px solid rgba(11,24,64,.12)}
article span{font-family:monospace;color:#1b3be8;font-size:34px;font-weight:900}
article h2{color:#080c18;font-size:24px;font-weight:900}article p{margin-top:8px;color:rgba(11,24,64,.7);line-height:1.7}
</style>
