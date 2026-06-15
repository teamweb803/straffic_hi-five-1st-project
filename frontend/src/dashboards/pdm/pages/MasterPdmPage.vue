<script setup>
import { ref, computed } from 'vue'
import EChartsPanel from '@/components/charts/EChartsPanel.vue'

// ── 정적 목업: 전체 지점 카메라 현황 ───────────────────────────
const centers = [
  {
    id: 'SEOUL',
    name: '서울 톨게이트',
    front: { code: 'CAM-F-01', score: 95, level: 'NORMAL',   ocr: 96.2, match: 95.8 },
    rear:  { code: 'CAM-R-01', score: 89, level: 'NORMAL',   ocr: 90.1, match: 88.4 },
    alerts: 0
  },
  {
    id: 'SUWON',
    name: '수원 톨게이트',
    front: { code: 'CAM-F-01', score: 88, level: 'NORMAL',   ocr: 89.4, match: 88.1 },
    rear:  { code: 'CAM-R-01', score: 68, level: 'WARNING',  ocr: 71.8, match: 75.3 },
    alerts: 2
  },
  {
    id: 'DAEJEON',
    name: '대전 톨게이트',
    front: { code: 'CAM-F-01', score: 72, level: 'WARNING',  ocr: 74.2, match: 73.0 },
    rear:  { code: 'CAM-R-01', score: 65, level: 'WARNING',  ocr: 68.3, match: 70.1 },
    alerts: 3
  },
  {
    id: 'DAEGU',
    name: '대구 톨게이트',
    front: { code: 'CAM-F-01', score: 91, level: 'NORMAL',   ocr: 92.5, match: 91.9 },
    rear:  { code: 'CAM-R-01', score: 45, level: 'CRITICAL', ocr: 48.7, match: 52.1 },
    alerts: 1
  },
  {
    id: 'BUSAN',
    name: '부산 톨게이트',
    front: { code: 'CAM-F-01', score: 93, level: 'NORMAL',   ocr: 94.0, match: 93.7 },
    rear:  { code: 'CAM-R-01', score: 87, level: 'NORMAL',   ocr: 88.2, match: 87.9 },
    alerts: 0
  },
  {
    id: 'GWANGJU',
    name: '광주 톨게이트',
    front: { code: 'CAM-F-01', score: 74, level: 'WARNING',  ocr: 76.1, match: 74.8 },
    rear:  { code: 'CAM-R-01', score: 82, level: 'NORMAL',   ocr: 83.5, match: 82.0 },
    alerts: 1
  },
  {
    id: 'GANGNEUNG',
    name: '강릉 톨게이트',
    front: { code: 'CAM-F-01', score: 90, level: 'NORMAL',   ocr: 91.3, match: 90.8 },
    rear:  { code: 'CAM-R-01', score: 86, level: 'NORMAL',   ocr: 87.0, match: 85.5 },
    alerts: 0
  },
  {
    id: 'JEJU',
    name: '제주 톨게이트',
    front: { code: 'CAM-F-01', score: 85, level: 'NORMAL',   ocr: 86.4, match: 85.2 },
    rear:  { code: 'CAM-R-01', score: 70, level: 'WARNING',  ocr: 72.5, match: 71.0 },
    alerts: 1
  }
]

const alerts = [
  { id: 1, center: '대구 톨게이트', cam: 'CAM-R-01', level: 'CRITICAL', title: '카메라 심각 손상 의심',       reason: '급격한 화질 저하',          action: '즉시 현장 점검',     status: 'OPEN',     time: '14:31' },
  { id: 2, center: '수원 톨게이트', cam: 'CAM-R-01', level: 'WARNING',  title: 'OCR 신뢰도 연속 하락',       reason: '렌즈 오염 의심',            action: '렌즈 청소',          status: 'OPEN',     time: '14:28' },
  { id: 3, center: '대전 톨게이트', cam: 'CAM-F-01', level: 'WARNING',  title: '인식 성공률 임계값 미달',    reason: '조명 환경 변화',            action: '조명 상태 확인',     status: 'CHECKING', time: '14:20' },
  { id: 4, center: '대전 톨게이트', cam: 'CAM-R-01', level: 'WARNING',  title: '전후방 일치율 저하',         reason: '카메라 정렬 이상',          action: '각도 재조정',        status: 'CHECKING', time: '14:15' },
  { id: 5, center: '광주 톨게이트', cam: 'CAM-F-01', level: 'WARNING',  title: '품질 지표 복합 하락',        reason: '렌즈 이물질 의심',          action: '렌즈 및 센서 점검', status: 'OPEN',     time: '13:55' },
  { id: 6, center: '제주 톨게이트', cam: 'CAM-R-01', level: 'WARNING',  title: 'OCR 신뢰도 경계값 도달',    reason: '자연광 영향',               action: '모니터링 강화',      status: 'RESOLVED', time: '13:42' }
]

