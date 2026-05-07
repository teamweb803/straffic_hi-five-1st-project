<script setup>
const values = [
  { title: '정차 없는 흐름', desc: '차량이 멈추지 않아도 통행 이벤트를 식별하고 정산 가능한 데이터로 전환합니다.' },
  { title: '현장 우선 설계', desc: 'Jetson, GPS, OCR, 관제 화면이 실제 차로 운영 조건을 기준으로 맞물리도록 설계합니다.' },
  { title: '검수 가능한 자동화', desc: 'AI 판정 결과를 그대로 끝내지 않고 저신뢰 이벤트를 운영자가 확인할 수 있게 분리합니다.' }
]

const milestones = [
  { year: '2024', label: 'R&D', text: '번호판 OCR, GPS 구간 판정, 통행 이벤트 모델 검증' },
  { year: '2025', label: 'PoC', text: 'RC카/모형 차로 기반 실시간 통행 및 과금 시연 구축' },
  { year: '2026', label: 'Scale', text: '회원사/지점별 관제와 마스터 관리자 운영 체계 확장' }
]
</script>

<template>
  <section class="company-hero">
    <div class="max-w-7xl mx-auto px-6">
      <p class="eyebrow">ABOUT HI-FIVE</p>
      <h1>요금소의 멈춤을 데이터의 흐름으로 바꿉니다.</h1>
      <p>
        HI-FIVE는 번호판 인식, GPS 구간 판정, 실시간 관제, 정산 검수를 하나의 운영 흐름으로 묶는
        스마트 하이패스 관제 플랫폼입니다.
      </p>
    </div>
  </section>

  <section class="company-values">
    <div class="max-w-7xl mx-auto px-6 grid lg:grid-cols-3 gap-5">
      <article v-for="item in values" :key="item.title">
        <span></span>
        <h2>{{ item.title }}</h2>
        <p>{{ item.desc }}</p>
      </article>
    </div>
  </section>

  <section class="company-story">
    <div class="max-w-7xl mx-auto px-6">
      <p class="eyebrow">ROADMAP</p>
      <h2>프로젝트가 향하는 방향</h2>
      <ol>
        <li v-for="item in milestones" :key="item.year">
          <strong>{{ item.year }}</strong>
          <div>
            <span>{{ item.label }}</span>
            <p>{{ item.text }}</p>
          </div>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.company-hero{padding:110px 0;background:#07101f;color:white}
.eyebrow{font-family:monospace;font-size:12px;letter-spacing:.28em;color:#38bef5;font-weight:800}
.company-hero h1{max-width:840px;margin:18px 0 0;font-size:58px;line-height:1.05;font-weight:900;letter-spacing:0}
.company-hero p{max-width:690px;margin-top:24px;color:rgba(255,255,255,.72);line-height:1.8}
.company-values{padding:72px 0;background:#e8effe}
.company-values article{min-height:230px;padding:28px;border:1px solid rgba(11,24,64,.12);background:white}
.company-values span{display:block;width:42px;height:4px;background:#1b3be8}
.company-values h2{margin-top:28px;color:#080c18;font-size:24px;font-weight:900}
.company-values p{margin-top:12px;color:rgba(11,24,64,.72);line-height:1.7}
.company-story{padding:90px 0;background:white}
.company-story h2{margin-top:8px;color:#080c18;font-size:42px;font-weight:900}
.company-story ol{display:grid;gap:0;margin:38px 0 0;padding:0;list-style:none;border-top:1px solid rgba(11,24,64,.12)}
.company-story li{display:grid;grid-template-columns:150px 1fr;gap:28px;padding:26px 0;border-bottom:1px solid rgba(11,24,64,.12)}
.company-story strong{color:#1b3be8;font-size:32px}
.company-story span{font-weight:900;color:#080c18}.company-story p{margin:.35rem 0 0;color:rgba(11,24,64,.68)}
</style>
