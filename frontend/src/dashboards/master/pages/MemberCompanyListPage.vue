<script setup>
import { inject } from 'vue'
import ChartJsPanel from '@/components/charts/ChartJsPanel.vue'

const masterDashboard = inject('masterDashboard')
if (!masterDashboard) {
  throw new Error('masterDashboard context is not provided')
}

const {
  MAP_MARKER_STORAGE_KEY,
  THEME_STORAGE_KEY,
  actionText,
  activateMenu,
  activeMenu,
  activeTab,
  applyMapMarkerPositions,
  assignDashboard,
  auditRows,
  auth,
  cancelMapEditMode,
  center,
  centerDetailMeta,
  centerIssueCount,
  centerMetricChartData,
  centerMetricChartLabels,
  centerMetricChartOptions,
  centerMetricChartValues,
  centerMetricPeriod,
  centerOwner,
  centerSection,
  centers,
  chartGridColor,
  chartTextColor,
  compactLineOptions,
  companies,
  companyByCenter,
  companyForm,
  companyModalMessage,
  companyPermissionChartData,
  companyPermissionChartOptions,
  companySection,
  createCompany,
  createMapMarkerSnapshot,
  dashboardSparklines,
  descriptions,
  deviceRows,
  displayCompanies,
  doughnutOptions,
  draggingCenterName,
  draggingLabelName,
  dummyCompanies,
  edgeFleetDoughnutData,
  edgeMetricCharts,
  editAccount,
  enterCenter,
  enterCompactCenter,
  expandCenterMetricValues,
  expandedCenter,
  exportAuditLog,
  exportSettlementReport,
  fetchCompanies,
  fetchMembers,
  filteredCompanies,
  filteredMembers,
  heartbeatData,
  incidentTimelineData,
  incidentTimelineOptions,
  ingressCharts,
  isLightMode,
  isMapEditMode,
  keyword,
  kpiSection,
  lineData,
  loadMapMarkerPositions,
  logout,
  mapChangeCount,
  mapEditSnapshot,
  mapPositionDirty,
  mapSection,
  mapStage,
  markMapDirty,
  markerPositions,
  markerX,
  markerY,
  memberMessage,
  members,
  menuGroups,
  meta,
  metric,
  multiLineData,
  nextLabelX,
  nextLabelY,
  nextX,
  nextY,
  noticeSection,
  notices,
  notifyCompanyEdited,
  notifyPermissionSaved,
  now,
  nowText,
  openCenterAdd,
  openCompanyModal,
  openDeviceRegister,
  openNoticeCreate,
  openQuickCompanyAdd,
  openSystemNotice,
  pad,
  pointerX,
  pointerY,
  recentAlerts,
  recentAuditRows,
  recentIssueByCenter,
  rect,
  resetAccount,
  resetMapEditPositions,
  router,
  saveMapMarkerPositions,
  saveMasterSettings,
  saved,
  savingCompany,
  search,
  selectedCenter,
  selectedCenterDetail,
  showActionMessage,
  showCenterModal,
  showCompanyModal,
  showDeviceDetail,
  showMoreNotices,
  source,
  sparklineOptions,
  startLabelDrag,
  startMarkerDrag,
  status,
  statusClass,
  statusText,
  stopMarkerDrag,
  subpageDescription,
  subpageTitle,
  sum,
  themeMode,
  toggleAccountLock,
  toggleCenterDetail,
  toggleMapEditMode,
  toggleThemeMode,
  topCenters,
  updateLabelPosition,
  updateMarkerPosition,
  updateTime,
  weights,
  x,
  y,
  zoomMap
} = masterDashboard
</script>

