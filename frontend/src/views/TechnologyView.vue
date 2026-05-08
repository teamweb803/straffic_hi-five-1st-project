<script setup>
const stacks = [
  { layer: 'AI / Vision', items: ['YOLOv8', 'OpenCV', 'EasyOCR', 'PaddleOCR'] },
  { layer: 'Edge / Ingress', items: ['WebTransport', 'aioquic', 'FastAPI', 'Protobuf'] },
  { layer: 'Backend', items: ['Spring Boot 3', 'Spring Security', 'JPA', 'PostgreSQL'] },
  { layer: 'Frontend', items: ['Vue.js 3', 'Pinia', 'Vue Router', 'Tailwind CSS'] },
  { layer: 'Infrastructure', items: ['GPS 연동', '가상 통과선', 'Docker', 'CI/CD'] }
]

const performance = [
  { label: 'Latency P95', metric: '42 ms', desc: 'end-to-end round-trip (edge → backend)' },
  { label: 'Payload', metric: '-70%', desc: 'Protobuf 직렬화 / JSON 대비' },
  { label: 'Accuracy', metric: '97.3%', desc: '번호판 OCR 평균 신뢰도' },
  { label: 'Availability', metric: '99.95%', desc: 'rolling 30d uptime' }
]

const toc = [
  { num: '01', label: 'Overview' },
  { num: '02', label: 'AI / Vision' },
  { num: '03', label: 'Edge / Ingress' },
  { num: '04', label: 'Backend' },
  { num: '05', label: 'Frontend' },
  { num: '06', label: 'Infrastructure' },
  { num: '07', label: 'Performance' }
]
</script>

<template>
  <div class="tech-page">
    <aside class="side">
      <p class="side-eyebrow">SPECIFICATION</p>
      <p class="side-rev">REV · 2026.05</p>
      <ul class="toc">
        <li v-for="t in toc" :key="t.num">
          <span class="toc-num">{{ t.num }}</span>
          <span class="toc-label">{{ t.label }}</span>
        </li>
      </ul>
      <p class="side-foot">DOC ID — HF-STK-001</p>
    </aside>

    <div class="main">
      <p class="eyebrow">TECHNOLOGY · 기술스택</p>
      <h1 class="title">TECHNOLOGY<br>SPECIFICATION.</h1>
      <p class="lead">
        HiFive는 검증된 오픈소스 위에서 동작합니다. 엣지부터 프론트까지 — 모든
        레이어를 모던하게.
      </p>

      <table class="spec-table">
        <tbody>
          <tr v-for="s in stacks" :key="s.layer">
            <th>{{ s.layer }}</th>
            <td>
              <span v-for="i in s.items" :key="i" class="chip">{{ i }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <h2 class="sub">PERFORMANCE</h2>
      <table class="spec-table">
        <tbody>
          <tr v-for="p in performance" :key="p.label">
            <th>{{ p.label }}</th>
            <td>
              <strong>{{ p.metric }}</strong>
              <span class="desc">{{ p.desc }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <p class="sign">— HiFive Mobility Lab / Engineering</p>
    </div>
  </div>
</template>

<style scoped>
.tech-page {
  --p-deep: #080C18;
  --p-navy: #0B1840;
  --p-blue: #1B3BE8;
  --p-sky: #38BEF5;
  --p-cloud: #E8EFFE;
  --p-line: rgba(11, 24, 64, 0.12);
  --p-headline: 'Big Shoulders Display', sans-serif;
  --p-mono: 'Fira Mono', monospace;

  min-height: 100vh;
  background: #fff;
  display: grid;
  grid-template-columns: 280px 1fr;
}

.side {
  background: #0A1024;
  color: #C9D2EA;
  padding: 60px 32px;
  font-family: var(--p-mono);
  font-size: 12px;
  border-right: 1px solid #26365F;
}
.side-eyebrow {
  color: var(--p-sky);
  letter-spacing: 2px;
  margin: 0 0 6px;
}
.side-rev {
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 32px;
}
.toc {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0;
}
.toc li {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px dashed #26365F;
  cursor: default;
  transition: color 160ms ease, padding 160ms ease;
}
.toc li:hover { color: #fff; padding-left: 6px; }
.toc-num { color: var(--p-sky); }
.side-foot {
  margin-top: 40px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 11px;
  letter-spacing: 1px;
}

.main { padding: 60px 60px 80px; }
.eyebrow {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-blue);
  margin: 0 0 14px;
}
.title {
  font-family: var(--p-headline);
  font-size: clamp(48px, 6vw, 88px);
  line-height: 0.92;
  margin: 0 0 24px;
  color: var(--p-deep);
}
.lead {
  max-width: 620px;
  color: rgba(11, 24, 64, 0.72);
  line-height: 1.85;
  margin: 0 0 50px;
}

.sub {
  font-family: var(--p-mono);
  font-size: 12px;
  color: var(--p-sky);
  letter-spacing: 2px;
  margin: 60px 0 0;
  text-transform: uppercase;
}

.spec-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--p-mono);
  font-size: 13px;
  margin-top: 12px;
}
.spec-table tr { border-top: 1px solid var(--p-line); }
.spec-table tr:last-child { border-bottom: 1px solid var(--p-line); }
.spec-table th {
  text-align: left;
  width: 200px;
  padding: 18px 18px 18px 0;
  color: var(--p-sky);
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  font-size: 11px;
  vertical-align: top;
}
.spec-table td {
  padding: 18px 0;
  color: var(--p-navy);
  vertical-align: top;
}
.spec-table td strong {
  font-family: var(--p-headline);
  font-size: 26px;
  color: var(--p-blue);
  margin-right: 12px;
}
.desc { color: rgba(11, 24, 64, 0.6); }

.chip {
  display: inline-block;
  padding: 5px 12px;
  border: 1px solid var(--p-line);
  margin: 3px 8px 3px 0;
  font-size: 11px;
  background: var(--p-cloud);
  color: var(--p-navy);
  letter-spacing: 0.5px;
}

.sign {
  margin-top: 60px;
  padding-top: 24px;
  border-top: 1px solid var(--p-line);
  font-family: var(--p-mono);
  font-size: 11px;
  color: rgba(11, 24, 64, 0.5);
  letter-spacing: 2px;
}

@media (max-width: 900px) {
  .tech-page { grid-template-columns: 1fr; }
  .main { padding: 40px 24px; }
  .side { padding: 40px 24px; }
  .spec-table th { width: 140px; }
}
</style>
