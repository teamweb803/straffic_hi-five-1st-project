<script setup>
import { ref, computed } from 'vue'
import EChartsPanel from '@/components/charts/EChartsPanel.vue'

// ── 정적 목업 데이터 ────────────────────────────────────────────
const summary = {
  totalCameraCount: 2,
  normalCameraCount: 1,
  warningCameraCount: 1,
  criticalCameraCount: 0,
  averageHealthScore: 82.0
}

const cameras = [
  {
    cameraId: 1,
    cameraCode: 'CAM-F-01',
    cameraName: '전방 카메라',
    direction: 'FRONT',
    laneNames: ['1차로', '2차로'],
    healthScore: 91.0,
    riskLevel: 'NORMAL',
    avgOcrConfidence: 94.2,
    successRate: 96.8,
    missingRate: 1.2,
    matchRate: 94.1,
    mismatchRate: 2.4,
    reasonText: '정상 운영 중',
    recommendedAction: '정기 점검 유지'
  },
  {
    cameraId: 2,
    cameraCode: 'CAM-R-01',
    cameraName: '후방 카메라',
    direction: 'REAR',
    laneNames: ['1차로', '2차로'],
    healthScore: 68.0,
    riskLevel: 'WARNING',
    avgOcrConfidence: 72.0,
    successRate: 81.0,
    missingRate: 6.5,
    matchRate: 76.0,
    mismatchRate: 8.3,
    reasonText: '후방 카메라 OCR 신뢰도 저하',
    recommendedAction: '렌즈 청소 및 초점 상태 확인'
  }
]

const trendLabels = ['14:00', '14:05', '14:10', '14:15', '14:20', '14:25', '14:30']

const trends = {
  1: {
    healthScore: [92, 93, 91, 92, 91, 90, 91],
    ocrConf:     [94.5, 94.8, 94.2, 95.0, 94.3, 94.1, 94.2],
    matchRate:   [94.0, 95.1, 93.8, 94.6, 94.2, 93.9, 94.1]
  },
  2: {
    healthScore: [78, 74, 71, 68, 68, 67, 68],
    ocrConf:     [80.1, 77.4, 74.8, 72.5, 72.3, 71.8, 72.0],
    matchRate:   [83.2, 80.1, 78.4, 76.8, 76.3, 75.9, 76.0]
  }
}

const alerts = [
  { alertId: 1, cameraCode: 'CAM-R-01', laneNames: ['1차로', '2차로'], riskLevel: 'WARNING',  title: 'OCR 신뢰도 연속 하락',     reasonText: '렌즈 오염 의심',    recommendedAction: '렌즈 청소',    status: 'OPEN',     occurredAt: '14:28' },
  { alertId: 2, cameraCode: 'CAM-R-01', laneNames: ['1차로', '2차로'], riskLevel: 'WARNING',  title: '전후방 일치율 임계값 미달', reasonText: '카메라 정렬 이상',  recommendedAction: '각도 재조정', status: 'CHECKING', occurredAt: '14:15' },
  { alertId: 3, cameraCode: 'CAM-F-01', laneNames: ['1차로', '2차로'], riskLevel: 'NORMAL',   title: '인식 성공률 소폭 저하',    reasonText: '조명 환경 변화',    recommendedAction: '모니터링 유지', status: 'RESOLVED', occurredAt: '13:42' }
]

const compareResults = [
  { groupKey: 'GRP-0001', laneId: 1, laneName: '1차로', frontPlate: '123가4567', rearPlate: '123가4567', isMatched: true,  mismatchType: null,           confGap: 0.02, comparedAt: '14:28:20' },
  { groupKey: 'GRP-0002', laneId: 2, laneName: '2차로', frontPlate: '456나8901', rearPlate: '456나8901', isMatched: true,  mismatchType: null,           confGap: 0.01, comparedAt: '14:28:15' },
  { groupKey: 'GRP-0003', laneId: 1, laneName: '1차로', frontPlate: '789다2345', rearPlate: '789가2345', isMatched: false, mismatchType: 'CHAR_DIFF',    confGap: 0.18, comparedAt: '14:27:58' },
  { groupKey: 'GRP-0004', laneId: 2, laneName: '2차로', frontPlate: '012라6789', rearPlate: null,        isMatched: false, mismatchType: 'REAR_MISSING', confGap: null, comparedAt: '14:27:44' },
  { groupKey: 'GRP-0005', laneId: 1, laneName: '1차로', frontPlate: '345마0123', rearPlate: '345마0123', isMatched: true,  mismatchType: null,           confGap: 0.03, comparedAt: '14:27:30' }
]

// ── 차트 탭 상태 ────────────────────────────────────────────────
const selectedCam = ref(1)

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

