<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ControlDashboardPage from '@/dashboards/control/pages/ControlDashboardPage.vue'
import ControlTrafficEventPage from '@/dashboards/control/pages/ControlTrafficEventPage.vue'
import ControlGpsDecisionPage from '@/dashboards/control/pages/ControlGpsDecisionPage.vue'
import ControlReviewPage from '@/dashboards/control/pages/ControlReviewPage.vue'
import ControlSettlementPage from '@/dashboards/control/pages/ControlSettlementPage.vue'
import ControlEquipmentPage from '@/dashboards/control/pages/ControlEquipmentPage.vue'
import ControlRealtimePage from '@/dashboards/control/pages/ControlRealtimePage.vue'
import ControlSettingsPage from '@/dashboards/control/pages/ControlSettingsPage.vue'
import ControlFallbackPage from '@/dashboards/control/pages/ControlFallbackPage.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const nowText = ref('')
const activeMenu = ref('대시보드')
const selectedLane = ref(2)
const isLightMode = ref(false)
const showNotifications = ref(false)
const showOperatorMenu = ref(false)

let timer = null

const centerLabel = computed(() => {
  const center = route.query.center ?? 'SEOUL-TOLL'
  const names = {
    'SEOUL-TOLL': '서울 톨링 A',
    'SUWON-TOLL': '수원 톨링 A',
    'DAEJEON-TOLL': '대전 톨링 B',
    'DAEGU-TOLL': '대구 톨링 C',
    'BUSAN-TOLL': '부산 톨링 D'
  }
  return names[center] ?? center
})

const navItems = [
  { label: '대시보드', icon: '⌂' },
  { label: '실시간 관제', icon: '▣' },
  { label: '통행 이벤트', icon: '▤' },
  { label: 'GPS 판정', icon: '⌖' },
  { label: '검수', icon: '☑' },
  { label: '정산', icon: '₩' },
  { label: '장비 상태', icon: '⌁' },
  { label: '설정', icon: '⚙' }
]

const dashboardKpis = [
  { title: '오늘 통행', value: '1,248', unit: '대', sub: '전일 대비 ▲ 6.8%', icon: 'car.png', tone: 'purple', trend: 'up' },
  { title: 'GPS 정상 판정', value: '1,212', unit: '건', sub: '정상률 97.1%', icon: 'gps.png', tone: 'blue', trend: 'up' },
  { title: '검수 대기', value: '36', unit: '건', sub: '전일 대비 ▼ 5건', icon: 'caution.png', tone: 'yellow', trend: 'down' },
  { title: '오늘 통행료', value: '₩2,450,800', unit: '', sub: '전일 대비 ▲ 6.1%', icon: 'won.png', tone: 'navy', trend: 'up' }
]

const dashboardDetections = [
  {
    lane: 1,
    title: '1번 레일',
    size: '960x480',
    plate: '31가 9829',
    distance: '20px',
    fps: 'FPS 29.8',
    color: 'green',
    vehicle: 'black'
  },
  {
    lane: 2,
    title: '2번 레일',
    size: '960x480',
    plate: '46다 7720',
    distance: '18px',
    fps: 'FPS 29.8',
    color: 'blue',
    vehicle: 'silver'
  }
]

const statusCards = [
  { label: 'CCTV 영상', value: '정상', icon: 'cctv.png', tone: 'ok' },
  { label: 'GPS 수신', value: '정상', icon: 'gps2.png', tone: 'ok' },
  { label: '이벤트 수신', value: '정상', icon: 'notification.png', tone: 'ok' },
  { label: '통신망', value: 'LAN 사용 중', icon: 'signalpng.png', tone: 'info' },
  { label: '데이터 반영', value: '정상', icon: 'data.png', tone: 'ok' }
]

const gpsJudgements = [
  { lane: 1, plate: '31가 9829', direction: 'IN', laneText: 'L1', time: '17:36:47', gps: '정상', payment: '결제 가능', tone: 'ok' },
  { lane: 2, plate: '45나 6721', direction: 'OUT', laneText: 'L2', time: '17:36:12', gps: '경계 걸침', payment: '검수 권장', tone: 'boundary' },
  { lane: 1, plate: '67더 9012', direction: 'OUT', laneText: 'L1', time: '17:35:41', gps: '영역 이탈', payment: '검수 필요', tone: 'danger' }
]

