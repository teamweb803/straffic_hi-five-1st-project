<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

const samples = [
  { id: 1,  code: 'HERO-SNAP',       label: 'Hero × Snap',        fit: 'company / solution' },
  { id: 2,  code: 'SPLIT-MANIFEST',  label: 'Split Manifesto',    fit: 'company' },
  { id: 3,  code: 'EDGE-GRID',       label: 'Edge Card Grid',     fit: 'solution / technology' },
  { id: 4,  code: 'ARCH-TWIN',       label: 'Architecture Twin',  fit: 'technology / guide' },
  { id: 5,  code: 'OUTLINE-CTA',     label: 'Outline Title CTA',  fit: 'contact / guide' },
  { id: 6,  code: 'TIMELINE-RAIL',   label: 'Timeline Rail',      fit: 'company / guide' },
  { id: 7,  code: 'SPEC-SHEET',      label: 'Spec Sheet',         fit: 'technology' },
  { id: 8,  code: 'LANE-FORM',       label: 'Lane Flow Form',     fit: 'contact' },
  { id: 9,  code: 'KPI-MOSAIC',      label: 'KPI Mosaic',         fit: 'solution / technology' },
  { id: 10, code: 'DARK-EDITORIAL',  label: 'Dark Editorial',     fit: 'company / contact' }
]

const active = ref(1)
const activeSample = computed(() => samples.find((s) => s.id === active.value))

