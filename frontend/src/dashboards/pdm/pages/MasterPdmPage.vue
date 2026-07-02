<script setup>
import { ref, computed, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { pdmApi, pdmFastApi } from '@/api/pdm'

const PDM_REFRESH_MS = 10 * 1000
let refreshTimer = null

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
const chartReady = ref(false)
const barChartHeight = 320
const demoMode = ref(false)
const demoModeBusy = ref(false)
const demoMailBusy = ref(false)
const demoMsg = ref('')
const errorMsg = ref('')

// ── 데이터 로딩 ────────────────────────────────────────────────
async function loadData({ silent = false } = {}) {
  if (!silent) {
    loading.value = true
    chartReady.value = false
  }
  try {
    const [summaryRes, camerasRes, alertsRes] = await Promise.all([
      pdmApi.getDashboardSummary(),
      pdmApi.getCameras(),
      pdmApi.getAlerts({ status: 'CREATED' }),
    ])
    summary.value = summaryRes.data
    cameras.value = camerasRes.data
    alerts.value = alertsRes.data.filter(alert => normalizeStatus(alert.status) !== 'RESOLVED')
    errorMsg.value = ''
    if (!silent || !chartReady.value) {
      nextTick(() => {
        requestAnimationFrame(() => { chartReady.value = true })
      })
    }
  } catch (e) {
    console.error('[PDM Master] 데이터 로딩 실패', e)
    errorMsg.value = '예지보전 데이터를 불러오지 못했습니다. 백엔드 연결을 확인하세요.'
  } finally {
    if (!silent) loading.value = false
  }
}

function refreshPdmPage() {
  loadData({ silent: true })
  loadFastApiStatus()
}

onMounted(() => {
  loadDemoMode()
  loadData()
  loadFastApiStatus()
  refreshTimer = window.setInterval(refreshPdmPage, PDM_REFRESH_MS)
})

// ── 시각 포맷 ──────────────────────────────────────────────────
function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function schedulerLabel(status) {
  if (!status) return '연결 안 됨'
  if (status.job?.running) return '분석 실행 중'
  return status.schedulerRunning ? '자동 실행 중' : '수동 대기'
}

function formatInterval(seconds) {
  const s = Number(seconds)
  if (!Number.isFinite(s)) return '—'
  return s % 60 === 0 ? `${s / 60}분` : `${s}초`
}

function formatTargets(targets) {
  if (!targets) return '—'
  const pairs = String(targets).split(',').map(p => p.trim()).filter(Boolean)
  if (!pairs.length) return '—'
  const cameras = new Set(pairs.map(p => p.split(':')[0]))
  return `카메라 ${cameras.size}대 · 분석 대상 ${pairs.length}개`
}

function normalizeRisk(level) {
  return { HIGH: 'CRITICAL' }[level] ?? level
}

function normalizeStatus(status) {
  return {
    CREATED: 'OPEN',
    FALSE_ALARM: 'RESOLVED',
  }[status] ?? status
}

function messageLabel(text) {
  return {
    'Recognition quality is stable': '인식 품질 안정',
    'No immediate maintenance required': '즉시 점검 불필요',
    'Temporary mismatch spike detected': '일시적 전후방 불일치 증가',
    'Rear camera OCR sudden drop detected': '후방 카메라 OCR 급락 감지',
    'Check recent camera frame delay and lens contamination': '최근 프레임 지연 및 렌즈 오염 확인',
    'Event count is too low for reliable sequence analysis': '이벤트 수 부족으로 시계열 분석 신뢰도 낮음',
    'Check camera capture pipeline and event forwarding': '카메라 캡처/이벤트 전달 경로 확인',
    'Long-term degradation trend detected': '장기 품질 저하 추세 감지',
    'Short repeated quality drop detected': '단기 반복 품질 저하 감지',
    'Legacy API save verification': '기존 API 저장 검증 알림',
    'Inspect mounting vibration and focus state': '거치대 진동 및 초점 상태 점검',
    'Schedule camera inspection and lens replacement check': '카메라 점검 일정 등록 및 렌즈 교체 여부 확인',
  }[text] ?? text
}

function alertTitleLabel(title) {
  return {
    'Front Camera Low Count WARNING alert': '전방 카메라 이벤트 부족 주의',
    'Front Camera Low Count CRITICAL alert': '전방 카메라 이벤트 부족 위험',
    'Rear Camera Spike WARNING alert': '후방 카메라 일시 품질 저하 주의',
    'Rear Camera Spike CRITICAL alert': '후방 카메라 OCR 급락 위험',
    'Rear Camera Degrade WARNING alert': '후방 카메라 장기 품질 저하 주의',
    'Rear Camera Degrade CRITICAL alert': '후방 카메라 장기 품질 저하 위험',
    'Front Camera Pattern WARNING alert': '전방 카메라 반복 품질 저하 주의',
    'Front Camera Pattern CRITICAL alert': '전방 카메라 반복 품질 저하 위험',
    'Front Camera Legacy CRITICAL alert': '전방 카메라 기존 검증 알림',
    'PDM Demo Mail Test WARNING alert': '메일 테스트 이상 알림',
  }[title] ?? title
}

function alertLaneLabel(alert) {
  if (alert.laneId == null) return ''
  const cam = cameras.value.find(c => c.cameraId === alert.cameraId)
  if (!cam) return `${alert.laneId}차로`
  const idx = cam.laneIds?.indexOf(alert.laneId) ?? -1
  return idx >= 0 && cam.laneNames?.[idx] ? cam.laneNames[idx] : `${alert.laneId}차로`
}

// ── 카메라별 미처리 알림 수 ────────────────────────────────────
function alertCountFor(cameraId) {
  return alerts.value.filter(a => a.cameraId === cameraId && normalizeStatus(a.status) !== 'RESOLVED').length
}

// ── 헬퍼 ──────────────────────────────────────────────────────
function scorePercent(score) {
  const number = Number(score ?? 0)
  if (!Number.isFinite(number)) return 0
  return Math.min(100, Math.max(0, number))
}

function animatedScore(score) {
  return chartReady.value ? scorePercent(score) : 0
}

function riskClass(level) {
  return { NORMAL: 'pdm-ok', WARNING: 'pdm-warn', CRITICAL: 'pdm-danger' }[normalizeRisk(level)] ?? ''
}
function csClass(level) {
  return { NORMAL: 'ok', WARNING: 'warn', CRITICAL: 'danger' }[normalizeRisk(level)] ?? ''
}
function riskLabel(level) {
  return { NORMAL: '정상', WARNING: '주의', CRITICAL: '위험' }[normalizeRisk(level)] ?? level
}
function directionLabel(d) {
  return { FRONT: '전방', REAR: '후방' }[d] ?? d
}
function statusLabel(s) {
  return { OPEN: '미처리', CHECKING: '확인 중', RESOLVED: '완료' }[normalizeStatus(s)] ?? s
}
function statusClass(s) {
  return { OPEN: 'pdm-badge-warn', CHECKING: 'pdm-badge-info', RESOLVED: 'pdm-badge-ok' }[normalizeStatus(s)] ?? ''
}

// ── 필터 ──────────────────────────────────────────────────────
const filterLevel = ref('ALL')
const filteredCameras = computed(() => {
  if (filterLevel.value === 'ALL') return cameras.value
  return cameras.value.filter(c => normalizeRisk(c.riskLevel) === filterLevel.value)
})

// ── FastAPI 분석 서버 상태 ─────────────────────────────────────
const fastApiStatus = ref(null)
const fastApiRunning = ref(false)
const fastApiMsg = ref('')

async function loadFastApiStatus() {
  try {
    const res = await pdmFastApi.getStatus()
    fastApiStatus.value = res.data
  } catch {
    fastApiStatus.value = null
  }
}

async function loadDemoMode() {
  try {
    const res = await pdmApi.getDemoMode()
    demoMode.value = Boolean(res.data?.enabled)
  } catch (e) {
    console.warn('[PDM Master] 데모 모드 상태 조회 실패', e)
  }
}

async function toggleDemoMode() {
  if (demoModeBusy.value) return
  demoModeBusy.value = true
  demoMsg.value = ''
  try {
    const res = await pdmApi.setDemoMode(!demoMode.value)
    demoMode.value = Boolean(res.data?.enabled)
    demoMsg.value = demoMode.value ? '데모 고정값 ON' : '데모 고정값 OFF'
    await loadData({ silent: true })
    setTimeout(() => { demoMsg.value = '' }, 3000)
  } catch {
    demoMsg.value = '시연 모드 변경 실패'
  } finally {
    demoModeBusy.value = false
  }
}

async function sendDemoMailAlert() {
  if (demoMailBusy.value) return
  demoMailBusy.value = true
  demoMsg.value = ''
  try {
    const res = await pdmApi.sendDemoMailAlert()
    demoMsg.value = res.data?.message ?? '메일 테스트 알림 요청 완료'
    await loadData({ silent: true })
    setTimeout(() => { demoMsg.value = '' }, 4000)
  } catch {
    demoMsg.value = '메일 테스트 알림 실패'
  } finally {
    demoMailBusy.value = false
  }
}

function refreshAfterAnalysisStart() {
  ;[1000, 15000, 55000].forEach(delay => {
    setTimeout(() => {
      loadFastApiStatus()
      loadData()
    }, delay)
  })
}

async function triggerAnalysis() {
  if (fastApiRunning.value) return
  fastApiRunning.value = true
  fastApiMsg.value = ''
  try {
    const res = await pdmFastApi.runDemoRefresh()
    fastApiMsg.value = res.data?.message ?? '분석이 백그라운드에서 시작되었습니다.'
    loadFastApiStatus()
    loadData()
    refreshAfterAnalysisStart()
    setTimeout(() => { fastApiMsg.value = '' }, 4000)
  } catch {
    fastApiMsg.value = '분석 서버에 연결할 수 없습니다. (FastAPI 실행 여부 확인)'
    setTimeout(() => { fastApiMsg.value = '' }, 5000)
  } finally {
    fastApiRunning.value = false
  }
}

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
<section class="pdm-page">

  <!-- 헤더 -->
  <section class="title-row">
    <h1>예지보전 현황</h1>
    <p>전체 카메라 인식 품질 기반 장비 이상 조기 탐지 집계</p>
  </section>

  <article class="panel pdm-demo-toolbar">
    <div>
      <b>데모 고정값</b>
      <span>{{ demoMode ? 'ON · 고정 시나리오 응답' : 'OFF · 실시간 분석 응답' }}</span>
    </div>
    <div class="pdm-demo-actions">
      <button
        type="button"
        class="pdm-action-button"
        :class="{ active: demoMode }"
        :disabled="demoModeBusy"
        @click="toggleDemoMode"
      >
        {{ demoModeBusy ? '전환 중...' : (demoMode ? '실시간으로 전환' : '데모 고정값 켜기') }}
      </button>
      <button
        type="button"
        class="pdm-action-button"
        :disabled="demoMailBusy"
        @click="sendDemoMailAlert"
      >
        {{ demoMailBusy ? '발송 확인 중...' : '메일 테스트 알림' }}
      </button>
      <small v-if="demoMsg">{{ demoMsg }}</small>
    </div>
  </article>

  <div v-if="errorMsg" class="pdm-state-banner">{{ errorMsg }}</div>

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
      <span>평균 인식 품질 점수</span>
      <strong>{{ summary.averageHealthScore }}<small>점</small></strong>
      <div class="pdm-score-track">
        <div class="pdm-score-fill" :style="`width:${animatedScore(summary.averageHealthScore)}%`"></div>
      </div>
    </article>
  </section>

  <!-- 차트 + 알림 -->
  <section class="pdm-mid-grid">

    <!-- 카메라별 인식 품질 점수 막대 차트 -->
    <article class="panel pdm-trend-panel pdm-trend-panel--fill">
      <div class="panel-head">
        <h2>카메라별 인식 품질 점수</h2>
        <small>정상(녹) / 주의(황) / 위험(적)</small>
      </div>
      <div class="pdm-score-bars">
        <div
          v-for="cam in cameras"
          :key="cam.cameraId"
          class="pdm-score-bar-row"
        >
          <b>{{ cam.cameraCode }}</b>
          <div class="pdm-score-bar-track">
            <div
              class="pdm-score-bar-fill"
              :class="riskClass(cam.riskLevel)"
              :style="`width:${animatedScore(cam.healthScore)}%`"
            ></div>
          </div>
          <strong :class="riskClass(cam.riskLevel)">{{ cam.healthScore }}</strong>
        </div>
        <div v-if="cameras.length === 0 && !loading && !errorMsg" class="pdm-score-empty">데이터 없음</div>
      </div>
    </article>

    <!-- 전체 알림 -->
    <article class="panel pdm-alert-panel">
      <div class="panel-head">
        <h2>이상 알림</h2>
        <span class="pdm-count-chip">{{ alerts.length }}</span>
      </div>
      <div class="pdm-alert-list pdm-alert-list--scroll" :style="`max-height:${barChartHeight}px`">
        <div
          v-for="alert in alerts"
          :key="alert.alertId"
          class="pdm-alert-row"
        >
          <div class="pdm-alert-dot" :class="riskClass(alert.riskLevel)"></div>
          <div class="pdm-alert-body">
            <b>{{ alertTitleLabel(alert.alertTitle) }}</b>
            <span>{{ alert.cameraCode }}{{ alertLaneLabel(alert) ? ' · ' + alertLaneLabel(alert) : '' }}</span>
            <em>{{ messageLabel(alert.reasonText) }}</em>
          </div>
          <div class="pdm-alert-meta">
            <span class="pdm-badge" :class="statusClass(alert.status)">{{ statusLabel(alert.status) }}</span>
            <time>{{ formatTime(alert.createdAt) }}</time>
          </div>
        </div>
        <div v-if="alerts.length === 0 && !loading && !errorMsg" class="pdm-alert-row">
          <div class="pdm-alert-dot pdm-ok"></div>
          <div class="pdm-alert-body"><b>이상 알림 없음</b><span>모든 카메라 정상 운영 중</span></div>
        </div>
      </div>
    </article>
  </section>

  <!-- 카메라 현황 테이블 -->
  <article class="company-admin-panel">
    <div class="company-panel-head">
      <h3>카메라 상태 현황 <small>카메라별 인식 품질 점수 및 알림</small></h3>
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
          <th>인식 품질 점수</th>
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
          <td colspan="7" class="pdm-empty-cell">데이터 없음</td>
        </tr>
      </tbody>
    </table>
  </article>

  <!-- FastAPI 분석 서버 패널 -->
  <article class="company-admin-panel">
    <div class="company-panel-head">
      <h3>PDM 분석 서버 <small>FastAPI — 모델별 이상 탐지 스케줄러</small></h3>
      <button
        type="button"
        class="pdm-action-button"
        :disabled="fastApiRunning"
        @click="triggerAnalysis"
      >
        {{ fastApiRunning ? '실행 중...' : '수동 분석 실행' }}
      </button>
    </div>
    <div v-if="fastApiMsg" class="pdm-server-message">{{ fastApiMsg }}</div>
    <div v-if="fastApiStatus" class="pdm-server-status">
      스케줄러: <b>{{ schedulerLabel(fastApiStatus) }}</b>
      <span v-if="fastApiStatus.nextRunAt"> · 다음 실행 {{ formatTime(fastApiStatus.nextRunAt) }}</span>
      <span v-if="fastApiStatus.job?.lastSummary"> · 최근 저장 {{ fastApiStatus.job.lastSummary.savedCount }}건</span>
    </div>
    <div v-if="fastApiStatus" class="pdm-server-grid">
      <div class="pdm-server-card">
        <div class="pdm-server-card-label">분석 주기</div>
        <div class="pdm-server-card-value">{{ formatInterval(fastApiStatus.intervalSeconds) }}</div>
      </div>
      <div class="pdm-server-card">
        <div class="pdm-server-card-label">분석 창</div>
        <div class="pdm-server-card-value">{{ fastApiStatus.analysisWindowMinutes }}분</div>
      </div>
      <div class="pdm-server-card">
        <div class="pdm-server-card-label">버킷 크기</div>
        <div class="pdm-server-card-value">{{ fastApiStatus.bucketMinutes }}분</div>
      </div>
      <div class="pdm-server-card">
        <div class="pdm-server-card-label">분석 대상</div>
        <div class="pdm-server-card-value pdm-server-targets">{{ formatTargets(fastApiStatus.targets) }}</div>
      </div>
    </div>
    <div v-else class="pdm-server-empty">
      분석 서버에 연결되지 않았습니다. FastAPI 서버가 실행 중인지 확인하세요.
    </div>
  </article>

</section>
</template>
