<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
  { title: '오늘 통행', value: '1,248', unit: '대', sub: '전일 대비 ▲ 6.8%', icon: 'car', tone: 'purple', trend: 'up' },
  { title: 'GPS 정상 판정', value: '1,212', unit: '건', sub: '정상률 97.1%', icon: 'target', tone: 'blue', trend: 'up' },
  { title: '검수 대기', value: '36', unit: '건', sub: '전일 대비 ▼ 5건', icon: 'warning', tone: 'yellow', trend: 'down' },
  { title: '오늘 통행료', value: '₩2,450,800', unit: '', sub: '전일 대비 ▲ 6.1%', icon: 'won', tone: 'navy', trend: 'up' }
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
  { label: 'CCTV 영상', value: '정상', icon: '▰', tone: 'ok' },
  { label: 'GPS 수신', value: '정상', icon: '⌖', tone: 'ok' },
  { label: '이벤트 수신', value: '정상', icon: '▣', tone: 'ok' },
  { label: '통신망', value: 'LAN 사용 중', icon: '⌁', tone: 'info' },
  { label: '데이터 반영', value: '정상', icon: '◉', tone: 'ok' }
]

const gpsJudgements = [
  { lane: 1, plate: '31가 9829', direction: 'IN', laneText: 'L1', time: '17:36:47', gps: '정상', payment: '결제 가능', tone: 'ok' },
  { lane: 2, plate: '45나 6721', direction: 'OUT', laneText: 'L2', time: '17:36:12', gps: '경계 걸침', payment: '검수 권장', tone: 'boundary' },
  { lane: 1, plate: '67더 9012', direction: 'OUT', laneText: 'L1', time: '17:35:41', gps: '영역 이탈', payment: '검수 필요', tone: 'danger' }
]

