<script setup>
const solutions = [
  { code: '01', title: 'Edge OCR', desc: 'YOLOv8 + EasyOCR/PaddleOCR 기반 엣지 인식. 카메라 단에서 즉시 차량/번호판 추출.' },
  { code: '02', title: 'Crossing Engine', desc: '가상 통과선 알고리즘이 ENTRY / EXIT 을 결정. GPS 와 결합해 구간 요금 계산.' },
  { code: '03', title: 'WebTransport Ingress', desc: 'Jetson Edge 이벤트를 Protobuf 바이너리로 Python Ingress에 송신하고 Spring REST ingest로 전달.' },
  { code: '04', title: 'Review Queue', desc: 'OCR 저신뢰도 케이스를 검수 큐로 자동 분리. 관리자 보정 후 정산 반영.' },
  { code: '05', title: 'Operator Dashboard', desc: '실시간 KPI, 통과 로그, GPS 구간 현황을 한 화면에서 모니터링.' },
  { code: '06', title: 'Open API', desc: '회원/요금/검수 API 와 통과 이벤트 webhook. 외부 정산 시스템과 즉시 연동.' }
]

const pipeline = [
  { code: '01', t: '차로 카메라', d: '차량/번호판 ROI 추출 (YOLOv8 + OpenCV).' },
  { code: '02', t: 'Jetson Edge', d: 'YOLO/OCR 병렬 처리와 PassageEvent Protobuf 생성.' },
  { code: '03', t: 'Python Ingress', d: 'WebTransport 수신 후 Spring REST ingest로 전달.' },
  { code: '04', t: 'Spring Boot 백엔드', d: '이벤트 저장, 중복 처리, GPS telemetry, 정산 / 검수 처리.' },
  { code: '05', t: 'Vue 관제 대시보드', d: '실시간 모니터링 + 저신뢰 차량 보정.' }
]
</script>

<template>
  <div class="solution-page">
    <section class="hero">
      <p class="eyebrow">SOLUTION · 솔루션</p>
      <h1 class="outline">FROM<br>CAMERA<br>TO BILL.</h1>
      <p class="copy">
        HiFive는 도로의 카메라부터 정산 시스템까지를 하나의 흐름으로 연결합니다.
        엣지 인식 · 가상 통과선 · WebTransport 전송 · 실시간 정산을 단일 플랫폼으로
        제공합니다.
      </p>
      <div class="actions">
        <router-link to="/contact" class="btn primary">도입 상담</router-link>
        <router-link to="/technology" class="btn">기술 스택 보기</router-link>
      </div>
      <div class="info">
        <span>엣지 AI 인식</span>
        <span>GPS 구간 정산</span>
        <span>실시간 관제</span>
      </div>
    </section>

    <section class="grid-section">
      <p class="eyebrow light">SIX MODULES</p>
      <h2>END-TO-END MODULES.</h2>
      <div class="grid">
        <article v-for="s in solutions" :key="s.code" class="card">
          <span class="code">{{ s.code }}</span>
          <h3>{{ s.title }}</h3>
          <p>{{ s.desc }}</p>
        </article>
      </div>
    </section>

    <section class="pipeline">
      <p class="eyebrow">PIPELINE</p>
      <h2 class="outline small">END-TO-END FLOW.</h2>
      <ol>
        <li v-for="p in pipeline" :key="p.code">
          <span class="step">{{ p.code }}</span>
          <div>
            <strong>{{ p.t }}</strong>
            <p>{{ p.d }}</p>
          </div>
        </li>
      </ol>
    </section>

    <footer class="foot">
      <span>© 2026 HiFive. Smart Tolling Platform.</span>
      <span>정확한 신호 · 멈춤 없는 흐름</span>
    </footer>
  </div>
</template>

<style scoped>
.solution-page {
  --p-deep: #080C18;
  --p-navy: #0B1840;
  --p-blue: #1B3BE8;
  --p-sky: #38BEF5;
  --p-cloud: #E8EFFE;
  --p-headline: 'Big Shoulders Display', sans-serif;
  --p-mono: 'Fira Mono', monospace;
  background: #0A1024;
  color: #F3F7FF;
  min-height: 100vh;
}

