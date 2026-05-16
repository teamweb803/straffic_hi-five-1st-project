<script setup>
import { inject } from 'vue'
import ChartJsPanel from '@/components/charts/ChartJsPanel.vue'

const {
  activeMenu,
  centerLabel,
  selectedLaneText,
  selectedLane,
  dashboardKpis,
  dashboardDetections,
  statusCards,
  filteredGpsJudgements,
  fieldAlerts,
  filteredTrafficRows,
  equipmentCards,
  equipmentLaneRows,
  equipmentAlerts,
  historyRows
} = inject('controlDashboardContext')

const tollChartData = {
  labels: ['00', '02', '04', '06', '08', '10', '12', '14', '16', '18', '20', '22', '24'],
  datasets: [
    {
      label: 'IN 입구',
      data: [12, 28, 48, 92, 154, 220, 265, 232, 210, 238, 195, 124, 42],
      backgroundColor: 'rgba(47, 140, 255, 0.82)',
      borderRadius: 4,
      stack: 'toll'
    },
    {
      label: 'OUT 출구',
      data: [7, 18, 32, 56, 84, 110, 126, 92, 86, 98, 76, 48, 18],
      backgroundColor: 'rgba(157, 98, 221, 0.86)',
      borderRadius: 4,
      stack: 'toll'
    }
  ]
}

const tollChartOptions = {
  plugins: {
    tooltip: {
      callbacks: {
        label(context) {
          return `${context.dataset.label}: ${context.parsed.y.toLocaleString()}천원`
        }
      }
    }
  },
  scales: {
    x: { stacked: true },
    y: { stacked: true, ticks: { callback: (value) => `${value}K` } }
  }
}

const settlementDonutData = {
  labels: ['결제 가능', '검수 필요', '보류'],
  datasets: [
    {
      data: [2108, 214, 148],
      backgroundColor: ['#35d36d', '#ffd13f', '#ff625c'],
      borderWidth: 0
    }
  ]
}

const settlementDonutOptions = {
  cutout: '68%',
  plugins: { legend: { display: false } },
  scales: { x: { display: false }, y: { display: false } }
}
</script>

