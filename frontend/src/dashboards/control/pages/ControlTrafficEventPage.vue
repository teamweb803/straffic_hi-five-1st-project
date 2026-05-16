<script setup>
import { inject } from 'vue'

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
</script>

<template>
<section class="traffic-event-page">
        <section class="event-title-row">
          <h1>통행 이벤트</h1>
          <p>통행 기록과 현장 이벤트를 조회하고 검수/처리할 수 있습니다.</p>
        </section>

        <section class="event-filter-row">
          <label class="date-range"><span>기간</span><b>2025-05-11 00:00 ~ 2025-05-11 23:59</b><i>▣</i></label>
          <button class="filter-toggle" type="button">차선 <b>전체</b></button>
          <button class="filter-toggle" type="button">방향 <b>전체</b></button>
          <button class="filter-toggle" type="button">GPS 판정 <b>전체</b></button>
          <label class="event-search"><input type="search" placeholder="차량번호 검색" /><span>⌕</span></label>
          <button class="reset-filter" type="button">필터 초기화</button>
        </section>

        <section class="event-main-grid">
          <article class="panel event-list-panel">
            <table class="event-table">
              <thead>
                <tr><th>No.</th><th>차량번호</th><th>차선</th><th>방향</th><th>통과시각</th><th>GPS 판정</th><th>결제 판정</th><th>현장 이벤트</th><th>증빙</th></tr>
              </thead>
              <tbody>
                <tr class="selected"><td>1</td><td>12가 3456</td><td>2차선</td><td><span class="event-pill out">OUT</span></td><td>17:35:42.289</td><td><span class="event-state ok">정상</span></td><td><span class="event-state ok">결제 가능</span></td><td>-</td><td><button>이미지 있음</button></td></tr>
                <tr><td>2</td><td>45나 6721</td><td>2차선</td><td><span class="event-pill in">IN</span></td><td>17:33:18.102</td><td><span class="event-state ok">정상</span></td><td><span class="event-state ok">결제 가능</span></td><td>-</td><td>이미지 없음</td></tr>
                <tr><td>3</td><td>67다 9012</td><td>1차선</td><td><span class="event-pill out">OUT</span></td><td>17:31:41.552</td><td><span class="event-state ok">정상</span></td><td><span class="event-state warn">검수 필요</span></td><td><span class="event-state warn">차선 경계</span></td><td><button>이미지 있음</button></td></tr>
                <tr><td>4</td><td>98머 3344</td><td>2차선</td><td><span class="event-pill in">IN</span></td><td>17:28:55.873</td><td><span class="event-state ok">정상</span></td><td><span class="event-state warn">검수 필요</span></td><td><span class="event-state danger">정차 의심</span></td><td><button>이미지 있음</button></td></tr>
                <tr><td>5</td><td>34다 1122</td><td>2차선</td><td><span class="event-pill out">OUT</span></td><td>17:26:17.430</td><td><span class="event-state danger">영역 이탈</span></td><td><span class="event-state danger">결제 불가</span></td><td>-</td><td><button>이미지 있음</button></td></tr>
                <tr><td>6</td><td>56라 7788</td><td>1차선</td><td><span class="event-pill in">IN</span></td><td>17:23:50.219</td><td><span class="event-state ok">정상</span></td><td><span class="event-state ok">결제 가능</span></td><td>-</td><td>이미지 없음</td></tr>
                <tr><td>7</td><td>12바 1234</td><td>2차선</td><td><span class="event-pill out">OUT</span></td><td>17:21:38.901</td><td><span class="event-state ok">정상</span></td><td><span class="event-state warn">검수 필요</span></td><td><span class="event-state danger">기준 구역 외</span></td><td><button>이미지 있음</button></td></tr>
                <tr><td>8</td><td>90허 5678</td><td>1차선</td><td><span class="event-pill in">IN</span></td><td>17:19:12.654</td><td><span class="event-state ok">정상</span></td><td><span class="event-state ok">결제 가능</span></td><td>-</td><td>이미지 없음</td></tr>
                <tr><td>9</td><td>22거 4567</td><td>2차선</td><td><span class="event-pill in">IN</span></td><td>17:17:05.338</td><td><span class="event-state ok">정상</span></td><td><span class="event-state ok">결제 가능</span></td><td>-</td><td>이미지 없음</td></tr>
                <tr><td>10</td><td>11서 2233</td><td>1차선</td><td><span class="event-pill out">OUT</span></td><td>17:14:46.072</td><td><span class="event-state danger">영역 이탈</span></td><td><span class="event-state danger">결제 불가</span></td><td>-</td><td><button>이미지 있음</button></td></tr>
              </tbody>
            </table>
            <footer class="event-pagination">
              <span>전체 1,248건</span>
              <div><button>‹</button><button class="active">1</button><button>2</button><button>3</button><button>4</button><button>5</button><button>…</button><button>125</button><button>›</button></div>
              <button class="filter-toggle">10개씩 보기</button>
            </footer>
          </article>

          <article class="panel event-detail-panel">
            <div class="event-detail-head"><h2>선택 이벤트 상세</h2><span class="event-state danger">정차 의심</span></div>
            <section class="event-detail-top">
              <dl>
                <dt>차량번호</dt><dd>12가 3456</dd>
                <dt>차선</dt><dd>2차선</dd>
                <dt>방향</dt><dd>OUT (출구)</dd>
                <dt>통과시각</dt><dd>2025-05-11 17:35:42.289</dd>
              </dl>
              <div class="plate-crop"><span>번호판 crop</span><strong>12가 3456</strong></div>
              <div class="event-image"><span>이벤트 이미지</span><div class="event-road-shot"><div class="event-car"><b>12가 3456</b></div></div></div>
            </section>

            <section class="gps-judge-card">
              <div class="event-detail-head"><h2>GPS 결제 영역 판정</h2><span class="event-state ok">정상 (영역 안)</span></div>
              <div class="gps-judge-body">
                <div class="gps-legend"><span class="zone">유효 통행 구역</span><span class="point">현재 GPS 위치</span><span class="lane">A 통행 차선(예시)</span></div>
                <div class="gps-map-mini"><i></i><b></b><em>A</em></div>
                <dl>
                  <dt>위도 (LAT)</dt><dd>37.491032</dd>
                  <dt>경도 (LNG)</dt><dd>126.725124</dd>
                  <dt>속도 (km/h)</dt><dd>58.6</dd>
                  <dt>방향각 (°)</dt><dd>185° (S)</dd>
                  <dt>GPS 판정</dt><dd><span class="event-state ok">정상</span></dd>
                  <dt>결제 판정</dt><dd><span class="event-state ok">결제 가능</span></dd>
                </dl>
              </div>
            </section>

            <footer class="event-detail-actions">
              <button type="button">▧ 증빙 이미지 보기</button>
              <button type="button">⌖ GPS 판정 확인</button>
              <button type="button" class="review">♙ 검수 요청</button>
            </footer>
          </article>
        </section>

        <article class="panel event-history-panel">
          <div class="panel-head"><h2>선택 이벤트 처리 내역 <small>(12가 3456)</small></h2></div>
          <table>
            <thead><tr><th>순번</th><th>처리시각</th><th>처리자</th><th>처리구분</th><th>내용</th><th>결과</th></tr></thead>
            <tbody>
              <tr><td>1</td><td>2025-05-11 17:36:02</td><td>operator01</td><td>자동 판정</td><td>GPS 영역 판정: 정상, 결제 판정: 결제 가능</td><td><span class="event-state ok">완료</span></td></tr>
              <tr><td>2</td><td>2025-05-11 17:36:12</td><td>operator01</td><td>검수 요청</td><td>정차 의심 이벤트 - 현장 확인 요청</td><td><span class="event-state warn">요청 중</span></td></tr>
              <tr><td>3</td><td>2025-05-11 17:36:28</td><td>operator02</td><td>현장 확인 결과</td><td>현장 확인 결과: 이상 없음</td><td><span class="event-state ok">완료</span></td></tr>
              <tr><td>4</td><td>2025-05-11 17:36:45</td><td>operator01</td><td>검수 완료</td><td>검수 완료 처리</td><td><span class="event-state ok">완료</span></td></tr>
            </tbody>
          </table>
        </article>
      </section>
</template>