const fieldAlerts = [
  { level: 'danger', title: '정차 의심', target: '2차선 · 98머 3344', time: '17:28:55', badge: '주의', icon: 'danger.png' },
  { level: 'warn', title: '2차선 CCTV 수신 지연', target: '2차선 카메라', time: '17:26:28', badge: '주의', icon: 'caution3.png' },
  { level: 'info', title: 'LTE 백업망 전환', target: 'LAN 연결 끊김 감지', time: '17:24:10', badge: '정보', icon: 'information2.png' }
]

const notifications = [
  { level: 'danger', title: '정차 의심 차량 확인 필요', desc: '2차선 · 98머 3344', time: '17:28:55' },
  { level: 'warn', title: '2차선 CCTV 수신 지연', desc: '카메라 프레임 지연 3초', time: '17:26:28' },
  { level: 'info', title: 'LTE 백업망 전환 기록', desc: 'LAN 연결 끊김 감지 후 복구', time: '17:24:10' }
]

const trafficRows = [
  { lane: 1, plate: '31가 9829', direction: 'IN', time: '17:36:47', gps: '정상', status: '정상 통과', tone: 'ok' },
  { lane: 2, plate: '46다 7720', direction: 'OUT', time: '17:36:12', gps: '경계 걸침', status: '검수 권장', tone: 'boundary' },
  { lane: 1, plate: '12가 3456', direction: 'IN', time: '17:35:41', gps: '영역 이탈', status: '검수 필요', tone: 'danger' },
  { lane: 2, plate: '85나 1212', direction: 'OUT', time: '17:35:18', gps: '정상', status: '정상 통과', tone: 'ok' }
]

const equipmentCards = [
  { title: '카메라 입력', status: '정상', desc: 'YOLO 합성 프레임 정상 수신', impact: '운영 정상', icon: '▣', tone: 'purple' },
  { title: 'GPS 수신', status: '정상', desc: 'GPS Fix 정상', impact: '운영 정상', icon: '⌖', tone: 'green' },
  { title: '통행 이벤트 수신', status: '정상', desc: '실시간 이벤트 정상 수신', impact: '운영 정상', icon: '▰', tone: 'blue' },
  { title: '통신망', status: '정상', desc: '현재 통신: LAN 사용 중', impact: '운영 정상', icon: '⌁', tone: 'teal' },
  { title: '데이터 반영', status: '정상', desc: '서버 반영 정상', impact: '운영 정상', icon: '◉', tone: 'mint' }
]

const equipmentLaneRows = [
  { lane: 1, name: '1번 레일 영역', eventAt: '17:36:46 (1초 전)', gps: '정상', analysis: '정상', impact: '운영 정상' },
  { lane: 2, name: '2번 레일 영역', eventAt: '17:36:46 (1초 전)', gps: '정상', analysis: '정상', impact: '운영 정상' }
]

const equipmentAlerts = [
  { tone: 'warn', title: '카메라 영상 수신 지연', desc: '카메라 영상 수신 지연 3초 발생', scope: '전체 레일', time: '17:33:12' },
  { tone: 'info', title: 'LTE 백업망 전환 기록', desc: 'LAN 장애로 LTE 백업망 전환 후 복구', scope: '전체 장비', time: '17:24:33' },
  { tone: 'warn', title: 'GPS 수신 지연', desc: 'GPS Fix 지연 2초 발생', scope: '전체 레일', time: '17:18:05' }
]

const historyRows = [
  { time: '17:36:28', item: '통행 이벤트 수신', impact: '없음', detail: '양 레일 이벤트 수신 정상', status: '완료', actor: '-' },
  { time: '17:33:12', item: '카메라 영상 수신 지연', impact: '전체 레일', detail: '카메라 영상 수신 지연 3초 발생 후 복구', status: '완료', actor: 'operator01' },
  { time: '17:24:33', item: 'LTE 백업망 전환', impact: '전체 장비', detail: 'LAN 장애 감지로 LTE 백업망 전환, 이후 LAN 복구', status: '완료', actor: 'system' },
  { time: '17:18:05', item: 'GPS 수신 지연', impact: '전체 레일', detail: 'GPS Fix 지연 2초 발생 후 복구', status: '완료', actor: 'operator01' },
  { time: '17:05:44', item: '데이터 반영 지연', impact: '서버 반영', detail: '데이터 반영 지연 5초 발생 후 복구', status: '완료', actor: 'system' }
]