// ── KPI 집계 ────────────────────────────────────────────────────
const kpi = computed(() => {
  let total = 0, normal = 0, warning = 0, critical = 0, scoreSum = 0
  for (const c of centers) {
    for (const cam of [c.front, c.rear]) {
      total++
      scoreSum += cam.score
      if (cam.level === 'NORMAL') normal++
      else if (cam.level === 'WARNING') warning++
      else critical++
    }
  }
  return { total, normal, warning, critical, avg: (scoreSum / total).toFixed(1) }
})

// ── ECharts 색상 토큰 ───────────────────────────────────────────
const EC = {
  textMuted: '#9fb2cb',
  gridLine:  'rgba(117,151,194,0.14)',
  green:     '#4cdf66',
  blue:      '#2f8cff',
  amber:     '#f5b84b',
  red:       '#ef5a54'
}

function levelColor(level) {
  return { NORMAL: EC.green, WARNING: EC.amber, CRITICAL: EC.red }[level] ?? EC.blue
}

// 지점별 Health Score 가로 막대 차트
const barOption = computed(() => {
  const names = centers.map(c => c.name.replace(' 톨게이트', ''))
  const frontScores = centers.map(c => c.front.score)
  const rearScores  = centers.map(c => c.rear.score)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      top: 4,
      textStyle: { color: EC.textMuted, fontSize: 12 },
      itemWidth: 12, itemHeight: 8
    },
    grid: { top: 36, right: 20, bottom: 28, left: 14, containLabel: true },
    xAxis: {
      type: 'value', min: 0, max: 100,
      splitLine: { lineStyle: { color: EC.gridLine } },
      axisLabel: { color: EC.textMuted, fontSize: 11, formatter: '{value}' }
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLine: { lineStyle: { color: EC.gridLine } },
      axisTick: { show: false },
      axisLabel: { color: EC.textMuted, fontSize: 11 }
    },
    series: [
      {
        name: '전방 Health Score',
        type: 'bar', barMaxWidth: 14,
        data: frontScores,
        itemStyle: {
          color: (params) => levelColor(centers[params.dataIndex].front.level),
          borderRadius: [0, 4, 4, 0]
        },
        label: { show: true, position: 'right', color: EC.textMuted, fontSize: 11, formatter: '{c}' }
      },
      {
        name: '후방 Health Score',
        type: 'bar', barMaxWidth: 14,
        data: rearScores,
        itemStyle: {
          color: (params) => {
            const c = levelColor(centers[params.dataIndex].rear.level)
            return c + 'bb'
          },
          borderRadius: [0, 4, 4, 0]
        },
        label: { show: true, position: 'right', color: EC.textMuted, fontSize: 11, formatter: '{c}' }
      }
    ]
  }
})

// ── 헬퍼 ──────────────────────────────────────────────────────
function riskClass(level) {
  return { NORMAL: 'pdm-ok', WARNING: 'pdm-warn', CRITICAL: 'pdm-danger' }[level] ?? ''
}
function riskLabel(level) {
  return { NORMAL: '정상', WARNING: '주의', CRITICAL: '위험' }[level] ?? level
}
function statusLabel(s) {
  return { OPEN: '미처리', CHECKING: '확인 중', RESOLVED: '완료' }[s] ?? s
}
function statusClass(s) {
  return { OPEN: 'pdm-badge-warn', CHECKING: 'pdm-badge-info', RESOLVED: 'pdm-badge-ok' }[s] ?? ''
}

// 필터
const filterLevel = ref('ALL')
const filteredCenters = computed(() => {
  if (filterLevel.value === 'ALL') return centers
  return centers.filter(c =>
    c.front.level === filterLevel.value || c.rear.level === filterLevel.value
  )
})
</script>