// 품질 추세 라인 차트
const trendOption = computed(() => {
  const d = trends[selectedCam.value]
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
      data: trendLabels,
      axisLine: { lineStyle: { color: EC.gridLine } },
      axisTick: { show: false },
      axisLabel: { color: EC.textMuted, fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      min: 60, max: 100,
      splitLine: { lineStyle: { color: EC.gridLine } },
      axisLabel: { color: EC.textMuted, fontSize: 11 }
    },
    series: [
      {
        name: 'Health Score',
        type: 'line', smooth: true,
        data: d.healthScore,
        lineStyle: { color: EC.green, width: 2 },
        itemStyle: { color: EC.green },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(76,223,102,.22)' }, { offset: 1, color: 'rgba(76,223,102,.02)' }] } },
        symbol: 'circle', symbolSize: 5
      },
      {
        name: 'OCR 신뢰도(%)',
        type: 'line', smooth: true,
        data: d.ocrConf,
        lineStyle: { color: EC.blue, width: 2 },
        itemStyle: { color: EC.blue },
        symbol: 'circle', symbolSize: 5
      },
      {
        name: '전후방 일치율(%)',
        type: 'line', smooth: true,
        data: d.matchRate,
        lineStyle: { color: EC.amber, width: 2 },
        itemStyle: { color: EC.amber },
        symbol: 'circle', symbolSize: 5
      }
    ]
  }
})

// 게이지 차트 (카메라별 Health Score)
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
        fontSize: 26,
        fontWeight: 800,
        color,
        formatter: '{value}'
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
      <!-- 카드 헤더 -->
      <div class="pdm-cam-head">
        <div class="pdm-cam-title">
          <b>{{ cam.cameraCode }}</b>
          <span>{{ cam.cameraName }} · 담당 차로 {{ cam.laneNames.join(', ') }}</span>
        </div>
        <span class="pdm-risk-badge" :class="riskClass(cam.riskLevel)">{{ riskLabel(cam.riskLevel) }}</span>
      </div>

      <div class="pdm-cam-body">
        <!-- 게이지 -->
        <div class="pdm-gauge-wrap">
          <EChartsPanel :option="gaugeOption(cam.healthScore, cam.riskLevel)" :height="130" />
        </div>

        <!-- 지표 목록 -->
        <div class="pdm-cam-metrics">
          <div class="pdm-metric-row">
            <span>OCR 신뢰도</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar pdm-blue" :style="`width:${cam.avgOcrConfidence}%`"></div></div>
            <b>{{ cam.avgOcrConfidence }}%</b>
          </div>
          <div class="pdm-metric-row">
            <span>인식 성공률</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar pdm-blue" :style="`width:${cam.successRate}%`"></div></div>
            <b>{{ cam.successRate }}%</b>
          </div>
          <div class="pdm-metric-row">
            <span>전후방 일치율</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar" :class="riskClass(cam.riskLevel)" :style="`width:${cam.matchRate}%`"></div></div>
            <b>{{ cam.matchRate }}%</b>
          </div>
          <div class="pdm-metric-row">
            <span>미검출률</span>
            <div class="pdm-mini-bar-wrap"><div class="pdm-mini-bar pdm-warn" :style="`width:${cam.missingRate * 8}%`"></div></div>
            <b>{{ cam.missingRate }}%</b>
          </div>
        </div>
      </div>

      <!-- 권장 조치 -->
      <div class="pdm-cam-reason">
        <p><span>예상 원인</span>{{ cam.reasonText }}</p>
        <p><span>권장 점검</span>{{ cam.recommendedAction }}</p>
      </div>
    </article>
  </section>

  <!-- 품질 추세 + 최근 알림 -->
  <section class="pdm-mid-grid">

    <!-- 품질 추세 차트 -->
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

    <!-- 최근 이상 알림 -->
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
            <b>{{ alert.title }}</b>
            <span>{{ alert.cameraCode }} · {{ alert.laneNames.join(', ') }}</span>
            <em>{{ alert.reasonText }}</em>
          </div>
          <div class="pdm-alert-meta">
            <span class="pdm-badge" :class="alertStatusClass(alert.status)">{{ alertStatusLabel(alert.status) }}</span>
            <time>{{ alert.occurredAt }}</time>
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
        <tr v-for="row in compareResults" :key="row.groupKey" :class="{ 'pdm-mismatch-row': !row.isMatched }">
          <td class="pdm-mono">{{ row.groupKey }}</td>
          <td><span class="pdm-lane-chip">{{ row.laneName }}</span></td>
          <td class="pdm-mono">{{ row.frontPlate ?? '—' }}</td>
          <td class="pdm-mono" :class="{ 'pdm-text-warn': !row.isMatched }">{{ row.rearPlate ?? '미검출' }}</td>
          <td><span class="pdm-badge" :class="row.isMatched ? 'pdm-badge-ok' : 'pdm-badge-warn'">{{ row.isMatched ? '일치' : '불일치' }}</span></td>
          <td>{{ row.mismatchType ?? '—' }}</td>
          <td>{{ row.confGap != null ? row.confGap.toFixed(2) : '—' }}</td>
          <td>{{ row.comparedAt }}</td>
        </tr>
      </tbody>
    </table>
  </article>

</section>
</template>