.eyebrow {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #8EA0FF;
  margin: 0 0 14px;
}
.eyebrow.light { color: var(--p-blue); }

.hero { padding: 100px 36px 80px; }
.hero > * { max-width: 1220px; margin-left: auto; margin-right: auto; }
.outline {
  font-family: var(--p-headline);
  font-size: clamp(72px, 12vw, 180px);
  line-height: 0.86;
  margin: 0;
  color: transparent;
  -webkit-text-stroke: 1.5px #E6ECFF;
}
.outline.small {
  font-size: clamp(40px, 5vw, 72px);
  -webkit-text-stroke: 1.2px #E6ECFF;
  margin: 0 0 32px;
}
.copy {
  max-width: 620px;
  margin: 30px auto 0 0;
  color: #AEB9D6;
  line-height: 1.85;
}
.actions { display: flex; gap: 12px; margin-top: 36px; }
.btn {
  padding: 12px 22px;
  border: 1px solid #26365F;
  background: #111B36;
  color: #E6ECFF;
  font-weight: 700;
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}
.btn.primary { background: var(--p-blue); border-color: var(--p-blue); color: #fff; }
.info {
  margin-top: 56px;
  border: 1px solid #26365F;
  border-radius: 8px;
  background: #101A34;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  font-family: var(--p-mono);
  font-size: 12px;
  color: #AEB9D6;
  overflow: hidden;
}
.info span { padding: 16px 18px; border-left: 1px solid #26365F; }
.info span:first-child { border-left: none; }

.grid-section {
  background: var(--p-cloud);
  color: var(--p-navy);
  padding: 100px 36px;
}
.grid-section > * { max-width: 1220px; margin-left: auto; margin-right: auto; }
.grid-section h2 {
  font-family: var(--p-headline);
  font-size: clamp(40px, 5vw, 72px);
  margin: 0 0 36px;
  color: var(--p-deep);
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  border: 1px solid rgba(11, 24, 64, 0.16);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.card {
  position: relative;
  padding: 32px 26px;
  border-right: 1px solid rgba(11, 24, 64, 0.12);
  border-bottom: 1px solid rgba(11, 24, 64, 0.12);
  transition: background 200ms ease;
}
.card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--p-blue);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 320ms ease;
}
.card:hover { background: #f4f7ff; }
.card:hover::before { transform: scaleX(1); }
.code {
  font-family: var(--p-mono);
  color: var(--p-blue);
  font-size: 12px;
  letter-spacing: 1.2px;
}
.card h3 {
  font-family: var(--p-headline);
  font-size: 26px;
  margin: 14px 0 10px;
  color: var(--p-deep);
  letter-spacing: 0.5px;
}
.card p { color: rgba(11, 24, 64, 0.7); line-height: 1.7; font-size: 13px; margin: 0; }

.pipeline { padding: 100px 36px; background: #0A1024; }
.pipeline > * { max-width: 1220px; margin-left: auto; margin-right: auto; }
.pipeline ol {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0;
  border-top: 1px solid #26365F;
  border-bottom: 1px solid #26365F;
}
.pipeline li {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 30px;
  padding: 26px 0;
  border-bottom: 1px solid #26365F;
  align-items: baseline;
  transition: padding 200ms ease;
}
.pipeline li:last-child { border-bottom: none; }
.pipeline li:hover { padding-left: 14px; }
.step {
  font-family: var(--p-headline);
  font-size: 36px;
  color: var(--p-sky);
  line-height: 1;
}
.pipeline li strong {
  display: block;
  color: #fff;
  font-size: 18px;
  margin-bottom: 6px;
}
.pipeline li p { color: #AEB9D6; line-height: 1.7; margin: 0; font-size: 14px; }

.foot {
  background: #0A1024;
  border-top: 1px solid #26365F;
  padding: 24px 36px;
  display: flex;
  justify-content: space-between;
  font-family: var(--p-mono);
  font-size: 11px;
  color: #7E8CB2;
}

@media (max-width: 900px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
  .info { grid-template-columns: 1fr; }
  .info span { border-left: none; border-top: 1px solid #26365F; }
  .info span:first-child { border-top: none; }
}
@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