// Architecture Twin (#4) 카운트업
const counters = ref({ a: 0, b: 0, c: 0 })
const progress = ref({ a: 0, b: 0, c: 0 })
let raf = null
function animateMetrics() {
  cancelAnimationFrame(raf)
  const targets = { a: 42, b: 70, c: 97.3 }
  const start = performance.now()
  const tick = (now) => {
    const t = Math.min((now - start) / 1200, 1)
    const e = 1 - Math.pow(1 - t, 3)
    counters.value = {
      a: Math.round(targets.a * e),
      b: Math.round(targets.b * e),
      c: +(targets.c * e).toFixed(1)
    }
    progress.value = { a: 78 * e, b: 72 * e, c: 97.3 * e }
    if (t < 1) raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

watch(active, async (id) => {
  await nextTick()
  window.scrollTo({ top: 0, behavior: 'smooth' })
  if (id === 4 || id === 9) animateMetrics()
})

onMounted(() => {
  if (active.value === 4) animateMetrics()
})
onBeforeUnmount(() => cancelAnimationFrame(raf))

const milestones = [
  { year: '2024', title: '창립', desc: '엣지 기반 스마트톨링 R&D 시작' },
  { year: '2025', title: '시범 사업', desc: '도시고속도로 1개 노선에서 PoC 진행' },
  { year: '2026', title: '확장', desc: 'WebTransport 기반 차세대 톨링 시스템 정식 출시' },
  { year: '2027', title: '글로벌', desc: '동남아 4개 도시 게이트리스 톨링 수출' }
]
const stack = [
  { layer: 'AI / Vision', items: ['YOLOv8', 'OpenCV', 'EasyOCR', 'PaddleOCR'] },
  { layer: 'Edge / Ingress', items: ['WebTransport', 'aioquic', 'FastAPI', 'Protobuf'] },
  { layer: 'Backend', items: ['Spring Boot 3', 'Spring Security', 'JPA', 'PostgreSQL'] },
  { layer: 'Frontend', items: ['Vue 3', 'Pinia', 'Vue Router', 'Tailwind'] }
]
</script>

<template>
  <div class="preview-root">
    <!-- 시안 네비게이션 바 -->
    <nav class="preview-tabs">
      <div class="preview-tabs-inner">
        <div class="tabs-meta">
          <p class="tabs-eyebrow">SUBPAGE PREVIEW · 시안 10종</p>
          <p class="tabs-active">
            <span class="badge">{{ String(activeSample.id).padStart(2, '0') }}</span>
            <strong>{{ activeSample.label }}</strong>
            <em>{{ activeSample.code }} · {{ activeSample.fit }}</em>
          </p>
        </div>
        <div class="tabs-buttons">
          <button
            v-for="s in samples"
            :key="s.id"
            class="tab-btn"
            :class="{ 'is-active': s.id === active }"
            @click="active = s.id"
          >
            <span class="tab-num">{{ String(s.id).padStart(2, '0') }}</span>
            <span class="tab-label">{{ s.label }}</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- ============ 01. HERO × SNAP ============ -->
    <article v-show="active === 1" class="s1">
      <section class="s1-hero">
        <div class="s1-bg"></div>
        <div class="s1-grid-bg"></div>
        <div class="s1-inner">
          <p class="eyebrow">COMPANY · 회사소개</p>
          <h1>WE BUILD<br><span class="shimmer">FREE-FLOW</span><br>HIGHWAYS.</h1>
          <p class="lead">
            HiFive는 게이트 없이 흐르는 도로를 만드는 차세대 스마트톨링 기업입니다.
            엣지 컴퓨팅, AI 비전, WebTransport 기반 분산 처리로 다음 세대 통행 인프라를 설계합니다.
          </p>
          <div class="s1-actions">
            <a class="s1-btn primary">도입 상담 시작</a>
            <a class="s1-btn">PoC 신청</a>
          </div>
          <div class="s1-caption">
            <span>현장 AI</span><span>요금 정책</span><span>관제 UX</span>
          </div>
        </div>
      </section>
      <section class="s1-cards">
        <div class="s1-cards-inner">
          <p class="section-label">CORE PILLARS</p>
          <h2 class="section-title">FOUR LAYERS.<br>ONE FLOW.</h2>
          <div class="s1-grid">
            <div class="s1-card" v-for="(c, i) in [
              { t: 'Edge OCR', d: '카메라 단에서 차량/번호판을 즉시 인식.' },
              { t: 'GPS Toll', d: '주행 좌표 기반 구간 요금을 실시간 계산.' },
              { t: 'WebTransport', d: 'Protobuf 스트림으로 페이로드 70% 감소.' },
              { t: 'Live Ops', d: '검수, 정산, KPI를 한 화면에서 관제.' }
            ]" :key="i">
              <span class="s1-num">{{ String(i + 1).padStart(2, '0') }}</span>
              <h3>{{ c.t }}</h3>
              <p>{{ c.d }}</p>
            </div>
          </div>
        </div>
      </section>
    </article>

    <!-- ============ 02. SPLIT MANIFESTO ============ -->
    <article v-show="active === 2" class="s2">
      <div class="s2-grid">
        <aside class="s2-left">
          <p class="eyebrow">MANIFESTO</p>
          <h1>THE INVISIBLE<br>TOLL.</h1>
          <p class="s2-author">HIFIVE · 2026</p>
        </aside>
        <div class="s2-right">
          <p class="s2-drop">엣</p>
          <p class="s2-body">
            지에서 인식하고 클라우드에서 정산합니다. 도로 위 차량이 멈출 이유가
            없도록, 우리는 게이트가 사라진 톨링을 설계합니다. AI 비전과 WebTransport,
            그리고 분산 정산 엔진이 도로의 흐름을 바꿉니다.
          </p>
          <h2>FREE FLOW.</h2>
          <p class="s2-body">
            물리적 게이트 없이 정확하게 통행료를 정산해, 도로의 흐름을 멈추지 않게 합니다.
            진입, 주행, 이탈을 GPS 좌표 그래프로 추적해 1초 단위로 비용을 산정합니다.
          </p>
          <h2>EDGE FIRST.</h2>
          <p class="s2-body">
            모든 결정은 가장 가까운 엣지에서 — 빠르고 정확하게. 클라우드는 결과를
            받아 정산합니다. 네트워크 단절에도 이벤트는 유실되지 않습니다.
          </p>
          <h2>SMART HIGHWAY.</h2>
          <p class="s2-body">
            전국 모든 유료 도로를 단일 플랫폼으로 연결하는 차세대 인프라를 향해.
          </p>
          <p class="s2-sign">— HiFive Mobility Lab</p>
        </div>
      </div>
    </article>

    <!-- ============ 03. EDGE CARD GRID ============ -->
    <article v-show="active === 3" class="s3">
      <header class="s3-header">
        <p class="eyebrow">SOLUTION</p>
        <h1>FROM CAMERA<br>TO BILL.</h1>
        <p class="s3-lead">도로의 카메라부터 정산 시스템까지를 하나의 흐름으로 연결합니다.</p>
      </header>
      <div class="s3-grid">
        <article v-for="(c, i) in [
          { tag: 'AI Engine', t: 'Edge OCR', d: 'YOLOv8 + EasyOCR/PaddleOCR. 카메라 단에서 차량/번호판 ROI 추출과 동시 실행.', metric: '97.3%', metricLabel: 'Recognition' },
          { tag: 'Toll', t: 'Crossing Engine', d: '가상 통과선과 GPS 좌표 결합. ENTRY/EXIT 판정과 구간 요금 산정 자동화.', metric: '0.3s', metricLabel: 'Decision' },
          { tag: 'Transport', t: 'WebTransport', d: 'Jetson Edge → Python Ingress → Spring REST. Protobuf 바이너리 송신.', metric: '-70%', metricLabel: 'Payload' },
          { tag: 'Review', t: 'Review Queue', d: 'OCR 저신뢰도 케이스 자동 분리. 관리자 보정 후 정산 반영.', metric: '<3s', metricLabel: 'Latency' },
          { tag: 'Console', t: 'Operator Dashboard', d: '실시간 KPI, 통과 로그, GPS 구간 현황을 한 화면에서.', metric: '24/7', metricLabel: 'Live' },
          { tag: 'Open', t: 'Open API', d: '회원/요금/검수 REST API와 통과 이벤트 webhook 표준 제공.', metric: 'REST', metricLabel: 'Standard' }
        ]" :key="i" class="s3-card">
          <div class="s3-index">
            <span>{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="s3-tag">{{ c.tag }}</span>
          </div>
          <h3>{{ c.t }}</h3>
          <p>{{ c.d }}</p>
          <div class="s3-foot"><strong>{{ c.metric }}</strong>{{ c.metricLabel }}</div>
        </article>
      </div>
    </article>

    <!-- ============ 04. ARCHITECTURE TWIN ============ -->
    <article v-show="active === 4" class="s4">
      <header class="s4-head">
        <p class="eyebrow">SYSTEM ARCHITECTURE</p>
        <h1>NETWORK MAP × KPI METRICS</h1>
      </header>
      <div class="s4-body">
        <div class="s4-panel">
          <svg viewBox="0 0 480 360" class="s4-svg" aria-hidden="true">
            <defs>
              <radialGradient id="s4-glow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="#38BEF5" stop-opacity=".5"/>
                <stop offset="100%" stop-color="#38BEF5" stop-opacity="0"/>
              </radialGradient>
            </defs>
            <rect width="480" height="360" fill="#0B1840"/>
            <g stroke="rgba(255,255,255,0.06)">
              <line v-for="i in 12" :key="'h'+i" :x1="0" :x2="480" :y1="i*30" :y2="i*30"/>
              <line v-for="i in 16" :key="'v'+i" :x1="i*30" :x2="i*30" :y1="0" :y2="360"/>
            </g>
            <line x1="80" y1="280" x2="240" y2="180" stroke="#38BEF5" stroke-width="1.2" stroke-dasharray="4 4">
              <animate attributeName="stroke-dashoffset" from="0" to="-16" dur="1s" repeatCount="indefinite"/>
            </line>
            <line x1="240" y1="180" x2="400" y2="80" stroke="#38BEF5" stroke-width="1.2" stroke-dasharray="4 4">
              <animate attributeName="stroke-dashoffset" from="0" to="-16" dur="1.2s" repeatCount="indefinite"/>
            </line>
            <line x1="240" y1="180" x2="400" y2="280" stroke="#7A74FF" stroke-width="1.2" stroke-dasharray="4 4">
              <animate attributeName="stroke-dashoffset" from="0" to="-16" dur="1.4s" repeatCount="indefinite"/>
            </line>
            <line x1="80" y1="280" x2="80" y2="120" stroke="#FFCA3A" stroke-width="1.2" stroke-dasharray="4 4"/>
            <circle cx="80" cy="280" r="34" fill="url(#s4-glow)"/>
            <circle cx="80" cy="280" r="10" fill="#FF5C5C"/>
            <text x="80" y="312" text-anchor="middle" fill="#fff" font-family="Fira Mono" font-size="10">EDGE</text>
            <circle cx="80" cy="120" r="8" fill="#FFCA3A"/>
            <text x="80" y="100" text-anchor="middle" fill="#fff" font-family="Fira Mono" font-size="10">CAMERA</text>
            <circle cx="240" cy="180" r="34" fill="url(#s4-glow)"/>
            <circle cx="240" cy="180" r="12" fill="#4BD6FF"/>
            <text x="240" y="160" text-anchor="middle" fill="#fff" font-family="Fira Mono" font-size="10">INGRESS</text>
            <circle cx="400" cy="80" r="9" fill="#46FFB4"/>
            <text x="400" y="60" text-anchor="middle" fill="#fff" font-family="Fira Mono" font-size="10">SPRING API</text>
            <circle cx="400" cy="280" r="9" fill="#7A74FF"/>
            <text x="400" y="306" text-anchor="middle" fill="#fff" font-family="Fira Mono" font-size="10">DASHBOARD</text>
          </svg>
          <div class="s4-legend">
            <span>CAMERA</span><span>EDGE</span><span>INGRESS</span><span>API</span><span>UI</span>
          </div>
        </div>
        <div class="s4-metrics">
          <div class="s4-metric">
            <strong>{{ counters.a }}<em>ms</em></strong>
            <span>P95 Round-trip Latency</span>
            <div class="s4-bar"><i :style="{ width: progress.a + '%' }"></i></div>
          </div>
          <div class="s4-metric">
            <strong>{{ counters.b }}<em>%</em></strong>
            <span>Payload Reduction (Protobuf)</span>
            <div class="s4-bar"><i :style="{ width: progress.b + '%' }"></i></div>
          </div>
          <div class="s4-metric">
            <strong>{{ counters.c }}<em>%</em></strong>
            <span>OCR Accuracy (avg)</span>
            <div class="s4-bar"><i :style="{ width: progress.c + '%' }"></i></div>
          </div>
        </div>
      </div>
    </article>

    <!-- ============ 05. OUTLINE TITLE CTA ============ -->
    <article v-show="active === 5" class="s5">
      <div class="s5-inner">
        <p class="eyebrow">CONTACT</p>
        <h1 class="s5-outline">NEXT<br>GENERATION<br>ROAD.</h1>
        <p class="s5-copy">
          HiFive는 AI 번호판 인식, GPS 구간 요금 계산, 실시간 관제 데이터를 하나의
          운영 흐름으로 연결해 차세대 하이패스 전환의 운영 표준을 만듭니다.
        </p>
        <div class="s5-actions">
          <a class="s5-btn primary">도입 문의하기</a>
          <a class="s5-btn">관리자 로그인</a>
        </div>
        <div class="s5-info">
          <span>contact@hifive.io</span>
          <span>02-000-0000</span>
          <span>서울특별시 강남구</span>
        </div>
        <div class="s5-bottom">
          <span>© 2026 HiFive. Smart Tolling Platform.</span>
          <span>정확한 신호 · 멈춤 없는 흐름</span>
        </div>
      </div>
    </article>

    <!-- ============ 06. TIMELINE RAIL ============ -->
    <article v-show="active === 6" class="s6">
      <header class="s6-head">
        <p class="eyebrow">JOURNEY</p>
        <h1>FROM 2024<br>TO BEYOND.</h1>
      </header>
      <div class="s6-rail">
        <div class="s6-line">
          <div class="s6-scan"></div>
        </div>
        <div class="s6-nodes">
          <article v-for="(m, i) in milestones" :key="m.year" class="s6-node">
            <span class="s6-dot"></span>
            <p class="s6-year">{{ m.year }}</p>
            <p class="s6-title">{{ m.title }}</p>
            <p class="s6-desc">{{ m.desc }}</p>
            <span class="s6-mono">// step {{ String(i + 1).padStart(2, '0') }}</span>
          </article>
        </div>
      </div>
    </article>

    <!-- ============ 07. SPEC SHEET ============ -->
    <article v-show="active === 7" class="s7">
      <aside class="s7-side">
        <p class="s7-eyebrow">SPECIFICATION</p>
        <p class="s7-rev">REV · 2026.05</p>
        <ul class="s7-toc">
          <li><span>01</span> Overview</li>
          <li><span>02</span> AI / Vision</li>
          <li><span>03</span> Edge / Ingress</li>
          <li><span>04</span> Backend</li>
          <li><span>05</span> Frontend</li>
          <li><span>06</span> Performance</li>
        </ul>
        <p class="s7-foot">DOC ID — HF-STK-001</p>
      </aside>
      <div class="s7-main">
        <h1 class="s7-title">TECHNOLOGY<br>SPECIFICATION</h1>
        <table class="s7-table">
          <tbody>
            <tr v-for="s in stack" :key="s.layer">
              <th>{{ s.layer }}</th>
              <td>
                <span v-for="i in s.items" :key="i" class="s7-chip">{{ i }}</span>
              </td>
            </tr>
            <tr><th>Latency P95</th><td><strong>42 ms</strong> end-to-end</td></tr>
            <tr><th>Payload</th><td><strong>-70%</strong> vs JSON (Protobuf)</td></tr>
            <tr><th>Accuracy</th><td><strong>97.3%</strong> avg OCR confidence</td></tr>
            <tr><th>Availability</th><td><strong>99.95%</strong> rolling 30d</td></tr>
          </tbody>
        </table>
      </div>
    </article>

    <!-- ============ 08. LANE FLOW FORM ============ -->
    <article v-show="active === 8" class="s8">
      <div class="s8-bg">
        <div class="s8-lane"></div>
        <div class="s8-lane s8-lane-2"></div>
        <div class="s8-lane s8-lane-3"></div>
      </div>
      <div class="s8-inner">
        <div class="s8-head">
          <p class="eyebrow">CONTACT</p>
          <h1>1:1<br>도입 문의</h1>
          <p class="s8-lead">평일 09:00 ~ 18:00 / contact@hifive.io</p>
        </div>
        <form class="s8-form" @submit.prevent>
          <label>
            <span class="s8-label">// 제목</span>
            <input type="text" placeholder="예) 지방도 OO 노선 PoC 문의" />
          </label>
          <label>
            <span class="s8-label">// 내용</span>
            <textarea rows="5" placeholder="회사 / 부서 / 검토 중인 노선 정보를 알려주세요."></textarea>
          </label>
          <div class="s8-row">
            <label>
              <span class="s8-label">// 차량번호</span>
              <input type="text" placeholder="12가3456" />
            </label>
            <label>
              <span class="s8-label">// 차량 수</span>
              <input type="number" placeholder="1" />
            </label>
          </div>
          <button type="button" class="s8-btn">SEND →</button>
        </form>
      </div>
    </article>

    <!-- ============ 09. KPI MOSAIC ============ -->
    <article v-show="active === 9" class="s9">
      <header class="s9-head">
        <p class="eyebrow">PERFORMANCE</p>
        <h1>KPI MOSAIC.</h1>
        <p class="s9-lead">엣지 인식부터 정산 응답까지의 모든 운영 지표를 한눈에.</p>
      </header>
      <div class="s9-grid">
        <div class="s9-cell s9-big">
          <p class="s9-label">RECOGNITION</p>
          <strong>97.3<em>%</em></strong>
          <p class="s9-sub">LPR avg confidence (30d)</p>
          <span class="s9-arc"></span>
          <span class="s9-arc s9-arc-2"></span>
        </div>
        <div class="s9-cell"><p class="s9-label">P95 RTT</p><strong>42<em>ms</em></strong></div>
        <div class="s9-cell"><p class="s9-label">PAYLOAD</p><strong>-70<em>%</em></strong></div>
        <div class="s9-cell s9-dark">
          <p class="s9-label">UPTIME</p>
          <strong>99.95<em>%</em></strong>
          <p class="s9-sub">rolling availability</p>
        </div>
        <div class="s9-cell"><p class="s9-label">EVENTS / DAY</p><strong>1.2<em>M</em></strong></div>
        <div class="s9-cell"><p class="s9-label">REVIEW QUEUE</p><strong>0.4<em>%</em></strong></div>
        <div class="s9-cell s9-wide">
          <p class="s9-label">LATENCY DISTRIBUTION</p>
          <div class="s9-bars">
            <i v-for="(h, i) in [22, 38, 56, 70, 88, 76, 60, 44, 28, 18, 12, 8]" :key="i" :style="{ height: h + '%' }"></i>
          </div>
        </div>
      </div>
    </article>

    <!-- ============ 10. DARK EDITORIAL ============ -->
    <article v-show="active === 10" class="s10">
      <header class="s10-head">
        <p class="eyebrow">COMPANY</p>
        <h1>WE BUILD<br>THE INVISIBLE<br>TOLL.</h1>
        <p class="s10-lead">
          엣지에서 인식하고 클라우드에서 정산하는 차세대 통행 인프라 — HiFive 는 멈추지
          않는 도로를 설계합니다.
        </p>
      </header>
      <section class="s10-stack">
        <div class="s10-row">
          <span class="s10-num">01</span>
          <h3>FREE FLOW</h3>
          <p>물리적 게이트 없이 정확하게 통행료를 정산해, 도로의 흐름을 멈추지 않게 합니다.</p>
        </div>
        <div class="s10-row">
          <span class="s10-num">02</span>
          <h3>SMART HIGHWAY</h3>
          <p>전국 모든 유료 도로를 단일 플랫폼으로 연결하는 차세대 인프라.</p>
        </div>
        <div class="s10-row">
          <span class="s10-num">03</span>
          <h3>EDGE FIRST</h3>
          <p>모든 결정은 가장 가까운 엣지에서. 빠르고 정확하게.</p>
        </div>
        <div class="s10-row">
          <span class="s10-num">04</span>
          <h3>OPEN STACK</h3>
          <p>검증된 오픈소스 위에서. 엣지부터 프론트까지 모두 모던하게.</p>
        </div>
      </section>
      <footer class="s10-foot">
        <span>— HiFive Mobility Lab</span>
        <span>2026</span>
      </footer>
    </article>
  </div>
</template>

<style scoped>
/* =========================================
   공통 토큰 (메인 인덱스에서 계승)
   ========================================= */
.preview-root {
  --p-deep: #080C18;
  --p-navy: #0B1840;
  --p-blue: #1B3BE8;
  --p-sky: #38BEF5;
  --p-cloud: #E8EFFE;
  --p-line: rgba(11, 24, 64, 0.12);
  --p-headline: 'Big Shoulders Display', sans-serif;
  --p-mono: 'Fira Mono', monospace;

  background: var(--p-cloud);
  color: var(--p-navy);
  min-height: 100vh;
}
.preview-root .eyebrow {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-sky);
  margin: 0 0 14px;
}
.preview-root .section-label {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--p-sky);
  text-transform: uppercase;
  margin-bottom: 14px;
  letter-spacing: 1.4px;
}
.preview-root .section-title {
  font-family: var(--p-headline);
  font-size: clamp(40px, 6vw, 84px);
  line-height: 0.92;
  margin: 0;
}
.preview-root .shimmer {
  display: inline-block;
  background: linear-gradient(92deg, var(--p-blue), var(--p-sky), var(--p-blue));
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-stroke: 2px var(--p-blue);
  animation: prv-shimmer 3s linear infinite;
}
@keyframes prv-shimmer { to { background-position: -220% 0; } }

