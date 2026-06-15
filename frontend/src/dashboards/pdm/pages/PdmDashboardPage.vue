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
const compareResults = ref([])
const qualityMetrics = ref({})
const selectedCam = ref(null)
const loading = ref(true)

// ── 시각 포맷 ──────────────────────────────────────────────────
function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
}
function formatDateTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

// ── 알림 차로 이름 헬퍼 ────────────────────────────────────────
function alertLaneLabel(alert) {
  if (alert.laneId == null) return ''
  const cam = cameras.value.find(c => c.cameraId === alert.cameraId)
  if (!cam) return `${alert.laneId}차로`
  const idx = cam.laneIds?.indexOf(alert.laneId) ?? -1
  return idx >= 0 && cam.laneNames?.[idx] ? cam.laneNames[idx] : `${alert.laneId}차로`
}

// ── 데이터 로딩 ────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const [summaryRes, camerasRes, alertsRes, compareRes] = await Promise.all([
      pdmApi.getDashboardSummary(),
      pdmApi.getCameras(),
      pdmApi.getAlerts(),
      pdmApi.getCompareResults(),
    ])
    summary.value = summaryRes.data
    alerts.value = alertsRes.data
    compareResults.value = compareRes.data

    // 카메라 상세 (avgOcrConfidence, successRate 등 포함)
    const camList = camerasRes.data
    const detailRes = await Promise.all(camList.map(c => pdmApi.getCameraDetail(c.cameraId)))
    cameras.value = detailRes.map(r => r.data)

    if (cameras.value.length > 0 && selectedCam.value === null) {
      selectedCam.value = cameras.value[0].cameraId
    }

    // 품질 추세 (카메라별)
    const metricsRes = await Promise.all(
      cameras.value.map(c => pdmApi.getQualityMetrics(c.cameraId).catch(() => ({ data: [] })))
    )
    const map = {}
    cameras.value.forEach((c, i) => { map[c.cameraId] = metricsRes[i].data })
    qualityMetrics.value = map

  } catch (e) {
    console.error('[PDM] 데이터 로딩 실패', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// ── ECharts 공통 색상 토큰 ──────────────────────────────────────
const EC = {
  textMuted: '#9fb2cb',
  textBase:  '#dce9f8',
  gridLine:  'rgba(117,151,194,0.14)',
  green:     '#4cdf66',
  blue:      '#2f8cff',
  amber:     '#f5b84b',
  red:       '#ef5a54'
}

// ── 품질 추세 라인 차트 ─────────────────────────────────────────
const trendOption = computed(() => {
  const metrics = qualityMetrics.value[selectedCam.value] ?? []
  const labels     = metrics.map(m => formatTime(m.bucketStart))
  const ocrData    = metrics.map(m => parseFloat((m.avgOcrConfidence ?? 0).toFixed(1)))
  const successData= metrics.map(m => parseFloat((m.successRate     ?? 0).toFixed(1)))
  const matchData  = metrics.map(m => parseFloat((m.matchRate       ?? 0).toFixed(1)))

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: {
      top: 4,
      textStyle: { color: EC.textMuted, fontSize: 12 },
      itemWidth: 12, itemHeight: 8
    },
    grid: { top: 40, right: 16, bottom: 28, left: 48, containLabel: false },
    xAxis: {
      type: 'category',
      data: labels.length ? labels : ['—'],
      axisLine: { lineStyle: { color: EC.gridLine } },
      axisTick: { show: false },
      axisLabel: { color: EC.textMuted, fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      min: 50, max: 100,
      splitLine: { lineStyle: { color: EC.gridLine } },
      axisLabel: { color: EC.textMuted, fontSize: 11 }
    },
    series: [
      {
        name: 'OCR 신뢰도(%)',
        type: 'line', smooth: true,
        data: ocrData,
        lineStyle: { color: EC.blue, width: 2 },
        itemStyle: { color: EC.blue },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(47,140,255,.22)' }, { offset: 1, color: 'rgba(47,140,255,.02)' }] } },
        symbol: 'circle', symbolSize: 5
      },
      {
        name: '인식 성공률(%)',
        type: 'line', smooth: true,
        data: successData,
        lineStyle: { color: EC.green, width: 2 },
        itemStyle: { color: EC.green },
        symbol: 'circle', symbolSize: 5
      },
      {
        name: '전후방 일치율(%)',
        type: 'line', smooth: true,
        data: matchData,
        lineStyle: { color: EC.amber, width: 2 },
        itemStyle: { color: EC.amber },
        symbol: 'circle', symbolSize: 5
      }
    ]
  }
})

// ── 게이지 차트 ─────────────────────────────────────────────────
function gaugeOption(score, level) {
  const color = level === 'NORMAL' ? EC.green : level === 'WARNING' ? EC.amber : EC.red
  return {
    backgroundColor: 'transparent',
    series: [{
      type: 'gauge',
      radius: '88%',
      startAngle: 200, endAngle: -20,
      min: 0, max: 100,
      splitNumber: 5,
      axisLine: {
        lineStyle: {
          width: 10,
          color: [
            [score / 100, color],
            [1, 'rgba(255,255,255,0.08)']
          ]
        }
      },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, '10%'],
        fontSize: 26, fontWeight: 800,
        color, formatter: '{value}'
      },
      title: { offsetCenter: [0, '38%'], fontSize: 11, color: EC.textMuted },
      data: [{ value: score, name: 'Health Score' }]
    }]
  }
}

