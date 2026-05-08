<script setup>
const principles = [
  { num: '01', title: 'FREE FLOW', desc: '물리적 게이트 없이 정확하게 통행료를 정산해, 도로의 흐름을 멈추지 않게 합니다.' },
  { num: '02', title: 'SMART HIGHWAY', desc: '전국 모든 유료 도로를 단일 플랫폼으로 연결하는 차세대 인프라.' },
  { num: '03', title: 'EDGE FIRST', desc: '모든 결정은 가장 가까운 엣지에서. 빠르고 정확하게.' },
  { num: '04', title: 'OPEN STACK', desc: '검증된 오픈소스 위에서. 엣지부터 프론트까지 모두 모던하게.' }
]

const milestones = [
  { year: '2024', title: '창립', desc: '엣지 기반 스마트톨링 R&D 시작' },
  { year: '2025', title: '시범 사업', desc: '도시고속도로 1개 노선에서 PoC 진행' },
  { year: '2026', title: '확장', desc: 'WebTransport 기반 차세대 톨링 시스템 정식 출시' },
  { year: '2027', title: '글로벌', desc: '동남아 4개 도시 게이트리스 톨링 수출' }
]
</script>

<template>
  <div class="company-page">
    <section class="hero">
      <p class="eyebrow">COMPANY · 회사소개</p>
      <h1>WE BUILD<br>THE INVISIBLE<br>TOLL.</h1>
      <p class="lead">
        엣지에서 인식하고 클라우드에서 정산하는 차세대 통행 인프라 — HiFive는
        멈추지 않는 도로를 설계합니다.
      </p>
    </section>

    <section class="stack">
      <div v-for="p in principles" :key="p.num" class="row">
        <span class="num">{{ p.num }}</span>
        <h3>{{ p.title }}</h3>
        <p>{{ p.desc }}</p>
      </div>
    </section>

    <section class="journey">
      <p class="eyebrow">JOURNEY</p>
      <h2>MILESTONES.</h2>
      <ol class="milestones">
        <li v-for="m in milestones" :key="m.year">
          <span class="m-year">{{ m.year }}</span>
          <span class="m-title">{{ m.title }}</span>
          <span class="m-desc">{{ m.desc }}</span>
        </li>
      </ol>
    </section>

    <footer class="foot">
      <span>— HiFive Mobility Lab</span>
      <span>2026</span>
    </footer>
  </div>
</template>

<style scoped>
.company-page {
  --p-deep: #080C18;
  --p-navy: #0B1840;
  --p-blue: #1B3BE8;
  --p-sky: #38BEF5;
  --p-headline: 'Big Shoulders Display', sans-serif;
  --p-mono: 'Fira Mono', monospace;
  background: #0A1024;
  color: #E6ECFF;
  min-height: 100vh;
  padding: 100px 36px 60px;
  display: flex;
  flex-direction: column;
}

.eyebrow {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-sky);
  margin: 0 0 14px;
}

.hero {
  max-width: 980px;
  margin: 0 auto 80px;
  width: 100%;
}
.hero h1 {
  font-family: var(--p-headline);
  font-size: clamp(72px, 11vw, 168px);
  line-height: 0.84;
  margin: 0;
  color: #fff;
  letter-spacing: 0.5px;
}
.hero .lead {
  margin-top: 36px;
  max-width: 580px;
  color: #AEB9D6;
  line-height: 1.85;
  font-size: 17px;
}

.stack {
  max-width: 980px;
  margin: 0 auto;
  width: 100%;
  border-top: 1px solid #26365F;
}
.row {
  display: grid;
  grid-template-columns: 80px 220px 1fr;
  gap: 30px;
  padding: 36px 0;
  border-bottom: 1px solid #26365F;
  align-items: baseline;
  transition: background 200ms ease, padding 200ms ease;
}
.row:hover {
  background: rgba(255, 255, 255, 0.02);
  padding-left: 14px;
}
.num {
  font-family: var(--p-mono);
  font-size: 14px;
  color: var(--p-sky);
  letter-spacing: 1px;
}
.row h3 {
  font-family: var(--p-headline);
  font-size: 32px;
  margin: 0;
  color: #fff;
  letter-spacing: 1px;
}
.row p {
  margin: 0;
  color: #AEB9D6;
  line-height: 1.75;
  font-size: 15px;
}

.journey {
  max-width: 980px;
  margin: 100px auto 0;
  width: 100%;
}
.journey h2 {
  font-family: var(--p-headline);
  font-size: clamp(40px, 5vw, 72px);
  margin: 0 0 36px;
  color: #fff;
}
.milestones {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid #26365F;
  border-bottom: 1px solid #26365F;
}
.milestones li {
  padding: 28px 22px;
  border-right: 1px solid #26365F;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.milestones li:last-child { border-right: none; }
.m-year {
  font-family: var(--p-headline);
  font-size: 44px;
  color: var(--p-blue);
  line-height: 1;
}
.m-title { font-weight: 700; color: #fff; font-size: 15px; }
.m-desc { color: #AEB9D6; font-size: 13px; line-height: 1.6; }

.foot {
  max-width: 980px;
  margin: 80px auto 0;
  width: 100%;
  display: flex;
  justify-content: space-between;
  font-family: var(--p-mono);
  font-size: 11px;
  color: #7E8CB2;
  padding-top: 24px;
  border-top: 1px solid #26365F;
}

@media (max-width: 760px) {
  .row { grid-template-columns: 50px 1fr; }
  .row h3 { grid-column: 2; }
  .row p { grid-column: 2; margin-top: 6px; }
  .milestones { grid-template-columns: repeat(2, 1fr); }
  .milestones li:nth-child(2) { border-right: none; }
}
</style>