const selectedLaneText = computed(() => `${selectedLane.value}차선`)
const topNetworkLabel = computed(() => (activeMenu.value === '대시보드' ? '이벤트 수신' : 'LAN 사용 중'))
const filteredGpsJudgements = computed(() => gpsJudgements.filter((row) => row.lane === selectedLane.value || row.tone === 'danger'))
const filteredTrafficRows = computed(() => trafficRows.filter((row) => row.lane === selectedLane.value))

function updateTime() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  const days = ['일', '월', '화', '수', '목', '금', '토']
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} (${days[now.getDay()]}) ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function logout() {
  window.alert('로그아웃 되었습니다.')
  auth.logout().finally(() => router.push('/'))
}

function goHome() {
  showOperatorMenu.value = false
  router.push('/')
}

function goMasterAdmin() {
  showOperatorMenu.value = false
  router.push('/master-admin')
}


const controlPageMap = {
  '대시보드': ControlDashboardPage,
  '통행 이벤트': ControlTrafficEventPage,
  'GPS 판정': ControlGpsDecisionPage,
  '검수': ControlReviewPage,
  '정산': ControlSettlementPage,
  '장비 상태': ControlEquipmentPage,
  '실시간 관제': ControlRealtimePage,
  '설정': ControlSettingsPage
}

const controlPageComponent = computed(() => controlPageMap[activeMenu.value] ?? ControlFallbackPage)

function getKpiIcon(filename) {
  return new URL(`../dashboards/icons/control/${filename}`, import.meta.url).href
}

function getAdminIcon(filename) {
  return new URL(`../dashboards/icons/admin/${filename}`, import.meta.url).href
}

provide('controlDashboardContext', {
  activeMenu,
  centerLabel,
  selectedLaneText,
  selectedLane,
  dashboardKpis,
  getKpiIcon,
  getAdminIcon,
  dashboardDetections,
  statusCards,
  filteredGpsJudgements,
  fieldAlerts,
  filteredTrafficRows,
  equipmentCards,
  equipmentLaneRows,
  equipmentAlerts,
  historyRows
})

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
})

onBeforeUnmount(() => {
  clearInterval(timer)
})
</script>