// ── 헬퍼 ──────────────────────────────────────────────────────
function riskClass(level) {
  return { NORMAL: 'pdm-ok', WARNING: 'pdm-warn', CRITICAL: 'pdm-danger' }[level] ?? ''
}
function riskLabel(level) {
  return { NORMAL: '정상', WARNING: '주의', CRITICAL: '위험' }[level] ?? level
}
function alertStatusLabel(s) {
  return { OPEN: '미처리', CHECKING: '확인 중', RESOLVED: '완료' }[s] ?? s
}
function alertStatusClass(s) {
  return { OPEN: 'pdm-badge-warn', CHECKING: 'pdm-badge-info', RESOLVED: 'pdm-badge-ok' }[s] ?? ''
}
</script>

<template>
<section class="pdm-page">

  <!-- 헤더 행 -->
  <section class="title-row">
    <h1>예지보전</h1>
    <p>전·후방 카메라 인식 품질 기반 장비 상태 진단</p>
  </section>

  <!-- KPI 요약 카드 5개 -->
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

  <!-- 카메라 상태 카드 -->
  <section class="pdm-cam-grid">
    <article
      v-for="cam in cameras"
      :key="cam.cameraId"
      class="panel pdm-cam-card"
    >
      <div class="pdm-cam-head">
        <div class="pdm-cam-title">
          <b>{{ cam.cameraCode }}</b>
          <span>{{ cam.cameraName }} · 담당 차로 {{ cam.laneNames?.join(', ') }}</span>
        </div>
        <span class="pdm-risk-badge" :class="riskClass(cam.riskLevel)">{{ riskLabel(cam.riskLevel) }}</span>
      </div>

      <div class="pdm-cam-body">
        <div class="pdm-gauge-wrap">
          <EChartsPanel :option="gaugeOption(cam.healthScore, cam.riskLevel)" :height="130" />
        </div>
        <div class="pdm-cam-metrics">
          <div class="pdm-metric-row">
            <span>OCR 신뢰도</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar pdm-blue" :style="`width:${cam.avgOcrConfidence}%`"></div></div>
            <b>{{ cam.avgOcrConfidence?.toFixed(1) }}%</b>
          </div>
          <div class="pdm-metric-row">
            <span>인식 성공률</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar pdm-blue" :style="`width:${cam.successRate}%`"></div></div>
            <b>{{ cam.successRate?.toFixed(1) }}%</b>
          </div>
          <div class="pdm-metric-row">
            <span>전후방 일치율</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar" :class="riskClass(cam.riskLevel)" :style="`width:${cam.matchRate}%`"></div></div>
            <b>{{ cam.matchRate?.toFixed(1) }}%</b>
          </div>
          <div class="pdm-metric-row">
            <span>미검출률</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar pdm-warn" :style="`width:${(cam.missingRate ?? 0) * 8}%`"></div></div>
            <b>{{ cam.missingRate?.toFixed(1) }}%</b>
          </div>
        </div>
      </div>

      <div class="pdm-cam-reason">
        <p><span>예상 원인</span>{{ cam.reasonText }}</p>
        <p><span>권장 점검</span>{{ cam.recommendedAction }}</p>
      </div>
    </article>
  </section>

  <!-- 품질 추세 + 최근 알림 -->
  <section class="pdm-mid-grid">

    <article class="panel pdm-trend-panel">
      <div class="panel-head">
        <h2>품질 지표 추세</h2>
        <div class="pdm-cam-tabs">
          <button
            v-for="cam in cameras"
            :key="cam.cameraId"
            type="button"
            :class="{ active: selectedCam === cam.cameraId }"
            @click="selectedCam = cam.cameraId"
          >{{ cam.cameraCode }}</button>
        </div>
      </div>
      <EChartsPanel :option="trendOption" :height="220" />
    </article>

    <article class="panel pdm-alert-panel">
      <div class="panel-head">
        <h2>최근 이상 알림</h2>
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
            <span>{{ alert.cameraCode }}{{ alertLaneLabel(alert) ? ' · ' + alertLaneLabel(alert) : '' }}</span>
            <em>{{ alert.reasonText }}</em>
          </div>
          <div class="pdm-alert-meta">
            <span class="pdm-badge" :class="alertStatusClass(alert.status)">{{ alertStatusLabel(alert.status) }}</span>
            <time>{{ formatTime(alert.createdAt) }}</time>
          </div>
        </div>
      </div>
    </article>
  </section>

  <!-- 전후방 비교 결과 테이블 -->
  <article class="panel pdm-compare-panel">
    <div class="panel-head">
      <h2>전후방 비교 결과</h2>
      <small>최근 30분 · {{ compareResults.length }}건</small>
    </div>
    <table class="pdm-compare-table">
      <thead>
        <tr>
          <th>이벤트 그룹</th>
          <th>차로</th>
          <th>전방 OCR</th>
          <th>후방 OCR</th>
          <th>일치</th>
          <th>불일치 유형</th>
          <th>신뢰도 차이</th>
          <th>비교 시각</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in compareResults" :key="row.compareId" :class="{ 'pdm-mismatch-row': !row.isMatched }">
          <td class="pdm-mono">{{ row.eventGroupKey }}</td>
          <td><span class="pdm-lane-chip">{{ row.laneName }}</span></td>
          <td class="pdm-mono">{{ row.frontPlateText ?? '—' }}</td>
          <td class="pdm-mono" :class="{ 'pdm-text-warn': !row.isMatched }">{{ row.rearPlateText ?? '미검출' }}</td>
          <td><span class="pdm-badge" :class="row.isMatched ? 'pdm-badge-ok' : 'pdm-badge-warn'">{{ row.isMatched ? '일치' : '불일치' }}</span></td>
          <td>{{ row.mismatchType ?? '—' }}</td>
          <td>{{ row.confidenceGap != null ? row.confidenceGap.toFixed(2) : '—' }}</td>
          <td>{{ formatDateTime(row.comparedAt) }}</td>
        </tr>
      </tbody>
    </table>
  </article>

</section>
</template>
