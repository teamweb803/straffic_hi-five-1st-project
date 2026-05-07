<script setup>
const flow = [
  { step: '01', title: '차량 감지', text: '차로 카메라가 차량과 번호판 ROI를 검출합니다.' },
  { step: '02', title: '번호판 인식', text: 'OCR 결과와 신뢰도를 생성하고 저신뢰 이벤트는 검수 대상으로 분리합니다.' },
  { step: '03', title: 'GPS 구간 매칭', text: '단말의 최신 GPS가 등록된 과금 구간 안에 있는지 판정합니다.' },
  { step: '04', title: '정산 이벤트 생성', text: '번호판과 GPS가 모두 통과 조건을 만족할 때만 결제 이력을 생성합니다.' }
]

const modules = ['실시간 통행 이벤트', 'OCR 검수 큐', 'GPS Telemetry 로그', '요금/정산 요약', '지점별 관제 대시보드']
</script>

<template>
  <section class="solution-hero">
    <div class="max-w-7xl mx-auto px-6">
      <div>
        <p class="eyebrow">SOLUTION</p>
        <h1>번호판과 GPS가 함께 증명하는 통행 정산.</h1>
      </div>
      <p>
        카메라 기반 OCR만으로 끝내지 않고 GPS 구간 통과 여부를 결합해 시연 환경에서도 명확한 결제 기준을 만듭니다.
      </p>
    </div>
  </section>

  <section class="flow-section">
    <div class="max-w-7xl mx-auto px-6">
      <div class="flow-board">
        <article v-for="item in flow" :key="item.step">
          <span>{{ item.step }}</span>
          <h2>{{ item.title }}</h2>
          <p>{{ item.text }}</p>
        </article>
      </div>
    </div>
  </section>

  <section class="module-section">
    <div class="max-w-7xl mx-auto px-6">
      <p class="eyebrow">OPERATION MODULES</p>
      <h2>운영자가 실제로 보는 기능</h2>
      <div>
        <button v-for="item in modules" :key="item">{{ item }}</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.solution-hero{padding:96px 0;background:linear-gradient(135deg,#f8fbff,#e8effe)}
.solution-hero>div{display:grid;grid-template-columns:1.1fr .9fr;gap:60px;align-items:end}
.eyebrow{font-family:monospace;font-size:12px;letter-spacing:.28em;color:#1b3be8;font-weight:800}
h1{margin-top:14px;color:#080c18;font-size:54px;line-height:1.05;font-weight:900}
.solution-hero p{color:rgba(11,24,64,.7);line-height:1.8}
.flow-section{padding:72px 0;background:#07101f}
.flow-board{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.flow-board article{padding:26px;border:1px solid rgba(56,190,245,.24);background:rgba(255,255,255,.04);color:white}
.flow-board span{color:#38bef5;font-family:monospace;font-weight:900}.flow-board h2{margin-top:26px;font-size:22px;font-weight:900}.flow-board p{color:rgba(255,255,255,.68);line-height:1.7}
.module-section{padding:90px 0;background:white}.module-section h2{margin-top:8px;color:#080c18;font-size:42px;font-weight:900}
.module-section div div{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}
.module-section button{padding:14px 18px;border:1px solid rgba(11,24,64,.12);border-radius:999px;background:#f7f9ff;color:#0b1840;font-weight:800}
</style>