<template>
          <article class="company-admin-page">
            <section class="company-admin-kpi-grid">
              <article class="company-admin-kpi"><i>▦</i><div><span>전체 회원사</span><strong>{{ displayCompanies.length }}</strong><small>전일 대비 ▲ 2</small></div></article>
              <article class="company-admin-kpi ok"><i>✓</i><div><span>정상 회원사</span><strong>18</strong><small>정상 비율 75.0%</small></div></article>
              <article class="company-admin-kpi warn"><i>!</i><div><span>주의 회원사</span><strong>4</strong><small>권한/정산 확인 필요</small></div></article>
              <article class="company-admin-kpi muted"><i>−</i><div><span>비활성</span><strong>2</strong><small>최근 30일 미접속</small></div></article>
              <article class="company-admin-kpi"><i>⌖</i><div><span>연결 지점</span><strong>38</strong><small>관제센터 포함</small></div></article>
              <article class="company-admin-kpi ok"><i>₩</i><div><span>정산 정상률</span><strong>99.2%</strong><small>미정산 1,248건</small></div></article>
            </section>

            <section class="company-admin-filter-row">
              <button class="filter-toggle" type="button">전체 회원사</button>
              <button class="filter-toggle" type="button">상태 전체</button>
              <button class="filter-toggle" type="button">권한 전체</button>
              <button class="filter-toggle" type="button">지점 연결 전체</button>
              <label><input v-model.trim="search" type="search" placeholder="회원사명, 대표자, 이메일 검색" /><span>⌕</span></label>
              <button class="primary" type="button" @click="openCompanyModal">회원사 추가</button>
            </section>

            <section class="company-admin-main-grid">
              <article class="company-admin-panel company-list-panel">
                <div class="company-panel-head">
                  <h3>회원사 목록 <small>운영/권한/지점 연결 현황</small></h3>
                  <div><button type="button">CSV 내보내기</button><button type="button">필터 초기화</button></div>
                </div>
                <table class="company-admin-table">
                  <thead><tr><th>회원사명</th><th>대표자</th><th>연락처</th><th>이메일</th><th>지점</th><th>상태</th><th>최근 로그인</th><th>관리</th></tr></thead>
                  <tbody>
                    <tr v-for="(company, index) in filteredCompanies" :key="company.email" :class="{ selected: index === 0 }">
                      <td><b>{{ company.name }}</b></td>
                      <td>{{ company.owner }}</td>
                      <td>{{ company.phone }}</td>
                      <td>{{ company.email }}</td>
                      <td>{{ company.centers }}개</td>
                      <td><span class="company-state" :class="statusClass(company.status)">{{ company.status }}</span></td>
                      <td>{{ index === 0 ? '2026-05-12 10:24' : '2026-05-11 17:32' }}</td>
                      <td><button type="button" @click="notifyCompanyEdited">수정</button><button type="button" @click="notifyPermissionSaved">권한</button></td>
                    </tr>
                  </tbody>
                </table>
                <footer class="company-admin-pagination"><span>전체 {{ filteredCompanies.length || 0 }}건</span><div><button>‹</button><button class="active">1</button><button>2</button><button>3</button><button>›</button></div><button>10개씩 보기</button></footer>
              </article>

              <aside class="company-admin-side">
                <article class="company-admin-panel company-detail-card">
                  <div class="company-panel-head"><h3>선택 회원사 상세</h3><span class="company-state ok">정상</span></div>
                  <dl>
                    <dt>회원사명</dt><dd>하이패스 서울(주)</dd>
                    <dt>대표자</dt><dd>김서울</dd>
                    <dt>대표 이메일</dt><dd>seoul@hipass.com</dd>
                    <dt>담당 지점</dt><dd>서울 톨게이트 외 4개</dd>
                    <dt>정산 권한</dt><dd>허용</dd>
                    <dt>최근 변경자</dt><dd>admin <small>2026-05-12 10:18</small></dd>
                  </dl>
                  <div class="company-detail-actions"><button type="button" @click="notifyCompanyEdited">회원사 수정</button><button type="button" @click="notifyPermissionSaved">권한 설정</button></div>
                </article>

                <article class="company-admin-panel company-link-card">
                  <h3>관제 대시보드 연결</h3>
                  <ul>
                    <li><span>서울 톨게이트</span><b>SEOUL-TOLL</b><em>진입 가능</em></li>
                    <li><span>수원 톨게이트</span><b>SUWON-TOLL</b><em>진입 가능</em></li>
                    <li><span>대전 톨게이트</span><b>DAEJEON-TOLL</b><em class="warn">검토 필요</em></li>
                    <li><span>대구 톨게이트</span><b>DAEGU-TOLL</b><em>진입 가능</em></li>
                  </ul>
                </article>
              </aside>
            </section>

            <section class="company-admin-bottom-grid">
              <article class="company-admin-panel company-permission-summary">
                <h3>권한/계정 요약</h3>
                <div class="permission-stat-cards">
                  <span><b>MASTER</b><strong>1</strong></span>
                  <span><b>ADMIN</b><strong>8</strong></span>
                  <span><b>OPERATOR</b><strong>26</strong></span>
                  <span><b>LOCKED</b><strong>2</strong></span>
                </div>
                <div class="permission-mini-chart">
                  <ChartJsPanel type="bar" :data="companyPermissionChartData" :options="companyPermissionChartOptions" :height="76" />
                </div>
              </article>
              <article class="company-admin-panel company-audit-card">
                <div class="company-panel-head"><h3>최근 회원사 관리 이력</h3><button type="button">전체 보기</button></div>
                <table class="company-admin-table compact">
                  <thead><tr><th>시간</th><th>관리자</th><th>대상</th><th>작업</th><th>결과</th></tr></thead>
                  <tbody>
                    <tr><td>10:24:11</td><td>admin</td><td>하이패스 서울(주)</td><td>권한 수정</td><td><span class="company-state ok">성공</span></td></tr>
                    <tr><td>10:18:02</td><td>admin</td><td>수원 하이패스(주)</td><td>지점 연결</td><td><span class="company-state ok">성공</span></td></tr>
                    <tr><td>09:42:33</td><td>admin</td><td>대전 하이패스(주)</td><td>정보 수정</td><td><span class="company-state warn">검토</span></td></tr>
                  </tbody>
                </table>
              </article>
            </section>
          </article>
</template>
