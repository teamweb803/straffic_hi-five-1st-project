<script setup>
import { ref, computed, onMounted } from 'vue'
import EChartsPanel from '@/components/charts/EChartsPanel.vue'
import { pdmApi } from '@/api/pdm'

// ── 반응형 상태 ─────────────────────────────────────────────────
const summary = ref({
  totalCameraCount: 0,
  normalCameraCount: 0,
  warningCameraCount: 0,
  criticalCameraCount: 0,
  averageHealthScore: 0
})
const cameras = ref([])
const alerts = ref([])
const loading = ref(true)

// ── 데이터 로딩 ────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const [summaryRes, camerasRes, alertsRes] = await Promise.all([
      pdmApi.getDashboardSummary(),
      pdmApi.getCameras(),
      pdmApi.getAlerts(),
    ])
    summary.value = summaryRes.data
    cameras.value = camerasRes.data
    alerts.value = alertsRes.data
  } catch (e) {
    console.error('[PDM Master] 데이터 로딩 실패', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// ── 시각 포맷 ──────────────────────────────────────────────────
function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
}

// ── 카메라별 미처리 알림 수 ────────────────────────────────────
function alertCountFor(cameraId) {
  return alerts.value.filter(a => a.cameraId === cameraId && a.status !== 'RESOLVED').length
}

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

// ── 카메라별 Health Score 가로 막대 차트 ──────────────────────
const barOption = computed(() => {
  const cams = cameras.value
  const names  = cams.map(c => c.cameraCode)
  const scores = cams.map(c => c.healthScore ?? 0)

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 16, right: 52, bottom: 28, left: 14, containLabel: true },
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
      axisLabel: { color: EC.textMuted, fontSize: 12 }
    },
    series: [
      {
        name: 'Health Score',
        type: 'bar', barWidth: 22,
        data: scores,
        itemStyle: {
          color: (params) => levelColor(cams[params.dataIndex]?.riskLevel),
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
function csClass(level) {
  return { NORMAL: 'ok', WARNING: 'warn', CRITICAL: 'danger' }[level] ?? ''
}
function riskLabel(level) {
  return { NORMAL: '정상', WARNING: '주의', CRITICAL: '위험' }[level] ?? level
}
function directionLabel(d) {
  return { FRONT: '전방', REAR: '후방' }[d] ?? d
}
function statusLabel(s) {
  return { OPEN: '미처리', CHECKING: '확인 중', RESOLVED: '완료' }[s] ?? s
}
function statusClass(s) {
  return { OPEN: 'pdm-badge-warn', CHECKING: 'pdm-badge-info', RESOLVED: 'pdm-badge-ok' }[s] ?? ''
}

// ── 필터 ──────────────────────────────────────────────────────
const filterLevel = ref('ALL')
const filteredCameras = computed(() => {
  if (filterLevel.value === 'ALL') return cameras.value
  return cameras.value.filter(c => c.riskLevel === filterLevel.value)
})
</script>

<template>
<section class="pdm-page">

  <!-- 헤더 -->
  <section class="title-row">
    <h1>예지보전 현황</h1>
    <p>전체 카메라 인식 품질 기반 장비 이상 조기 탐지 집계</p>
  </section>

  <!-- KPI 카드 -->
  <section class="pdm-kpi-grid">
    <article class="pdm-kpi-card">
      <span>전체 카메라</span>
      <strong>{{ summary.totalCameraCount }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card">
      <span>정상</span>
      <strong class="pdm-ok">{{ summary.normalCameraCount }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card">
      <span>주의</span>
      <strong class="pdm-warn">{{ summary.warningCameraCount }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card">
      <span>위험</span>
      <strong class="pdm-danger">{{ summary.criticalCameraCount }}<small>대</small></strong>
    </article>
    <article class="pdm-kpi-card pdm-kpi-score">
      <span>평균 Health Score</span>
      <strong>{{ summary.averageHealthScore }}<small>점</small></strong>
      <div class="pdm-score-track">
        <div class="pdm-score-fill" :style="`width:${summary.averageHealthScore}%`"></div>
      </div>
    </article>
  </section>

  <!-- 차트 + 알림 -->
  <section class="pdm-mid-grid">

    <!-- 카메라별 Health Score 막대 차트 -->
    <article class="panel pdm-trend-panel pdm-trend-panel--fill">
      <div class="panel-head">
        <h2>카메라별 Health Score</h2>
        <small>정상(녹) / 주의(황) / 위험(적)</small>
      </div>
      <div class="pdm-chart-fill">
        <EChartsPanel :option="barOption" height="100%" />
      </div>
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
          :key="alert.alertId"
          class="pdm-alert-row"
        >
          <div class="pdm-alert-dot" :class="riskClass(alert.riskLevel)"></div>
          <div class="pdm-alert-body">
            <b>{{ alert.alertTitle }}</b>
            <span>{{ alert.cameraCode }}</span>
            <em>{{ alert.reasonText }}</em>
          </div>
          <div class="pdm-alert-meta">
            <span class="pdm-badge" :class="statusClass(alert.status)">{{ statusLabel(alert.status) }}</span>
            <time>{{ formatTime(alert.createdAt) }}</time>
          </div>
        </div>
        <div v-if="alerts.length === 0 && !loading" class="pdm-alert-row">
          <div class="pdm-alert-dot pdm-ok"></div>
          <div class="pdm-alert-body"><b>이상 알림 없음</b><span>모든 카메라 정상 운영 중</span></div>
        </div>
      </div>
    </article>
  </section>

  <!-- 카메라 현황 테이블 -->
  <article class="company-admin-panel">
    <div class="company-panel-head">
      <h3>카메라 상태 현황 <small>카메라별 Health Score 및 알림</small></h3>
      <div>
        <button
          v-for="opt in ['ALL','NORMAL','WARNING','CRITICAL']"
          :key="opt"
          type="button"
          :class="{ active: filterLevel === opt }"
          @click="filterLevel = opt"
        >{{ opt === 'ALL' ? '전체' : riskLabel(opt) }}</button>
      </div>
    </div>
    <table class="company-admin-table">
      <thead>
        <tr>
          <th>카메라 코드</th>
          <th>카메라명</th>
          <th>방향</th>
          <th>담당 차로</th>
          <th>상태</th>
          <th>Health Score</th>
          <th>미처리 알림</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="cam in filteredCameras" :key="cam.cameraId">
          <td><b>{{ cam.cameraCode }}</b></td>
          <td>{{ cam.cameraName }}</td>
          <td>{{ directionLabel(cam.direction) }}</td>
          <td>{{ cam.laneNames?.join(', ') }}</td>
          <td><span class="company-state" :class="csClass(cam.riskLevel)">{{ riskLabel(cam.riskLevel) }}</span></td>
          <td><b :class="riskClass(cam.riskLevel)">{{ cam.healthScore }}</b></td>
          <td>
            <span class="company-state" :class="alertCountFor(cam.cameraId) > 0 ? 'warn' : 'ok'">
              {{ alertCountFor(cam.cameraId) }}건
            </span>
          </td>
        </tr>
        <tr v-if="filteredCameras.length === 0 && !loading">
          <td colspan="7" style="text-align:center;color:#9fb2cb;padding:20px">데이터 없음</td>
        </tr>
      </tbody>
    </table>
  </article>

</section>
</template>