<template>
<section class="pdm-page">

  <!-- 헤더 -->
  <section class="title-row">
    <h1>예지보전 현황</h1>
    <p>전체 지점 카메라 인식 품질 기반 장비 이상 조기 탐지 집계</p>
  </section>

  <!-- KPI 카드 -->
  <section class="pdm-kpi-grid">
    <article class="pdm-kpi-card">
      <span>전체 카메라</span>
      <strong>{{ kpi.total }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card">
      <span>정상</span>
      <strong class="pdm-ok">{{ kpi.normal }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card">
      <span>주의</span>
      <strong class="pdm-warn">{{ kpi.warning }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card">
      <span>위험</span>
      <strong class="pdm-danger">{{ kpi.critical }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card pdm-kpi-score">
      <span>평균 Health Score</span>
      <strong>{{ kpi.avg }}<small>점</small></strong>
      <div class="pdm-score-track">
        <div class="pdm-score-fill" :style="`width:${kpi.avg}%`"></div>
      </div>
    </article>
  </section>

  <!-- 차트 + 알림 -->
  <section class="pdm-mid-grid">

    <!-- 지점별 Health Score 막대 차트 -->
    <article class="panel pdm-trend-panel">
      <div class="panel-head">
        <h2>지점별 Health Score</h2>
        <small>전방(진) / 후방(연)</small>
      </div>
      <EChartsPanel :option="barOption" :height="280" />
    </article>

    <!-- 전체 알림 -->
    <article class="panel pdm-alert-panel">
      <div class="panel-head">
        <h2>이상 알림</h2>
        <span class="pdm-count-chip">{{ alerts.length }}</span>
      </div>
      <div class="pdm-alert-list">
        <div
          v-for="alert in alerts"
          :key="alert.id"
          class="pdm-alert-row"
        >
          <div class="pdm-alert-dot" :class="riskClass(alert.level)"></div>
          <div class="pdm-alert-body">
            <b>{{ alert.title }}</b>
            <span>{{ alert.center }} · {{ alert.cam }}</span>
            <em>{{ alert.reason }}</em>
          </div>
          <div class="pdm-alert-meta">
            <span class="pdm-badge" :class="statusClass(alert.status)">{{ statusLabel(alert.status) }}</span>
            <time>{{ alert.time }}</time>
          </div>
        </div>
      </div>
    </article>
  </section>

  <!-- 지점별 카메라 현황 테이블 -->
  <article class="panel pdm-compare-panel">
    <div class="panel-head">
      <h2>지점별 카메라 현황</h2>
      <div class="pdm-filter-tabs">
        <button
          v-for="opt in ['ALL','NORMAL','WARNING','CRITICAL']"
          :key="opt"
          type="button"
          :class="{ active: filterLevel === opt }"
          @click="filterLevel = opt"
        >{{ opt === 'ALL' ? '전체' : riskLabel(opt) }}</button>
      </div>
    </div>
    <table class="pdm-compare-table pdm-center-table">
      <thead>
        <tr>
          <th>지점</th>
          <th>전방 카메라</th>
          <th>Health</th>
          <th>OCR</th>
          <th>일치율</th>
          <th>후방 카메라</th>
          <th>Health</th>
          <th>OCR</th>
          <th>일치율</th>
          <th>알림</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="c in filteredCenters"
          :key="c.id"
          :class="{ 'pdm-mismatch-row': c.front.level !== 'NORMAL' || c.rear.level !== 'NORMAL' }"
        >
          <td><b style="color:inherit">{{ c.name }}</b></td>
          <!-- 전방 -->
          <td>
            <span class="pdm-risk-badge" :class="riskClass(c.front.level)">{{ riskLabel(c.front.level) }}</span>
          </td>
          <td><b :class="riskClass(c.front.level)">{{ c.front.score }}</b></td>
          <td>{{ c.front.ocr }}%</td>
          <td>{{ c.front.match }}%</td>
          <!-- 후방 -->
          <td>
            <span class="pdm-risk-badge" :class="riskClass(c.rear.level)">{{ riskLabel(c.rear.level) }}</span>
          </td>
          <td><b :class="riskClass(c.rear.level)">{{ c.rear.score }}</b></td>
          <td>{{ c.rear.ocr }}%</td>
          <td>{{ c.rear.match }}%</td>
          <!-- 알림 -->
          <td>
            <span v-if="c.alerts > 0" class="pdm-badge pdm-badge-warn">{{ c.alerts }}</span>
            <span v-else class="pdm-badge pdm-badge-ok">0</span>
          </td>
        </tr>
      </tbody>
    </table>
  </article>

</section>
</template>