/* =========================================
   상단 시안 탭 네비
   ========================================= */
.preview-tabs {
  position: sticky;
  top: 64px;
  z-index: 30;
  background: rgba(11, 24, 64, 0.96);
  backdrop-filter: blur(12px);
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.preview-tabs-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 14px 24px 16px;
  display: grid;
  gap: 12px;
}
.tabs-eyebrow {
  font-family: var(--p-mono);
  font-size: 11px;
  letter-spacing: 1.6px;
  color: var(--p-sky);
  margin: 0;
  text-transform: uppercase;
}
.tabs-active {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 4px 0 0;
  font-family: var(--p-mono);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
.tabs-active strong {
  font-family: var(--p-headline);
  font-size: 22px;
  letter-spacing: 1px;
  color: #fff;
}
.tabs-active em {
  font-style: normal;
  color: rgba(255, 255, 255, 0.45);
}
.tabs-active .badge {
  font-family: var(--p-mono);
  background: var(--p-blue);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.tabs-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.78);
  font-family: var(--p-mono);
  font-size: 11px;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
}
.tab-btn:hover { background: rgba(255, 255, 255, 0.06); color: #fff; }
.tab-btn.is-active {
  background: var(--p-blue);
  border-color: var(--p-blue);
  color: #fff;
}
.tab-num { font-weight: 700; color: var(--p-sky); }
.tab-btn.is-active .tab-num { color: #fff; }
.tab-label { font-size: 12px; }

/* =========================================
   01. HERO × SNAP
   ========================================= */
.s1-hero {
  position: relative;
  min-height: 92vh;
  padding: 100px 36px 80px;
  display: flex;
  align-items: center;
  overflow: hidden;
  background: linear-gradient(180deg, #DDE8FB 0%, #C9D8F4 52%, #B6C9EA 100%);
}
.s1-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(60% 50% at 80% 30%, rgba(56,190,245,0.35), transparent 70%),
    radial-gradient(70% 60% at 10% 80%, rgba(27,59,232,0.18), transparent 70%);
  pointer-events: none;
}
.s1-grid-bg {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(11,24,64,0.06) 1px, transparent 1px),
    linear-gradient(180deg, rgba(11,24,64,0.05) 1px, transparent 1px);
  background-size: 80px 80px;
  mask-image: linear-gradient(180deg, transparent, #000 30%, #000 80%, transparent);
}
.s1-inner {
  position: relative;
  width: min(1220px, 100%);
  margin: 0 auto;
}
.s1 h1 {
  font-family: var(--p-headline);
  font-size: clamp(56px, 9vw, 132px);
  line-height: 0.86;
  margin: 0 0 24px;
  color: var(--p-navy);
  letter-spacing: 0;
}
.s1 .lead {
  max-width: 560px;
  color: rgba(11, 24, 64, 0.72);
  line-height: 1.78;
  margin: 0;
}
.s1-actions { display: flex; gap: 10px; margin-top: 30px; }
.s1-btn {
  display: inline-block;
  padding: 12px 22px;
  border-radius: 6px;
  background: rgba(255,255,255,0.5);
  border: 1px solid rgba(11,24,64,0.18);
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: transform 160ms ease;
}
.s1-btn.primary { background: var(--p-blue); color: #fff; border-color: var(--p-blue); }
.s1-btn:hover { transform: translateY(-2px); }
.s1-caption {
  display: flex;
  gap: 10px;
  margin-top: 36px;
  font-family: var(--p-mono);
  font-size: 11px;
  color: rgba(11, 24, 64, 0.6);
}
.s1-caption span {
  padding: 8px 12px;
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(11,24,64,0.1);
  border-radius: 99px;
}
.s1-cards { padding: 100px 36px; background: #fff; }
.s1-cards-inner { max-width: 1220px; margin: 0 auto; }
.s1-grid {
  margin-top: 42px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.s1-card {
  border: 1px solid var(--p-line);
  border-radius: 14px;
  padding: 28px 22px;
  background: #fff;
  transition: transform 200ms ease, border-color 200ms ease;
}
.s1-card:hover { transform: translateY(-4px); border-color: var(--p-blue); }
.s1-num {
  font-family: var(--p-mono);
  color: var(--p-blue);
  font-size: 12px;
  letter-spacing: 1px;
}
.s1-card h3 {
  font-family: var(--p-headline);
  font-size: 26px;
  margin: 14px 0 10px;
  color: var(--p-deep);
  letter-spacing: 0.5px;
}
.s1-card p { font-size: 13px; color: rgba(11,24,64,0.7); line-height: 1.6; margin: 0; }

/* =========================================
   02. SPLIT MANIFESTO
   ========================================= */
.s2 {
  background: #fff;
  min-height: 90vh;
  padding: 80px 36px 120px;
}
.s2-grid {
  max-width: 1280px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  gap: 80px;
  align-items: start;
}
.s2-left {
  position: sticky;
  top: 200px;
}
.s2-left h1 {
  font-family: var(--p-headline);
  font-size: clamp(64px, 9vw, 140px);
  line-height: 0.86;
  margin: 18px 0 10px;
  color: var(--p-deep);
}
.s2-author {
  font-family: var(--p-mono);
  font-size: 11px;
  letter-spacing: 2px;
  color: rgba(11, 24, 64, 0.5);
}
.s2-right { padding-top: 12px; }
.s2-drop {
  float: left;
  font-family: var(--p-headline);
  font-size: 92px;
  line-height: 0.8;
  color: var(--p-blue);
  margin: 0 14px -6px 0;
}
.s2-body {
  font-size: 17px;
  line-height: 1.85;
  color: rgba(11, 24, 64, 0.78);
  margin: 0 0 30px;
}
.s2-right h2 {
  font-family: var(--p-headline);
  font-size: clamp(36px, 4.4vw, 64px);
  margin: 56px 0 20px;
  border-top: 2px solid var(--p-deep);
  padding-top: 24px;
  color: var(--p-deep);
}
.s2-sign {
  font-family: var(--p-mono);
  color: rgba(11, 24, 64, 0.5);
  margin-top: 50px;
  font-size: 12px;
  letter-spacing: 2px;
}
@media (max-width: 900px) {
  .s2-grid { grid-template-columns: 1fr; gap: 30px; }
  .s2-left { position: static; }
}

/* =========================================
   03. EDGE CARD GRID
   ========================================= */
.s3 {
  background: #0A1024;
  color: #F3F7FF;
  padding: 100px 36px 120px;
}
.s3-header { max-width: 1220px; margin: 0 auto 50px; }
.s3 .eyebrow { color: #8EA0FF; }
.s3 h1 {
  font-family: var(--p-headline);
  font-size: clamp(48px, 7vw, 100px);
  line-height: 0.9;
  margin: 0 0 18px;
  color: #E6ECFF;
}
.s3-lead { color: #AEB9D6; max-width: 560px; line-height: 1.7; }
.s3-grid {
  max-width: 1220px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  border: 1px solid #26365F;
  border-radius: 8px;
  overflow: hidden;
  background: #101A34;
}
.s3-card {
  position: relative;
  padding: 32px 26px;
  background: #111B36;
  border-right: 1px solid #26365F;
  border-bottom: 1px solid #26365F;
  transition: background 200ms ease;
}
.s3-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: #5D79FF;
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 320ms ease;
}
.s3-card:hover { background: #152140; }
.s3-card:hover::before { transform: scaleX(1); }
.s3-index {
  display: flex;
  justify-content: space-between;
  font-family: var(--p-mono);
  font-size: 11px;
  color: #7E8CB2;
  margin-bottom: 22px;
}
.s3-tag { color: #8EA0FF; text-transform: uppercase; letter-spacing: 1px; }
.s3-card h3 {
  font-family: var(--p-headline);
  font-size: 28px;
  margin: 0 0 12px;
  color: #F5F8FF;
  letter-spacing: 0.5px;
}
.s3-card p { color: #AEB9D6; line-height: 1.7; font-size: 13px; margin: 0; }
.s3-foot {
  margin-top: 26px;
  padding-top: 16px;
  border-top: 1px solid #26365F;
  font-family: var(--p-mono);
  font-size: 11px;
  color: #7E8CB2;
}
.s3-foot strong {
  display: block;
  font-family: var(--p-headline);
  font-size: 32px;
  color: #DCE5FF;
  margin-bottom: 4px;
}
@media (max-width: 900px) {
  .s3-grid { grid-template-columns: repeat(2, 1fr); }
}

/* =========================================
   04. ARCHITECTURE TWIN
   ========================================= */
.s4 {
  background: var(--p-cloud);
  padding: 80px 36px 110px;
}
.s4-head { max-width: 1220px; margin: 0 auto 36px; text-align: center; }
.s4-head h1 {
  font-family: var(--p-headline);
  font-size: clamp(40px, 5vw, 72px);
  margin: 0;
  color: var(--p-navy);
}
.s4-body {
  max-width: 1220px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 30px;
}
.s4-panel {
  position: relative;
  background: var(--p-navy);
  border-radius: 8px;
  padding: 26px;
  border: 1px solid var(--p-line);
  box-shadow: 0 24px 60px rgba(8, 12, 24, 0.18);
  min-height: 460px;
}
.s4-svg { width: 100%; height: auto; display: block; }
.s4-legend {
  position: absolute;
  left: 26px;
  bottom: 18px;
  display: flex;
  gap: 14px;
  font-family: var(--p-mono);
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
}
.s4-legend span::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.s4-legend span:nth-child(1)::before { background: #FFCA3A; }
.s4-legend span:nth-child(2)::before { background: #FF5C5C; }
.s4-legend span:nth-child(3)::before { background: #4BD6FF; }
.s4-legend span:nth-child(4)::before { background: #46FFB4; }
.s4-legend span:nth-child(5)::before { background: #7A74FF; }
.s4-metrics {
  background: rgba(255,255,255,0.5);
  border: 1px solid var(--p-line);
  border-radius: 8px;
  padding: 32px;
  display: grid;
  gap: 22px;
  align-content: center;
  box-shadow: 0 24px 60px rgba(8, 12, 24, 0.1);
}
.s4-metric { border-bottom: 1px solid rgba(11, 24, 64, 0.14); padding-bottom: 18px; }
.s4-metric:last-child { border-bottom: none; padding-bottom: 0; }
.s4-metric strong {
  display: block;
  font-family: var(--p-headline);
  font-size: clamp(36px, 4vw, 56px);
  color: var(--p-blue);
  line-height: 1;
}
.s4-metric strong em { font-size: 24px; font-style: normal; margin-left: 4px; }
.s4-metric span {
  display: block;
  margin: 8px 0 14px;
  color: rgba(11, 24, 64, 0.7);
  font-weight: 600;
  font-size: 13px;
}
.s4-bar { height: 8px; border-radius: 99px; background: rgba(11,24,64,0.12); overflow: hidden; }
.s4-bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--p-blue), var(--p-sky));
  border-radius: inherit;
  transition: width 0.1s linear;
}
@media (max-width: 900px) {
  .s4-body { grid-template-columns: 1fr; }
}

/* =========================================
   05. OUTLINE TITLE CTA
   ========================================= */
.s5 {
  background: #0A1024;
  color: #F3F7FF;
  padding: 100px 36px 60px;
  min-height: 90vh;
}
.s5 .eyebrow { color: #8EA0FF; }
.s5-inner { max-width: 1220px; margin: 0 auto; }
.s5-outline {
  font-family: var(--p-headline);
  font-size: clamp(72px, 12vw, 180px);
  line-height: 0.86;
  margin: 0;
  color: transparent;
  -webkit-text-stroke: 1.5px #E6ECFF;
}
.s5-copy {
  max-width: 620px;
  margin: 30px 0 0;
  color: #AEB9D6;
  line-height: 1.85;
}
.s5-actions { display: flex; gap: 12px; margin-top: 36px; }
.s5-btn {
  padding: 12px 22px;
  border: 1px solid #26365F;
  background: #111B36;
  color: #E6ECFF;
  font-weight: 700;
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
}
.s5-btn.primary { background: var(--p-blue); border-color: var(--p-blue); color: #fff; }
.s5-info {
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
.s5-info span { padding: 16px 18px; border-left: 1px solid #26365F; }
.s5-info span:first-child { border-left: none; }
.s5-bottom {
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid #26365F;
  display: flex;
  justify-content: space-between;
  font-family: var(--p-mono);
  font-size: 11px;
  color: #7E8CB2;
}

/* =========================================
   06. TIMELINE RAIL
   ========================================= */
.s6 {
  background: #fff;
  padding: 100px 36px 120px;
}
.s6-head { max-width: 1220px; margin: 0 auto 60px; }
.s6 h1 {
  font-family: var(--p-headline);
  font-size: clamp(48px, 7vw, 100px);
  line-height: 0.9;
  margin: 0;
  color: var(--p-deep);
}
.s6-rail {
  max-width: 1220px;
  margin: 0 auto;
  position: relative;
  padding: 30px 0;
}
.s6-line {
  position: absolute;
  top: 80px;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(11, 24, 64, 0.12);
  overflow: hidden;
}
.s6-scan {
  position: absolute;
  top: 0;
  left: 0;
  width: 24%;
  height: 100%;
  background: linear-gradient(90deg, transparent, var(--p-sky), var(--p-blue), transparent);
  animation: s6-sweep 3.6s linear infinite;
}
@keyframes s6-sweep { to { transform: translateX(380%); } }
.s6-nodes {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  position: relative;
}
.s6-node {
  padding: 100px 18px 0;
  border-right: 1px dashed rgba(11, 24, 64, 0.12);
  position: relative;
}
.s6-node:last-child { border-right: none; }
.s6-dot {
  position: absolute;
  top: 71px;
  left: 18px;
  width: 18px;
  height: 18px;
  background: var(--p-blue);
  border-radius: 50%;
  box-shadow: 0 0 0 6px rgba(27, 59, 232, 0.18);
}
.s6-year {
  font-family: var(--p-headline);
  font-size: 56px;
  color: var(--p-blue);
  margin: 0 0 6px;
  line-height: 1;
}
.s6-title { font-weight: 700; color: var(--p-deep); margin: 6px 0; font-size: 16px; }
.s6-desc { color: rgba(11, 24, 64, 0.7); font-size: 13px; line-height: 1.6; margin: 0 0 16px; }
.s6-mono {
  font-family: var(--p-mono);
  font-size: 11px;
  color: var(--p-sky);
  letter-spacing: 1px;
}
@media (max-width: 900px) {
  .s6-nodes { grid-template-columns: repeat(2, 1fr); }
}

/* =========================================
   07. SPEC SHEET
   ========================================= */
.s7 {
  background: #fff;
  min-height: 90vh;
  display: grid;
  grid-template-columns: 280px 1fr;
}
.s7-side {
  background: #0A1024;
  color: #C9D2EA;
  padding: 60px 32px;
  font-family: var(--p-mono);
  font-size: 12px;
  border-right: 1px solid #26365F;
}
.s7-eyebrow { color: var(--p-sky); letter-spacing: 2px; margin: 0 0 6px; }
.s7-rev { color: rgba(255,255,255,0.5); margin: 0 0 32px; }
.s7-toc { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
.s7-toc li { display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px dashed #26365F; }
.s7-toc li span { color: var(--p-sky); }
.s7-foot { margin-top: 40px; color: rgba(255,255,255,0.4); font-size: 11px; }

.s7-main { padding: 60px 60px; }
.s7-title {
  font-family: var(--p-headline);
  font-size: clamp(48px, 6vw, 88px);
  line-height: 0.92;
  margin: 0 0 50px;
  color: var(--p-deep);
}
.s7-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--p-mono);
  font-size: 13px;
}
.s7-table tr { border-top: 1px solid var(--p-line); }
.s7-table tr:last-child { border-bottom: 1px solid var(--p-line); }
.s7-table th {
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
.s7-table td { padding: 18px 0; color: var(--p-navy); }
.s7-table td strong { font-family: var(--p-headline); font-size: 22px; color: var(--p-blue); margin-right: 8px; }
.s7-chip {
  display: inline-block;
  padding: 4px 10px;
  border: 1px solid var(--p-line);
  border-radius: 0;
  margin: 2px 6px 2px 0;
  font-size: 11px;
  background: var(--p-cloud);
}
@media (max-width: 900px) {
  .s7 { grid-template-columns: 1fr; }
  .s7-main { padding: 40px 24px; }
}

/* =========================================
   08. LANE FLOW FORM
   ========================================= */
.s8 {
  position: relative;
  min-height: 92vh;
  background: #0A1024;
  color: #fff;
  padding: 80px 36px;
  overflow: hidden;
}
.s8-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(60% 70% at 30% 20%, rgba(27, 59, 232, 0.45), transparent 60%),
    radial-gradient(50% 60% at 90% 90%, rgba(56, 190, 245, 0.3), transparent 70%);
  pointer-events: none;
}
.s8-lane {
  position: absolute;
  top: -10%;
  bottom: -10%;
  width: 3px;
  background: linear-gradient(180deg, transparent, var(--p-sky), transparent);
  animation: s8-flow 1.6s linear infinite;
}
.s8-lane { left: 22%; }
.s8-lane-2 { left: 50%; animation-delay: 0.4s; opacity: 0.7; }
.s8-lane-3 { left: 78%; animation-delay: 0.8s; opacity: 0.5; }
@keyframes s8-flow {
  from { transform: translateY(-30%); opacity: 0.2; }
  50% { opacity: 0.85; }
  to { transform: translateY(30%); opacity: 0.1; }
}
.s8-inner {
  position: relative;
  max-width: 1100px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 60px;
  align-items: center;
}
.s8 .eyebrow { color: var(--p-sky); }
.s8 h1 {
  font-family: var(--p-headline);
  font-size: clamp(56px, 7vw, 110px);
  line-height: 0.86;
  margin: 0;
  color: #fff;
}
.s8-lead {
  margin-top: 22px;
  font-family: var(--p-mono);
  color: rgba(255,255,255,0.5);
  font-size: 12px;
  letter-spacing: 1.4px;
}
.s8-form {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255,255,255,0.14);
  padding: 36px;
  display: grid;
  gap: 18px;
}
.s8-form label { display: grid; gap: 6px; }
.s8-label {
  font-family: var(--p-mono);
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--p-sky);
}
.s8-form input,
.s8-form textarea {
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 0;
  padding: 14px 16px;
  color: #fff;
  font-family: inherit;
  font-size: 14px;
  outline: none;
  transition: border-color 160ms ease;
}
.s8-form input:focus,
.s8-form textarea:focus { border-color: var(--p-sky); }
.s8-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.s8-btn {
  background: var(--p-blue);
  color: #fff;
  border: none;
  padding: 16px;
  font-family: var(--p-headline);
  font-size: 22px;
  letter-spacing: 2px;
  cursor: pointer;
  transition: background 160ms ease;
}
.s8-btn:hover { background: #1530c5; }
@media (max-width: 900px) {
  .s8-inner { grid-template-columns: 1fr; }
}

/* =========================================
   09. KPI MOSAIC
   ========================================= */
.s9 {
  background: var(--p-cloud);
  padding: 90px 36px 110px;
}
.s9-head { max-width: 1220px; margin: 0 auto 40px; }
.s9 h1 {
  font-family: var(--p-headline);
  font-size: clamp(48px, 7vw, 100px);
  margin: 0;
  color: var(--p-deep);
}
.s9-lead { color: rgba(11,24,64,0.7); margin-top: 14px; }
.s9-grid {
  max-width: 1220px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: 180px;
  gap: 14px;
}
.s9-cell {
  position: relative;
  background: #fff;
  border: 1px solid var(--p-line);
  border-radius: 8px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  box-shadow: 0 14px 30px rgba(8,12,24,0.06);
}
.s9-label {
  font-family: var(--p-mono);
  font-size: 11px;
  letter-spacing: 1.4px;
  color: var(--p-sky);
  margin: 0;
  text-transform: uppercase;
}
.s9-cell strong {
  font-family: var(--p-headline);
  font-size: clamp(40px, 4.5vw, 64px);
  color: var(--p-blue);
  line-height: 1;
}
.s9-cell strong em { font-size: 22px; font-style: normal; margin-left: 4px; color: var(--p-sky); }
.s9-sub { font-size: 12px; color: rgba(11,24,64,0.6); margin: 0; }
.s9-big {
  grid-column: span 2;
  grid-row: span 2;
  background: linear-gradient(135deg, #fff 0%, #f4f7ff 100%);
}
.s9-big strong { font-size: clamp(80px, 10vw, 140px); }
.s9-big strong em { font-size: 36px; }
.s9-arc {
  position: absolute;
  border: 1px solid rgba(27,59,232,0.2);
  border-radius: 50%;
  width: 280px;
  height: 280px;
  right: -60px;
  bottom: -100px;
  animation: s9-pulse 3s ease-in-out infinite;
}
.s9-arc-2 {
  width: 400px;
  height: 400px;
  right: -120px;
  bottom: -160px;
  animation-delay: 1s;
}
@keyframes s9-pulse { 50% { border-color: rgba(56,190,245,0.4); transform: scale(1.04); } }
.s9-dark { background: var(--p-navy); color: #fff; }
.s9-dark .s9-label { color: var(--p-sky); }
.s9-dark strong { color: #fff; }
.s9-dark .s9-sub { color: rgba(255,255,255,0.6); }
.s9-wide {
  grid-column: span 2;
  background: var(--p-deep);
  color: #fff;
}
.s9-wide .s9-label { color: var(--p-sky); }
.s9-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 100%;
  padding-top: 14px;
}
.s9-bars i {
  flex: 1;
  background: linear-gradient(180deg, var(--p-sky), var(--p-blue));
  border-radius: 2px;
  min-height: 10%;
}
@media (max-width: 900px) {
  .s9-grid { grid-template-columns: repeat(2, 1fr); }
  .s9-big, .s9-wide { grid-column: span 2; }
}

/* =========================================
   10. DARK EDITORIAL
   ========================================= */
.s10 {
  background: #0A1024;
  color: #E6ECFF;
  min-height: 92vh;
  padding: 100px 36px 60px;
  display: flex;
  flex-direction: column;
}
.s10 .eyebrow { color: var(--p-sky); }
.s10-head { max-width: 980px; margin: 0 auto 80px; }
.s10 h1 {
  font-family: var(--p-headline);
  font-size: clamp(72px, 11vw, 168px);
  line-height: 0.84;
  margin: 0;
  color: #fff;
  letter-spacing: 0.5px;
}
.s10-lead {
  margin-top: 36px;
  max-width: 580px;
  color: #AEB9D6;
  line-height: 1.85;
  font-size: 17px;
}
.s10-stack {
  max-width: 980px;
  margin: 0 auto;
  width: 100%;
  border-top: 1px solid #26365F;
}
.s10-row {
  display: grid;
  grid-template-columns: 80px 220px 1fr;
  gap: 30px;
  padding: 36px 0;
  border-bottom: 1px solid #26365F;
  align-items: baseline;
  transition: background 200ms ease, padding 200ms ease;
}
.s10-row:hover { background: rgba(255,255,255,0.02); padding-left: 14px; }
.s10-num {
  font-family: var(--p-mono);
  font-size: 14px;
  color: var(--p-sky);
  letter-spacing: 1px;
}
.s10-row h3 {
  font-family: var(--p-headline);
  font-size: 32px;
  margin: 0;
  color: #fff;
  letter-spacing: 1px;
}
.s10-row p {
  margin: 0;
  color: #AEB9D6;
  line-height: 1.75;
  font-size: 15px;
}
.s10-foot {
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
  .s10-row { grid-template-columns: 50px 1fr; }
  .s10-row h3 { grid-column: 2; }
  .s10-row p { grid-column: 2; margin-top: 6px; }
}
</style>