<template>
<section class="settlement-page">
        <section class="event-title-row">
          <h1>정산</h1>
          <p>통행 이벤트 기반 정산 현황을 요약합니다.</p>
        </section>

        <div class="settlement-tabs">
          <button class="active" type="button">금일</button>
          <button type="button">주간</button>
          <button type="button">월간</button>
          <button type="button">사용자 지정 <span class="filter-caret">▣</span></button>
        </div>

        <section class="settlement-kpi-grid">
          <article class="settlement-kpi fee"><i>₩</i><span>총 통행료</span><strong>₩2,450,800</strong><em>전일 대비 ▲ 6.1%</em></article>
          <article class="settlement-kpi card"><i>▰</i><span>결제 가능 건수</span><strong>2,108 <small>건</small></strong><em>전일 대비 ▲5.7%</em></article>
          <article class="settlement-kpi danger"><i>!</i><span>GPS 영역 이탈 건수</span><strong>214 <small>건</small></strong><em>전일 대비 ▼ 5.3%</em></article>
          <article class="settlement-kpi hold"><i>●</i><span>검수 대기 금액</span><strong>₩231,600</strong><em>전일 대비 ▲ 7.9%</em></article>
        </section>

        <section class="settlement-mid-grid">
          <article class="panel toll-chart-panel">
            <div class="panel-head">
              <h2>시간대별 통행료 (금액)</h2>
              <div class="chart-toggle"><button class="active" type="button">금액</button><button type="button">건수</button></div>
            </div>
            <div class="chart-legend"><span class="in">IN 입구</span><span class="out">OUT 출구</span><strong>₩2,450,800<br /><small>합계</small></strong></div>
            <ChartJsPanel type="bar" :data="tollChartData" :options="tollChartOptions" :height="198" />
          </article>

          <article class="panel settlement-donut-panel">
            <div class="panel-head"><h2>정산 상태 요약</h2></div>
            <div class="settlement-donut-wrap">
              <div class="settlement-donut chart-donut">
                <ChartJsPanel type="doughnut" :data="settlementDonutData" :options="settlementDonutOptions" :height="170" />
                <div class="settlement-donut-center"><strong>2,470 <small>건</small></strong><span>총 통행 이벤트</span></div>
              </div>
              <dl>
                <dt class="ok">결제 가능</dt><dd>2,108 건 (85.2%)</dd>
                <dt class="warn">검수 필요</dt><dd>214 건 (8.7%)</dd>
                <dt class="danger">보류</dt><dd>148 건 (6.0%)</dd>
              </dl>
            </div>
          </article>

          <article class="panel gps-impact-panel">
            <div class="panel-head"><h2>GPS 판정 영향 <small>ⓘ</small></h2></div>
            <section class="impact-card ok">
              <header><b>정상 판정 (영역 내 통과)</b><span>정상</span></header>
              <div><p>금액<strong>₩2,108,200</strong></p><p>건수<strong>2,108 건</strong></p><p>비율<strong>85.9%</strong></p></div>
            </section>
            <section class="impact-card danger">
              <header><b>영역 이탈 (검수 필요)</b><span>검수 필요</span></header>
              <div><p>금액<strong>₩231,600</strong></p><p>건수<strong>214 건</strong></p><p>비율<strong>8.4%</strong></p></div>
            </section>
            <p class="nofix-line"><i></i>미송신 / No Fix <span>건수 148 건 (6.0%)</span></p>
          </article>
        </section>

        <article class="panel settlement-table-panel">
          <div class="panel-head">
            <h2>정산 후보 요약 <small>(결제 대상)</small></h2>
            <div><button type="button">⇩ 내보내기 <span class="filter-caret">⌄</span></button><button type="button">⟳ 새로고침</button></div>
          </div>
          <table>
            <thead><tr><th>No.</th><th>차량번호</th><th>방향</th><th>차선</th><th>통과시각</th><th>GPS 판정</th><th>결제 판정</th><th>금액</th><th>상태</th></tr></thead>
            <tbody>
              <tr><td>1</td><td>12가 3456</td><td><span class="event-pill in">IN</span></td><td>2차선</td><td>17:35:42</td><td><span class="event-state ok">정상 (영역 내)</span></td><td><span class="event-state ok">결제 가능</span></td><td>₩1,900</td><td><span class="event-state ok">결제 완료</span></td></tr>
              <tr><td>2</td><td>45나 6721</td><td><span class="event-pill out">OUT</span></td><td>2차선</td><td>17:33:18</td><td><span class="event-state ok">정상 (영역 내)</span></td><td><span class="event-state ok">결제 가능</span></td><td>₩1,900</td><td><span class="event-state warn">대기</span></td></tr>
              <tr><td>3</td><td>67다 9012</td><td><span class="event-pill in">IN</span></td><td>1차선</td><td>17:31:41</td><td><span class="event-state danger">영역 이탈</span></td><td><span class="event-state warn">검수 필요</span></td><td>₩1,900</td><td><span class="event-state warn">검수 대기</span></td></tr>
              <tr><td>4</td><td>34머 1122</td><td><span class="event-pill out">OUT</span></td><td>2차선</td><td>17:26:17</td><td><span class="event-state danger">영역 이탈</span></td><td><span class="event-state warn">검수 필요</span></td><td>₩1,900</td><td><span class="event-state warn">검수 대기</span></td></tr>
              <tr><td>5</td><td>90허 5678</td><td><span class="event-pill in">IN</span></td><td>1차선</td><td>17:19:12</td><td><span class="event-state ok">정상 (영역 내)</span></td><td><span class="event-state ok">결제 가능</span></td><td>₩1,900</td><td><span class="event-state warn">대기</span></td></tr>
              <tr><td>6</td><td>78버 3347</td><td><span class="event-pill out">OUT</span></td><td>2차선</td><td>17:12:22</td><td><span class="event-state muted">No Fix / 미송신</span></td><td><span class="event-state danger">보류</span></td><td>₩1,900</td><td><span class="event-state danger">보류</span></td></tr>
            </tbody>
          </table>
        </article>
      </section>
</template>