<template>
  <div class="ops-shell" :class="{ 'light-mode': isLightMode }">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark"></span>
        <div>
          <strong>HI-FIVE</strong>
          <span>OPERATOR</span>
        </div>
      </div>

      <nav class="nav">
        <button
          v-for="item in navItems"
          :key="item.label"
          :class="{ active: activeMenu === item.label }"
          type="button"
          @click="activeMenu = item.label"
        >
          <i>{{ item.icon }}</i>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div v-if="activeMenu === '정산'" class="event-side-stack settlement-side-stack">
        <section class="zone-card event-stats-card">
          <h3>정산 상태 <small>ⓘ</small></h3>
          <p><span class="zone-icon gps">✓</span><b>완료</b><strong>2,356건</strong></p>
          <p><span class="zone-icon warn">◔</span><b>대기</b><strong>142건</strong></p>
          <p><span class="zone-icon danger">!</span><b>보류</b><strong>36건</strong></p>
        </section>
      </div>

      <div v-else-if="activeMenu === '검수'" class="event-side-stack review-side-stack">
        <section class="zone-card event-stats-card">
          <h3>검수 요약 <small>ⓘ</small></h3>
          <p><span class="zone-icon warn">⌛</span><b>대기</b><strong>12</strong></p>
          <p><span class="zone-icon cctv">↻</span><b>처리중</b><strong>3</strong></p>
          <p><span class="zone-icon gps">✓</span><b>완료</b><strong>48</strong></p>
        </section>
        <section class="zone-card gps-guide-card">
          <p><span class="zone-icon cctv">▧</span><b>검수 가이드</b><strong></strong></p>
        </section>
      </div>

      <div v-else-if="activeMenu === 'GPS 판정'" class="event-side-stack gps-side-stack">
        <section class="zone-card event-stats-card">
          <h3>GPS 요약 <small>ⓘ</small></h3>
          <p><span class="zone-icon gps">✓</span><b>정상</b><strong>4,512건</strong></p>
          <p><span class="zone-icon danger">!</span><b>영역 이탈</b><strong>214건</strong></p>
          <p><span class="zone-icon lan">◉</span><b>최근 반영</b><strong>2초 전</strong></p>
        </section>
        <section class="zone-card gps-guide-card">
          <p><span class="zone-icon cctv">▧</span><b>GPS 판정 가이드</b><strong></strong></p>
        </section>
      </div>

      <div v-else-if="activeMenu === '통행 이벤트'" class="event-side-stack">
        <section class="zone-card event-filter-card">
          <h3>빠른 필터 <small>⌘</small></h3>
          <p><span class="zone-icon cctv">▣</span><b>오늘</b><strong></strong></p>
          <p><span class="zone-icon gps">✓</span><b>GPS 정상</b><strong></strong></p>
          <p><span class="zone-icon danger">△</span><b>영역 이탈</b><strong></strong></p>
          <p><span class="zone-icon warn">◎</span><b>검수 필요</b><strong></strong></p>
        </section>
        <section class="zone-card event-stats-card">
          <h3>이벤트 통계 <small>(금일)</small></h3>
          <p><b>전체 이벤트</b><strong>1,248건</strong></p>
          <p><b>GPS 정상</b><strong>1,074건</strong></p>
          <p><b>영역 이탈</b><strong>36건</strong></p>
          <p><b>검수 필요</b><strong>138건</strong></p>
        </section>
      </div>

      <section v-else class="zone-card">
        <h3>구역 상태</h3>
        <p><span class="zone-icon cctv">▰</span><b>CCTV</b><strong>정상</strong></p>
        <p><span class="zone-icon gps">⌖</span><b>GPS 수신</b><strong>정상</strong></p>
        <p><span class="zone-icon lan">⌁</span><b>LAN</b><strong>사용 중</strong></p>
      </section>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="center-toggle">
          <span>⌖ {{ centerLabel }}</span>
          <div class="lane-toggle" role="group" aria-label="차선 선택">
            <button type="button" :class="{ active: selectedLane === 1 }" @click="selectedLane = 1">1차선</button>
            <button type="button" :class="{ active: selectedLane === 2 }" @click="selectedLane = 2">2차선</button>
          </div>
        </div>
        <time>{{ nowText }}</time>
        <div class="top-status">
          <span><i class="dot ok"></i>CCTV 정상</span>
          <span><i class="dot ok"></i>GPS 정상</span>
          <span><i class="dot info"></i>{{ topNetworkLabel }}</span>
        </div>
        <button
          class="theme-toggle"
          type="button"
          :aria-label="isLightMode ? '다크 모드로 변경' : '라이트 모드로 변경'"
          @click="isLightMode = !isLightMode"
        >
          {{ isLightMode ? '☾' : '☀' }}
        </button>
        <div class="notify-wrap">
          <button class="bell" type="button" @click="showNotifications = !showNotifications">
            <span>{{ notifications.length }}</span>♢
          </button>
          <section v-if="showNotifications" class="notification-popover">
            <header>
              <b>알림 내역</b>
              <button type="button" @click="showNotifications = false">×</button>
            </header>
            <article v-for="item in notifications" :key="`${item.title}-${item.time}`" :class="item.level">
              <i>{{ item.level === 'info' ? 'i' : '!' }}</i>
              <div>
                <strong>{{ item.title }}</strong>
                <span>{{ item.desc }}</span>
              </div>
              <time>{{ item.time }}</time>
            </article>
          </section>
        </div>
        <div class="operator-wrap">
          <button class="operator" type="button" @click="showOperatorMenu = !showOperatorMenu">
            <b>{{ auth.member?.memberName ?? 'operator01' }}</b>
            <small>운영자</small>
          </button>
          <section v-if="showOperatorMenu" class="operator-menu">
            <button type="button" @click="goHome">홈</button>
            <button type="button" @click="goMasterAdmin">관리자</button>
            <button type="button" @click="logout">로그아웃</button>
          </section>
        </div>
      </header>

            <component :is="controlPageComponent" />

      </main>
  </div>
</template>

<style src="@/dashboards/control/styles/control-dashboard.css"></style>