const fieldAlerts = [
  { level: 'danger', title: '정차 의심', target: '2차선 · 98머 3344', time: '17:28:55', badge: '주의' },
  { level: 'warn', title: '2차선 CCTV 수신 지연', target: '2차선 카메라', time: '17:26:28', badge: '주의' },
  { level: 'info', title: 'LTE 백업망 전환', target: 'LAN 연결 끊김 감지', time: '17:24:10', badge: '정보' }
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

      <section class="zone-card">
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

      <section v-if="activeMenu === '대시보드'" class="dashboard-page">
        <section class="kpi-grid">
          <article v-for="card in dashboardKpis" :key="card.title" class="kpi-card" :class="card.tone">
            <i>{{ card.icon }}</i>
            <div>
              <span>{{ card.title }}</span>
              <strong>{{ card.value }} <small>{{ card.unit }}</small></strong>
              <em :class="card.trend">{{ card.sub }}</em>
            </div>
          </article>
        </section>

        <section class="dashboard-grid">
          <article class="panel yolo-panel">
            <div class="panel-head">
              <h2>YOLO 합성 960x960</h2>
              <span class="live-chip"><i class="dot ok"></i>LIVE</span>
            </div>
            <div class="yolo-frame">
              <section
                v-for="lane in dashboardDetections"
                :key="lane.lane"
                class="dash-lane"
                :class="[lane.color, { selected: selectedLane === lane.lane }]"
              >
                <div class="dash-lane-title">
                  <b>{{ lane.title }}</b>
                  <span>{{ lane.size }}</span>
                </div>
                <span class="fps-chip">{{ lane.fps }}</span>
                <div class="road-scene">
                  <span class="road-line left"></span>
                  <span class="road-line right"></span>
                  <div class="dash-car" :class="lane.vehicle">
                    <i></i>
                    <em></em>
                  </div>
                  <div class="plate-box">
                    <strong>{{ lane.plate }}</strong>
                    <small>{{ lane.distance }}</small>
                  </div>
                </div>
              </section>
            </div>
            <footer class="frame-meta">
              <p><span>원본 해상도</span><b>1920 x 1080</b></p>
              <p><span>합성 해상도</span><b>960 x 960</b></p>
              <p><span>YOLO 모델</span><b>v8.1 (tuned)</b></p>
              <p><span>FPS</span><b>29.8</b></p>
              <p><span>구역</span><b>{{ centerLabel }}</b></p>
              <p><span>운영 상태</span><b>정상</b></p>
            </footer>
          </article>

          <section class="right-column">
            <article class="panel current-panel">
              <div class="panel-head"><h2>현재 상태</h2></div>
              <div class="status-grid">
                <article v-for="item in statusCards" :key="item.label" :class="item.tone">
                  <i>{{ item.icon }}</i>
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </article>
              </div>
            </article>

            <article class="panel gps-panel">
              <div class="panel-head">
                <h2>최근 GPS 판정</h2>
                <button type="button">전체 보기 ›</button>
              </div>
              <table>
                <thead>
                  <tr><th>차량번호</th><th>방향</th><th>차선</th><th>통과 시각</th><th>GPS 판정</th><th>결제 판정</th></tr>
                </thead>
                <tbody>
                  <tr v-for="row in filteredGpsJudgements" :key="`${row.plate}-${row.time}`">
                    <td><i class="row-dot" :class="row.tone"></i>{{ row.plate }}</td>
                    <td><span class="pill">{{ row.direction }}</span></td>
                    <td><span class="pill">{{ row.laneText }}</span></td>
                    <td>{{ row.time }}</td>
                    <td><span class="state" :class="row.tone">{{ row.gps }}</span></td>
                    <td><span class="pay" :class="row.tone">{{ row.payment }}</span></td>
                  </tr>
                </tbody>
              </table>
            </article>

            <article class="panel field-panel">
              <div class="panel-head">
                <h2>현장 알림 <small>(최근 3건)</small></h2>
                <button type="button">전체 보기 ›</button>
              </div>
              <div class="field-list">
                <article v-for="alert in fieldAlerts" :key="alert.title" :class="alert.level">
                  <i>{{ alert.level === 'info' ? 'i' : '!' }}</i>
                  <b>{{ alert.title }}</b>
                  <span>{{ alert.target }}</span>
                  <time>{{ alert.time }}</time>
                  <em>{{ alert.badge }}</em>
                </article>
              </div>
            </article>
          </section>
        </section>

        <article class="panel recent-panel">
          <div class="panel-head">
            <h2>최근 통행</h2>
            <button type="button">전체 보기 ›</button>
          </div>
          <table>
            <thead>
              <tr><th>차량번호</th><th>차선</th><th>방향</th><th>통과시각</th><th>GPS 판정</th><th>상태</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in filteredTrafficRows" :key="`${row.plate}-${row.time}`">
                <td>{{ row.plate }}</td>
                <td><span class="pill">{{ row.lane }}번 레일</span></td>
                <td><span class="pill">{{ row.direction }}</span></td>
                <td>{{ row.time }}</td>
                <td><span class="state" :class="row.tone">{{ row.gps }}</span></td>
                <td><span class="pay" :class="row.tone">{{ row.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>

      <section v-else-if="activeMenu === '장비 상태'" class="equipment-page">
        <section class="title-row">
          <h1>장비 상태</h1>
          <p>구역 운영에 영향을 주는 상태만 표시합니다.</p>
        </section>

        <section class="equipment-grid">
          <article v-for="card in equipmentCards" :key="card.title" class="equipment-card" :class="card.tone">
            <i>{{ card.icon }}</i>
            <div>
              <span>{{ card.title }}</span>
              <strong>{{ card.status }}</strong>
              <em>{{ card.desc }}</em>
            </div>
            <p>영향 : {{ card.impact }}</p>
          </article>
        </section>

        <section class="equipment-layout">
          <article class="panel camera-panel">
            <div class="panel-head">
              <h2>단일 카메라 / YOLO 합성 프레임</h2>
              <span class="live-chip"><i class="dot ok"></i>LIVE</span>
            </div>
            <div class="camera-note">
              <span>단일 카메라 입력<br /><b>YOLO 합성 프레임 960x960</b></span>
              <span>상단 : 1번 레일 영역 960x480<br />하단 : 2번 레일 영역 960x480</span>
            </div>
            <div class="equipment-frame">
              <section
                v-for="lane in dashboardDetections"
                :key="lane.lane"
                class="dash-lane"
                :class="[lane.color, { selected: selectedLane === lane.lane }]"
              >
                <div class="dash-lane-title">
                  <b>{{ lane.title }} 영역</b>
                  <span>{{ lane.size }}</span>
                </div>
                <div class="road-scene">
                  <span class="road-line left"></span>
                  <span class="road-line right"></span>
                  <div class="dash-car" :class="lane.vehicle">
                    <i></i>
                    <em></em>
                  </div>
                  <div class="plate-box">
                    <strong>{{ lane.plate }}</strong>
                    <small>{{ lane.distance }}</small>
                  </div>
                </div>
              </section>
            </div>
          </article>

          <section class="right-column">
            <article class="panel comm-panel">
              <div class="panel-head"><h2>장비 통신 상태</h2></div>
              <div class="comm-grid">
                <div class="comm-card">
                  <i>⌁</i>
                  <span>현재 통신</span>
                  <strong>LAN 사용 중</strong>
                  <small>유선 네트워크 정상</small>
                </div>
                <div class="comm-card">
                  <i>△</i>
                  <span>LTE 백업망</span>
                  <strong class="pending">대기</strong>
                  <small>자동 전환 대기 상태</small>
                </div>
              </div>
              <div class="comm-summary">
                <p><span>마지막 전환 시간</span><b>2025-05-08 14:22:31</b></p>
                <p><span>통신 장애 상태</span><b>없음</b></p>
                <p><span>예상 영향</span><b>없음 (운영 정상)</b></p>
              </div>
            </article>

            <article class="panel rail-panel">
              <div class="panel-head"><h2>레일 영역 상태</h2></div>
              <table>
                <thead>
                  <tr><th>레일 영역</th><th>마지막 이벤트 수신</th><th>GPS 판정 가능</th><th>분석 상태</th><th>영향</th></tr>
                </thead>
                <tbody>
                  <tr v-for="row in equipmentLaneRows" :key="row.lane">
                    <td><b class="lane-badge">{{ row.lane }}</b>{{ row.name }}</td>
                    <td class="ok">{{ row.eventAt }}</td>
                    <td class="ok">{{ row.gps }}</td>
                    <td class="ok">{{ row.analysis }}</td>
                    <td class="ok">{{ row.impact }}</td>
                  </tr>
                </tbody>
              </table>
            </article>

            <article class="panel alert-panel">
              <div class="panel-head">
                <h2>알림 및 조치</h2>
                <button type="button">전체 알림 보기 ›</button>
              </div>
              <div class="alert-list">
                <article v-for="alert in equipmentAlerts" :key="alert.title" class="alert-row" :class="alert.tone">
                  <i>{{ alert.tone === 'info' ? 'i' : '!' }}</i>
                  <div>
                    <b>{{ alert.title }}</b>
                    <span>{{ alert.desc }}</span>
                  </div>
                  <p><span>영향 범위</span>{{ alert.scope }}</p>
                  <p><span>발생 시각</span>{{ alert.time }}</p>
                  <button type="button">확인</button>
                  <button type="button">유지보수 요청</button>
                  <button type="button" class="done">조치 완료</button>
                </article>
              </div>
            </article>
          </section>
        </section>

        <article class="panel history-panel">
          <div class="panel-head">
            <h2>상태 이력 <small>(최근 5건)</small></h2>
            <button type="button">전체 이력 보기 ›</button>
          </div>
          <table>
            <thead>
              <tr><th>발생시각</th><th>항목</th><th>영향</th><th>상세 내용</th><th>처리 상태</th><th>처리자</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in historyRows" :key="`${row.time}-${row.item}`">
                <td>{{ row.time }}</td>
                <td>{{ row.item }}</td>
                <td>{{ row.impact }}</td>
                <td>{{ row.detail }}</td>
                <td><span class="status-ok">{{ row.status }}</span></td>
                <td>{{ row.actor }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>

      <section v-else class="panel empty-page">
        <h1>{{ activeMenu }}</h1>
        <p>{{ centerLabel }} · {{ selectedLaneText }} 기준 상세 화면입니다.</p>
        <button type="button" @click="activeMenu = '대시보드'">대시보드로 돌아가기</button>
      </section>
    </main>
  </div>
</template>

<style scoped>
:global(body){background:#020b16}
*{box-sizing:border-box}
button{font:inherit;cursor:pointer}
.ops-shell{min-height:100vh;min-width:1440px;display:grid;grid-template-columns:200px 1fr;color:#dce9f8;background:radial-gradient(circle at 78% 0,rgba(0,126,255,.14),transparent 34%),radial-gradient(circle at 24% 24%,rgba(0,78,160,.12),transparent 30%),linear-gradient(135deg,#020914 0%,#061528 54%,#020914 100%);font-family:Pretendard,Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.sidebar{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;padding:20px 12px;border-right:1px solid rgba(46,130,225,.28);background:linear-gradient(180deg,rgba(5,16,34,.98),rgba(4,22,42,.96));overflow:hidden}
.brand{display:flex;gap:12px;align-items:flex-start;height:80px}
.brand-mark{width:32px;height:32px;border:5px solid #1784ff;transform:rotate(45deg);position:relative}
.brand-mark::after{content:'';position:absolute;inset:7px;border-radius:50%;background:#1784ff}
.brand strong{display:block;color:#fff;font-size:25px;line-height:1}
.brand span{display:block;margin-top:2px;color:#d6e6f8;font-size:13px}
.nav{display:grid;gap:8px}
.nav button{height:46px;display:flex;align-items:center;gap:13px;padding:0 12px;border:0;border-radius:6px;background:transparent;color:#d4e2f3;text-align:left;font-size:16px}
.nav button i{width:20px;text-align:center;color:#e8f3ff;font-style:normal;font-size:18px}
.nav button.active,.nav button:hover{color:#fff;background:linear-gradient(90deg,rgba(22,103,219,.56),rgba(17,78,153,.25));box-shadow:inset 0 0 0 1px rgba(33,130,255,.66)}
.zone-card{position:sticky;top:calc(100vh - 300px);margin-top:auto;padding:16px 14px;border:1px solid rgba(42,133,227,.3);border-radius:7px;background:rgba(5,18,37,.66)}
.zone-card h3{margin:0 0 14px;color:#eaf4ff;font-size:15px}
.zone-card p{min-height:58px;display:grid;grid-template-columns:34px 1fr;align-items:center;column-gap:10px;margin:0;padding:9px 0;border-top:1px solid rgba(125,164,210,.12)}
.zone-card b{align-self:end;font-size:14px;font-weight:500;line-height:1.05}
.zone-card strong{grid-column:2;align-self:start;color:#66ed8a;font-size:14px;font-weight:500;line-height:1.1}
.zone-icon{grid-row:1/3;display:grid;place-items:center;width:32px;height:32px;border-radius:7px;color:#061120;background:#5be578;font-size:19px}
.zone-icon.gps{background:#75e578}.zone-icon.lan{background:#2789ff;color:white}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%}
.dot.ok{background:#46dd70}.dot.warn{background:#ffc33e}.dot.danger{background:#ff5b55}.dot.info{background:#1979ff}
.main{min-width:0;padding:0 20px 16px}
.topbar{height:68px;display:grid;grid-template-columns:330px 1fr auto 40px 44px 132px;align-items:center;gap:12px;border-bottom:1px solid rgba(42,133,227,.24)}
.center-toggle,.top-status span{height:38px;display:inline-flex;align-items:center;gap:10px;padding:0 14px;border:1px solid rgba(42,133,227,.42);border-radius:6px;background:rgba(6,24,48,.74);color:#eaf4ff}
.center-toggle{justify-content:space-between}
.center-toggle>span{font-weight:900;white-space:nowrap}
.lane-toggle{display:flex;gap:4px;padding:3px;border-radius:5px;background:rgba(1,8,18,.55)}
.lane-toggle button{height:26px;padding:0 10px;border:0;border-radius:4px;background:transparent;color:#a9c2df;font-weight:800}
.lane-toggle button.active{background:linear-gradient(180deg,#0b74df,#074c9f);color:white;box-shadow:0 0 16px rgba(34,132,255,.35)}
.topbar time{text-align:center;color:#e4edf9}
.top-status{display:flex;gap:8px}
.theme-toggle{width:38px;height:38px;display:grid;place-items:center;border:1px solid rgba(42,133,227,.44);border-radius:50%;background:rgba(6,24,48,.78);color:#ffd766;font-size:18px;box-shadow:0 0 16px rgba(29,120,255,.12)}
.notify-wrap{position:relative}
.bell{position:relative;width:40px;height:40px;border:0;background:transparent;color:#dce9f8;font-size:22px}
.bell span{position:absolute;right:1px;top:2px;display:grid;place-items:center;width:18px;height:18px;border-radius:50%;background:#ec4b55;color:white;font-size:12px}
.notification-popover{position:absolute;right:-8px;top:48px;z-index:30;width:340px;padding:10px;border:1px solid rgba(58,126,204,.48);border-radius:8px;background:linear-gradient(145deg,rgba(7,24,45,.98),rgba(4,13,26,.96));box-shadow:0 22px 48px rgba(0,0,0,.42)}
.notification-popover header{display:flex;align-items:center;justify-content:space-between;padding:4px 4px 10px;border-bottom:1px solid rgba(125,164,210,.15)}
.notification-popover header b{color:#f2f8ff}.notification-popover header button{width:26px;height:26px;border:0;border-radius:50%;background:rgba(255,255,255,.08);color:#dce9f8}
.notification-popover article{display:grid;grid-template-columns:28px 1fr 58px;gap:8px;align-items:center;min-height:58px;padding:10px 4px;border-bottom:1px solid rgba(125,164,210,.12)}
.notification-popover article:last-child{border-bottom:0}.notification-popover i{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;font-style:normal;font-weight:900}.notification-popover .danger i{background:#ff5b55;color:#fff}.notification-popover .warn i{background:#ffc33e;color:#061120}.notification-popover .info i{background:#398dff;color:#fff}
.notification-popover strong{display:block;color:#f3f8ff;font-size:13px}.notification-popover span{display:block;margin-top:3px;color:#a9bdd5;font-size:12px}.notification-popover time{color:#9fb4ce;font-size:12px;text-align:right}
.operator-wrap{position:relative}
.operator{width:100%;display:grid;grid-template-columns:1fr;align-items:center;justify-items:start;border:0;background:transparent;padding:0;text-align:left;cursor:pointer}
.operator b{color:#fff}.operator small{color:#a9bdd5}
.operator-menu{position:absolute;right:0;top:44px;z-index:35;width:132px;padding:8px;border:1px solid rgba(58,126,204,.48);border-radius:8px;background:linear-gradient(145deg,rgba(7,24,45,.98),rgba(4,13,26,.96));box-shadow:0 22px 48px rgba(0,0,0,.42)}
.operator-menu button{width:100%;height:32px;border:0;border-radius:5px;background:transparent;color:#dce9f8;text-align:left;padding:0 10px}
.operator-menu button:hover{background:rgba(47,140,255,.18);color:#fff}
.panel{border:1px solid rgba(58,126,204,.46);border-radius:7px;background:linear-gradient(145deg,rgba(10,29,53,.92),rgba(5,16,32,.82));box-shadow:0 18px 42px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.03);overflow:hidden}
.panel-head{min-height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;border-bottom:1px solid rgba(125,164,210,.14)}
.panel-head h2{margin:0;color:#f1f7ff;font-size:17px}.panel-head small{color:#9fb4ce}
.panel-head button{height:28px;border:0;background:transparent;color:#b9d3ef}
.kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:14px}
.kpi-card{min-height:116px;display:grid;grid-template-columns:76px 1fr;gap:14px;align-items:center;padding:17px;border:1px solid rgba(58,126,204,.44);border-radius:7px;background:linear-gradient(145deg,rgba(12,33,59,.96),rgba(5,17,33,.88));box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.kpi-card i{display:grid;place-items:center;width:62px;height:62px;border-radius:50%;font-style:normal;font-size:0;background:linear-gradient(135deg,#2f8cff,#0c4d9f)}
.kpi-card i::before{font-size:31px;line-height:1;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.34)}
.kpi-card.purple i::before{content:'🚘'}
.kpi-card.blue i::before{content:'◎';font-size:42px;font-weight:900}
.kpi-card.yellow i::before{content:'⚠';font-size:34px}
.kpi-card.navy i::before{content:'₩';font-size:36px;font-weight:900}
.kpi-card.purple i{background:linear-gradient(135deg,#9672ff,#553cbb)}.kpi-card.yellow i{background:linear-gradient(135deg,#ffd65d,#b17600)}.kpi-card.navy i{background:linear-gradient(135deg,#1d75d8,#093b7c)}
.kpi-card span{display:block;color:#f1f7ff;font-weight:800}.kpi-card strong{display:block;margin-top:6px;color:#fff;font-size:28px;line-height:1.1}.kpi-card small{font-size:16px}.kpi-card em{display:block;margin-top:7px;color:#68ef8c;font-style:normal}.kpi-card em.down{color:#ff6b63}
.dashboard-grid{display:grid;grid-template-columns:minmax(600px,.97fr) minmax(570px,1.03fr);gap:10px;margin-top:10px}
.yolo-panel{padding-bottom:10px}
.live-chip{height:26px;display:inline-flex;align-items:center;gap:7px;padding:0 12px;border-radius:5px;background:rgba(35,136,68,.18);color:#84f1a0;font-weight:800}
.yolo-frame{height:486px;margin:0 10px;border:1px solid rgba(89,157,255,.4);border-radius:7px;overflow:hidden;background:#07111f}
.dash-lane{position:relative;height:50%;border-bottom:1px solid rgba(89,157,255,.28);overflow:hidden;background:linear-gradient(180deg,rgba(60,89,116,.36),rgba(14,24,35,.9))}
.dash-lane:last-child{border-bottom:0}.dash-lane.selected{box-shadow:inset 0 0 0 2px rgba(78,169,255,.78)}
.dash-lane-title{position:absolute;left:12px;top:12px;z-index:4;display:flex;gap:8px;align-items:center}
.dash-lane-title b,.dash-lane-title span,.fps-chip{height:30px;display:inline-flex;align-items:center;padding:0 10px;border-radius:5px;background:rgba(5,21,42,.86);color:#f5fbff;font-weight:900;white-space:nowrap}
.dash-lane-title b{background:rgba(8,45,92,.92)}.fps-chip{position:absolute;right:10px;top:12px;z-index:4}
.road-scene{position:absolute;inset:0;background:linear-gradient(115deg,transparent 0 28%,rgba(255,255,255,.16) 28% 29%,transparent 29% 68%,rgba(255,255,255,.13) 68% 69%,transparent 69%),repeating-linear-gradient(90deg,rgba(255,255,255,.05) 0 7px,transparent 7px 44px),linear-gradient(180deg,#56606a,#252e37)}
.road-line{position:absolute;top:0;bottom:0;width:3px;background:rgba(255,255,255,.42);transform:skewX(-14deg)}.road-line.left{left:38%}.road-line.right{right:26%}
.dash-car{position:absolute;left:50%;top:50%;width:170px;height:104px;transform:translate(-50%,-40%);border:2px solid rgba(98,255,78,.8);border-radius:36px 36px 16px 16px;background:linear-gradient(180deg,#1d242c,#07090d);box-shadow:0 20px 26px rgba(0,0,0,.36)}
.dash-car.silver{border-color:rgba(38,132,255,.85);background:linear-gradient(180deg,#d6dee8,#596778)}
.dash-car i{position:absolute;left:31px;right:31px;top:18px;height:34px;border-radius:22px 22px 6px 6px;background:rgba(255,255,255,.18)}
.dash-car em{position:absolute;left:22px;right:22px;bottom:16px;height:12px;border-radius:10px;background:rgba(255,255,255,.18)}
.plate-box{position:absolute;left:50%;bottom:26px;z-index:5;transform:translateX(-50%);display:grid;place-items:center;min-width:94px;border-radius:5px;background:#62dc2f;color:#061120;box-shadow:0 0 18px rgba(98,220,47,.34);font-weight:900}
.dash-lane.blue .plate-box{background:#1682ff;color:white;box-shadow:0 0 18px rgba(22,130,255,.36)}
.plate-box strong{padding:4px 10px;font-size:15px}.plate-box small{width:100%;padding:3px 0;border-top:1px solid rgba(0,0,0,.18);text-align:center}
.frame-meta{display:grid;grid-template-columns:repeat(6,1fr);margin:10px 10px 0;border:1px solid rgba(125,164,210,.16);border-radius:6px;overflow:hidden}
.frame-meta p{margin:0;padding:9px 12px;border-right:1px solid rgba(125,164,210,.16)}.frame-meta p:last-child{border-right:0}.frame-meta span{display:block;color:#9fb4ce;font-size:12px}.frame-meta b{display:block;margin-top:3px;color:#fff}
.right-column{display:grid;gap:10px;grid-template-rows:auto auto 1fr}
.status-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:12px}
.status-grid article{min-height:72px;display:grid;grid-template-columns:34px 1fr;align-items:center;justify-items:center;column-gap:8px;padding:10px;border:1px solid rgba(86,151,221,.28);border-radius:6px;background:rgba(8,28,54,.62);text-align:center}
.status-grid i{grid-row:1/3;display:inline-grid;place-items:center;width:34px;height:34px;margin-right:0;border-radius:8px;background:#4dde73;color:#061120;font-style:normal;font-size:19px}
.status-grid span{color:#f2f8ff;justify-self:center;text-align:center}.status-grid strong{grid-column:2;display:grid;place-items:center;width:100%;margin-top:2px;color:#67ed88;text-align:center;font-size:13px;font-weight:500}.status-grid .info strong{color:#53aaff}
table{width:100%;border-collapse:collapse}.gps-panel table,.recent-panel table,.rail-panel table,.history-panel table{font-size:14px}
th,td{height:34px;padding:0 12px;border-bottom:1px solid rgba(125,164,210,.13);color:#dce9f8;text-align:left;white-space:nowrap}
th{color:#a8bbd2;background:rgba(26,46,73,.62);font-weight:600}.gps-panel table,.recent-panel table{margin:12px;width:calc(100% - 24px)}
.pill{display:inline-grid;place-items:center;min-width:46px;height:24px;padding:0 10px;border-radius:5px;background:rgba(19,92,178,.5);color:#f3f9ff}.row-dot{display:inline-block;width:11px;height:11px;margin-right:12px;border-radius:50%;background:#49e46d;box-shadow:0 0 10px rgba(73,228,109,.34)}.row-dot.boundary,.row-dot.warn{background:#ff9f2f;box-shadow:0 0 10px rgba(255,159,47,.36)}.row-dot.danger{background:#ff5f58;box-shadow:0 0 10px rgba(255,95,88,.36)}
.state,.pay{display:inline-grid;place-items:center;min-width:58px;height:24px;padding:0 10px;border-radius:5px;font-weight:900}.state.ok,.pay.ok{background:rgba(37,204,113,.16);color:#65ef87}.state.boundary,.pay.boundary,.state.warn,.pay.warn{background:rgba(255,159,47,.16);color:#ffb65f}.state.danger{background:rgba(255,91,85,.16);color:#ff6d67}.pay.danger{background:rgba(255,195,62,.16);color:#ffd44e}
.field-list{display:grid;gap:8px;padding:12px}.field-list article{display:grid;grid-template-columns:30px minmax(220px,240px) minmax(150px,1fr) 90px 62px;align-items:center;gap:10px;min-height:44px;padding:8px 10px;border:1px solid rgba(125,164,210,.16);border-radius:6px;background:rgba(5,18,37,.46)}.field-list i{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;font-style:normal;font-weight:900}.field-list .danger i{background:#ff6560;color:white}.field-list .warn i{background:#ffc33e;color:#061120}.field-list .info i{background:#398dff;color:white}.field-list b{color:#ff6f69;white-space:nowrap}.field-list .warn b{color:#ffd86a}.field-list .info b{color:#9ccaff}.field-list span{color:#dce9f8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.field-list time{color:#a8bbd2}.field-list em{display:grid;place-items:center;height:25px;border-radius:5px;background:rgba(255,91,85,.13);color:#ff756f;font-style:normal;font-weight:900}.field-list .info em{background:rgba(57,141,255,.14);color:#8fc1ff}
.recent-panel{margin-top:10px}.recent-panel table{font-size:16px;table-layout:fixed}.recent-panel th,.recent-panel td{height:40px}.recent-panel th:nth-child(1),.recent-panel td:nth-child(1){width:20%}.recent-panel th:nth-child(2),.recent-panel td:nth-child(2){width:16%}.recent-panel th:nth-child(3),.recent-panel td:nth-child(3){width:12%}.recent-panel th:nth-child(4),.recent-panel td:nth-child(4){width:18%}.recent-panel th:nth-child(5),.recent-panel td:nth-child(5){width:17%}.recent-panel th:nth-child(6),.recent-panel td:nth-child(6){width:17%}
.title-row{display:flex;align-items:end;gap:14px;height:54px}.title-row h1{margin:0;color:#fff;font-size:28px}.title-row p{margin:0 0 4px;color:#a9bdd5}
.equipment-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.equipment-card{min-height:120px;display:grid;grid-template-columns:62px 1fr;gap:10px;padding:16px;border:1px solid rgba(58,126,204,.38);border-radius:7px;background:linear-gradient(145deg,rgba(11,31,56,.9),rgba(5,17,33,.82))}.equipment-card i{grid-row:span 2;display:grid;place-items:center;width:56px;height:56px;border-radius:50%;font-style:normal;font-size:28px;background:linear-gradient(135deg,#35b7ff,#1378ef)}.equipment-card.purple i{background:linear-gradient(135deg,#9c6bff,#6846d8)}.equipment-card.green i{background:linear-gradient(135deg,#5ff5be,#16a373)}.equipment-card.teal i{background:linear-gradient(135deg,#2be7c3,#137c8f)}.equipment-card.mint i{background:linear-gradient(135deg,#7af0b0,#159f65)}.equipment-card span{color:#e8f4ff;font-weight:800}.equipment-card strong{display:block;color:#45f577;font-size:26px;line-height:1.1}.equipment-card em{color:#45f577;font-style:normal;font-size:12px}.equipment-card p{grid-column:1/-1;margin:6px 0 0;padding-top:12px;border-top:1px solid rgba(125,164,210,.14);color:#d5e4f5}
.equipment-layout{display:grid;grid-template-columns:minmax(560px,.83fr) minmax(700px,1.07fr);gap:14px;margin-top:12px}.camera-panel{padding-bottom:14px}.camera-note{display:grid;grid-template-columns:1fr 1fr;margin:14px 14px 8px;padding:10px 14px;border:1px solid rgba(33,130,255,.58);border-radius:5px;background:rgba(14,55,104,.42);color:#cfe1f7}.camera-note b{color:#55a9ff}.equipment-frame{position:relative;width:min(100%,620px);aspect-ratio:1/1;margin:0 auto;overflow:hidden;border:1px solid rgba(89,157,255,.42);border-radius:8px;background:#07111f}
.comm-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px}.comm-card{display:grid;grid-template-columns:50px 1fr;align-items:center;padding:14px;border:1px solid rgba(58,126,204,.28);border-radius:6px;background:rgba(5,18,37,.52)}.comm-card i{grid-row:span 3;color:#9eb9d6;font-size:30px;font-style:normal}.comm-card span{color:#a8bad0}.comm-card strong{color:#43e875;font-size:24px}.comm-card strong.pending{color:#fff}.comm-card small{color:#c8d8ea}.comm-summary{display:grid;grid-template-columns:repeat(3,1fr);padding:0 14px 14px}.comm-summary p{margin:0;padding:12px;border-right:1px solid rgba(125,164,210,.14)}.comm-summary p:last-child{border-right:0}.comm-summary span{display:block;color:#9fb4ce}.comm-summary b{color:#fff}
.rail-panel{padding-bottom:12px}.rail-panel table{margin:12px 14px;width:calc(100% - 28px);border:1px solid rgba(125,164,210,.16);border-radius:6px;overflow:hidden}.lane-badge{display:inline-grid;place-items:center;width:22px;height:22px;margin-right:10px;border-radius:50%;background:#6d55d9;color:#fff}.rail-panel tr:nth-child(2) .lane-badge{background:#2e73d9}.ok{color:#48e875!important}
.alert-panel{min-height:198px}.alert-list{display:grid;gap:8px;padding:12px 14px}.alert-row{display:grid;grid-template-columns:30px minmax(220px,1fr) 90px 80px 56px 104px 88px;align-items:center;gap:10px;min-height:48px;padding:8px;border:1px solid rgba(125,164,210,.16);border-radius:6px;background:rgba(5,18,37,.42)}.alert-row i{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;font-style:normal;font-weight:900}.alert-row.warn i{background:#ffc33e;color:#05101f}.alert-row.info i{background:#3b8cff;color:#fff}.alert-row b{display:block;color:#ffd86a}.alert-row.info b{color:#9ac8ff}.alert-row span,.alert-row p span{display:block;color:#9fb4ce;font-size:12px}.alert-row p{margin:0;color:#dce9f8;font-size:12px}.alert-row button{height:28px;border:1px solid rgba(58,126,204,.36);border-radius:5px;background:rgba(9,37,72,.62);color:#dce9f8}.alert-row button.done{border-color:rgba(37,204,113,.34);color:#83f0a2;background:rgba(37,204,113,.12)}
.history-panel{margin-top:10px}.history-panel table{margin:0 12px 12px;width:calc(100% - 24px)}.status-ok{display:inline-grid;place-items:center;min-width:48px;height:23px;border-radius:5px;background:rgba(37,204,113,.16);color:#6ff08e;font-weight:800}
.empty-page{margin-top:14px;padding:40px}.empty-page h1{margin:0 0 10px;color:#fff}.empty-page p{color:#b7c9dd}.empty-page button{height:34px;padding:0 14px;border:1px solid rgba(33,130,255,.6);border-radius:6px;background:rgba(9,58,116,.72);color:#fff}
.ops-shell.light-mode{color:#1b2b3d;background:linear-gradient(135deg,#edf5ff 0%,#f8fbff 48%,#e8f2ff 100%)}
.light-mode .sidebar{background:linear-gradient(180deg,#f7fbff,#e8f2ff);border-right-color:rgba(58,126,204,.32)}
.light-mode .brand strong,.light-mode .nav button,.light-mode .nav button i,.light-mode .operator b,.light-mode .title-row h1,.light-mode .panel-head h2,.light-mode .kpi-card strong,.light-mode .frame-meta b,.light-mode .empty-page h1{color:#102033}
.light-mode .brand span,.light-mode .operator small,.light-mode .title-row p,.light-mode .panel-head small,.light-mode .frame-meta span,.light-mode th{color:#53677f}
.light-mode .nav button.active,.light-mode .nav button:hover{color:#0a3d78;background:linear-gradient(90deg,rgba(68,149,246,.2),rgba(68,149,246,.08));box-shadow:inset 0 0 0 1px rgba(20,104,208,.42)}
.light-mode .zone-card,.light-mode .panel,.light-mode .kpi-card,.light-mode .center-toggle,.light-mode .top-status span,.light-mode .theme-toggle{background:rgba(255,255,255,.82);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}
.light-mode .topbar{border-bottom-color:rgba(58,126,204,.24)}
.light-mode .topbar time,.light-mode .top-status span,.light-mode .center-toggle,.light-mode td,.light-mode .field-list span,.light-mode .field-list time,.light-mode .camera-note,.light-mode .comm-card small{color:#21364d}
.light-mode .lane-toggle{background:#e7f0fb}.light-mode .lane-toggle button{color:#41617f}.light-mode .lane-toggle button.active{color:white}
.light-mode .theme-toggle{color:#21496f;background:#f7fbff}
.light-mode .bell,.light-mode .operator button{color:#21496f}
.light-mode .notification-popover{background:rgba(255,255,255,.98);border-color:rgba(58,126,204,.32);box-shadow:0 22px 48px rgba(49,91,137,.22)}
.light-mode .notification-popover header{border-bottom-color:rgba(58,126,204,.18)}.light-mode .notification-popover header b,.light-mode .notification-popover strong{color:#102033}.light-mode .notification-popover span,.light-mode .notification-popover time{color:#53677f}.light-mode .notification-popover header button{background:#e8f1fb;color:#21496f}
.light-mode .kpi-card span,.light-mode .equipment-card span,.light-mode .status-grid span{color:#21364d}
.light-mode .kpi-card em,.light-mode .status-grid strong,.light-mode .zone-card strong{color:#16733b}
.light-mode .kpi-card em.down{color:#c43c35}
.light-mode .status-grid article,.light-mode .field-list article,.light-mode .comm-card{background:rgba(246,250,255,.86);border-color:rgba(58,126,204,.26)}
.light-mode th{background:#e5eef9}.light-mode .pill{background:#dcecff;color:#0f4f9b}
.light-mode .yolo-frame,.light-mode .equipment-frame{background:#dce8f5}
.light-mode .dash-lane{background:linear-gradient(180deg,rgba(210,222,234,.86),rgba(175,191,207,.92))}
.light-mode .road-scene{background:linear-gradient(115deg,transparent 0 28%,rgba(255,255,255,.55) 28% 29%,transparent 29% 68%,rgba(255,255,255,.5) 68% 69%,transparent 69%),repeating-linear-gradient(90deg,rgba(255,255,255,.18) 0 7px,transparent 7px 44px),linear-gradient(180deg,#a9b5c2,#7d8894)}
.light-mode .recent-panel table,.light-mode .gps-panel table,.light-mode .history-panel table{background:rgba(255,255,255,.32)}

/* Master dashboard visual alignment: keep layout, unify tone and component language. */
.ops-shell{background:radial-gradient(circle at 78% 0,rgba(22,131,255,.12),transparent 34%),linear-gradient(135deg,#020914 0%,#061528 54%,#020914 100%)}
.sidebar{padding:16px 14px;border-right-color:rgba(41,129,219,.34);background:linear-gradient(180deg,rgba(4,13,28,.98),rgba(4,20,40,.96))}
.brand{height:54px;margin-bottom:18px}.brand-mark{width:23px;height:23px;border-width:3px;box-shadow:0 0 8px rgba(22,131,255,.32)}.brand-mark::after{inset:5px}.brand strong{font-size:28px;letter-spacing:.02em}.brand span{color:#d7e6ff;font-size:14px}
.nav button{height:38px;border-radius:5px;color:#c9d7eb;font-size:14px;white-space:nowrap}.nav button i{color:#d9e7ff}.nav button.active,.nav button:hover{background:linear-gradient(90deg,rgba(22,103,219,.45),rgba(17,78,153,.23));box-shadow:inset 0 0 24px rgba(22,131,255,.18),inset 0 0 0 1px rgba(33,130,255,.7)}
.zone-card,.panel,.kpi-card,.center-toggle,.top-status span,.theme-toggle,.notification-popover{border-color:rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}
.topbar{height:56px;border-bottom-color:rgba(42,133,227,.28);background:rgba(2,9,20,.72)}
.center-toggle,.top-status span{height:34px;border-color:rgba(42,133,227,.45);background:linear-gradient(180deg,rgba(15,49,92,.78),rgba(6,24,50,.78))}
.theme-toggle{width:34px;height:34px;border-radius:50%;color:#f8fbff;background:linear-gradient(135deg,rgba(22,131,255,.36),rgba(52,211,153,.18));box-shadow:0 0 14px rgba(22,131,255,.18)}
.operator b,.topbar time{color:#e5efff}.operator small{color:#b8c7da}
.panel{padding:13px;border-radius:6px}.panel-head{min-height:28px;margin-bottom:11px;padding:0 0 0 10px;border-bottom:0;border-left:2px solid #1683ff}.panel-head h2{font-size:16px;font-weight:800}.panel-head button{color:#b9d3ef}
.kpi-card{min-height:96px;border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}
.kpi-card i{width:58px;height:58px;box-shadow:0 0 12px rgba(19,120,239,.24)}.kpi-card.purple i{background:linear-gradient(135deg,#aab0ff,#7a6cff)}.kpi-card.blue i{background:linear-gradient(135deg,#35b7ff,#1378ef)}.kpi-card.yellow i{background:linear-gradient(135deg,#ffe16e,#ffb928)}.kpi-card.navy i{background:linear-gradient(135deg,#2be7e4,#15a7ba)}
.kpi-card span{color:#e6f1ff;font-size:13px}.kpi-card strong{font-size:28px}.kpi-card em{font-size:12px;color:#5fe080}.kpi-card em.down{color:#ff704f}
.yolo-frame,.equipment-frame{border-color:rgba(42,133,227,.34);border-radius:6px}.dash-lane-title b,.dash-lane-title span,.fps-chip,.pill{border-radius:5px;background:rgba(5,18,37,.72)}
.status-grid article,.field-list article,.comm-card,.alert-row{border-color:rgba(42,133,227,.24);border-radius:5px;background:rgba(5,18,37,.52)}
th{color:#9fb2cb;background:rgba(26,46,73,.54)}td{color:#dce9f8}.state,.pay,.status-ok{border-radius:5px}
.gps-panel th,.gps-panel td{text-align:center}
.gps-panel td:first-child{display:flex;align-items:center;justify-content:center}
.zone-card h3{color:#eaf4ff}.zone-icon{box-shadow:0 0 12px rgba(76,223,102,.22)}
.ops-shell.light-mode{background:linear-gradient(135deg,#edf5ff 0%,#f8fbff 48%,#e8f2ff 100%)}
.light-mode .zone-card,.light-mode .panel,.light-mode .kpi-card,.light-mode .center-toggle,.light-mode .top-status span,.light-mode .theme-toggle,.light-mode .notification-popover{background:rgba(255,255,255,.82);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}
.light-mode .topbar{background:rgba(247,251,255,.78)}
.light-mode .center-toggle,.light-mode .top-status span{background:rgba(255,255,255,.82)}
.light-mode .panel-head{border-left-color:#1683ff}

/* Reduced color system: blue/cyan base, semantic colors only for states. */
.kpi-card.purple i,
.kpi-card.blue i,
.kpi-card.yellow i,
.kpi-card.navy i,
.equipment-card i,
.equipment-card.purple i,
.equipment-card.green i,
.equipment-card.teal i,
.equipment-card.mint i{
  background:linear-gradient(135deg,#35b7ff,#1378ef);
  box-shadow:0 0 12px rgba(19,120,239,.22);
}
.kpi-card.yellow i::before,
.kpi-card.navy i::before,
.kpi-card.purple i::before,
.kpi-card.blue i::before{color:#f8fbff;text-shadow:none}
.zone-icon,
.zone-icon.gps,
.zone-icon.lan,
.status-grid i{
  color:#eaf6ff;
  background:linear-gradient(135deg,#2493e8,#0c5da8);
  box-shadow:0 0 10px rgba(19,120,239,.18);
}
.dot.ok{background:#4cdf66}.dot.warn{background:#f5b84b}.dot.danger{background:#ef5a54}.dot.info{background:#2f8cff}
.top-status span .dot,
.live-chip .dot{box-shadow:none}
.status-grid strong,
.zone-card strong,
.equipment-card strong,
.equipment-card em,
.ok{color:#67df87!important}
.kpi-card em,
.state.ok,
.pay.ok{color:#67df87}
.row-dot{background:#4cdf66;box-shadow:0 0 8px rgba(76,223,102,.2)}
.row-dot.boundary,
.row-dot.warn{background:#f5a94d;box-shadow:0 0 8px rgba(245,169,77,.18)}
.row-dot.danger{background:#ef5a54;box-shadow:0 0 8px rgba(239,90,84,.18)}
.state.boundary,
.pay.boundary,
.state.warn,
.pay.warn{color:#f5b84b;background:rgba(245,184,75,.12)}
.state.danger{color:#ef6b65;background:rgba(239,90,84,.12)}
.pay.danger{color:#f5b84b;background:rgba(245,184,75,.12)}
.field-list .danger i,
.alert-row.warn i,
.notification-popover .danger i{background:#ef5a54;color:#fff}
.field-list .warn i,
.notification-popover .warn i{background:#f5b84b;color:#061120}
.field-list .info i,
.notification-popover .info i{background:#2f8cff;color:#fff}
.field-list b,
.field-list .warn b,
.field-list .info b,
.alert-row b,
.alert-row.info b{color:#dce9f8}
.field-list em{background:rgba(47,140,255,.12);color:#9fc9ff}
.plate-box{background:#1f8fff;color:#f8fbff;box-shadow:0 0 14px rgba(31,143,255,.28)}
.dash-lane.blue .plate-box{background:#1f8fff;box-shadow:0 0 14px rgba(31,143,255,.28)}
.dash-car{border-color:rgba(79,166,255,.75)}
.dash-car.silver{border-color:rgba(79,166,255,.75)}
.light-mode .zone-icon,
.light-mode .status-grid i{color:#fff;background:linear-gradient(135deg,#2f8cff,#176dc0)}
.light-mode .field-list b,
.light-mode .alert-row b{color:#21364d}
@media (max-width:1439px){.ops-shell{min-width:1280px}.dashboard-grid,.equipment-layout{grid-template-columns:1fr 1fr}.kpi-grid{grid-template-columns:repeat(4,minmax(220px,1fr))}}
</style>
