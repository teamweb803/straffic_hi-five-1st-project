<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { gpsApi } from '@/api/gps'
import { tollApi } from '@/api/toll'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const nowText = ref('')
const activeFilter = ref('전체')
const selectedId = ref(2)
const showGpsPanel = ref(false)
const gpsTelemetry = ref([])
const tollHistory = ref([])
const tollDecision = ref(null)
let timer = null
let gpsTimer = null

const events = ref([
  { id: 1, time: '10:21:03', lane: '1', plate: '12가3456', conf: 97, status: '저장완료', gps: { lat: '37.401224', lng: '127.104582', speed: '7.8' } },
  { id: 2, time: '10:22:15', lane: '2', plate: '33나9029', conf: 62, status: '검수필요', gps: { lat: '37.401319', lng: '127.104691', speed: '5.4' } },
  { id: 3, time: '10:23:07', lane: '1', plate: '48다7720', conf: 91, status: '정산대기', gps: { lat: '37.401428', lng: '127.104803', speed: '6.1' } },
  { id: 4, time: '10:23:42', lane: '3', plate: '77가0033', conf: 58, status: '검수필요', gps: { lat: '37.401512', lng: '127.104956', speed: '4.6' } }
])

const selectedEvent = computed(() => events.value.find((event) => event.id === selectedId.value) ?? events.value[0])
const dashboardLabel = computed(() => route.query.center ?? auth.assignedDashboardId ?? 'RC-DEMO-CENTER')
const filteredEvents = computed(() => {
  if (activeFilter.value === '전체') return events.value
  if (activeFilter.value === '정산완료') return events.value.filter((event) => event.status === '저장완료')
  return events.value.filter((event) => event.status === activeFilter.value)
})
const latestGps = computed(() => gpsTelemetry.value[0] ?? null)

const kpiCards = [
  { icon: 'IN', title: '오늘 통행 수', value: '1,248', caption: '전일 대비 증가', delta: '+8.4%', tone: 'blue' },
  { icon: '₩', title: '미정산 건수', value: '36', caption: '정산 대기 이벤트', delta: '-3건', tone: 'red' },
  { icon: 'RV', title: '검수 대기', value: '12', caption: 'OCR 저신뢰 케이스', delta: '+2건', tone: 'yellow' },
  { icon: 'GPS', title: 'GPS 수신 단말', value: '3', caption: '최근 30초 활성', delta: '정상', tone: 'green' },
  { icon: 'OK', title: '시스템 상태', value: '정상', caption: 'Spring/DB 연결 양호', delta: '99.9%', tone: 'green' }
]

const reviewRows = [
  { plate: '33나9029', reason: 'OCR 저신뢰', conf: 62, time: '00:01:12' },
  { plate: '77가0033', reason: '번호판 흐림', conf: 58, time: '00:03:48' },
  { plate: '25마4499', reason: 'GPS 매칭 대기', conf: 66, time: '00:05:21' }
]

const laneStats = [
  { name: 'LANE 1', count: 486, rate: 92 },
  { name: 'LANE 2', count: 392, rate: 74 },
  { name: 'LANE 3', count: 255, rate: 48 },
  { name: 'LANE 4', count: 115, rate: 22 }
]

function updateTime() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function statusClass(status) {
  if (['저장완료', '정상', '통과'].includes(status)) return 'success'
  if (status === '검수필요') return 'warning'
  if (status === '정산대기') return 'pending'
  return 'danger'
}

function selectEvent(event) {
  selectedId.value = event.id
  showGpsPanel.value = event.status === '검수필요'
}

function fmtTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleTimeString('ko-KR', { hour12: false })
}

function fmtCoord(value) {
  return Number(value ?? 0).toFixed(6)
}

async function fetchGpsTelemetry() {
  const { data } = await gpsApi.latest()
  gpsTelemetry.value = data.map((telemetry) => ({
    ...telemetry,
    capturedAt: normalizeDate(telemetry.capturedAt)
  }))
}

async function fetchTollHistory() {
  const { data } = await tollApi.latestHistory()
  tollHistory.value = data
}

async function simulatePlateRecognition() {
  const latest = latestGps.value
  if (!latest) {
    tollDecision.value = { charged: false, reason: '먼저 GPS 로그가 수신되어야 합니다.' }
    return
  }
  const { data } = await tollApi.recognizePlate({
    plateNumber: selectedEvent.value.plate,
    gpsDeviceId: latest.gpsDeviceId,
    laneId: latest.laneId ?? 'RC-DEMO-LANE',
    edgeNodeId: latest.edgeNodeId ?? 'EDGE-RC-01',
    plateConfidence: selectedEvent.value.conf / 100
  })
  tollDecision.value = data
  await fetchTollHistory()
}

function normalizeDate(raw) {
  if (!raw) return null
  if (typeof raw === 'string') return raw
  if (Array.isArray(raw)) {
    const [year, month, day, hour = 0, minute = 0, second = 0] = raw
    return new Date(year, month - 1, day, hour, minute, second).toISOString()
  }
  return raw
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  fetchGpsTelemetry().catch(() => {})
  fetchTollHistory().catch(() => {})
  gpsTimer = setInterval(() => {
    fetchGpsTelemetry().catch(() => {})
    fetchTollHistory().catch(() => {})
  }, 5000)
})

onBeforeUnmount(() => {
  clearInterval(timer)
  clearInterval(gpsTimer)
})
</script>

<template>
  <div class="ops-dashboard">
    <header class="ops-top glass">
      <div class="brand-block">
        <div class="brand-mark">H5</div>
        <div>
          <p class="eyebrow">HI-FIVE</p>
          <h1>Admin Dashboard</h1>
          <span>{{ dashboardLabel }} 관제센터</span>
        </div>
      </div>
      <div class="header-actions">
        <span class="pill">{{ nowText }}</span>
        <span class="pill ok"><i></i>서버 상태: 정상</span>
        <span class="pill">관리자: <strong>{{ auth.member?.memberName }}</strong></span>
        <button class="home-btn" @click="router.push('/')">홈으로</button>
      </div>
    </header>

    <main class="ops-main">
      <section class="kpi-grid">
        <article v-for="card in kpiCards" :key="card.title" class="kpi glass">
          <div class="kpi-icon" :class="card.tone">{{ card.icon }}</div>
          <p>{{ card.title }}</p>
          <strong>{{ card.value }}</strong>
          <span>{{ card.caption }}</span>
          <em>{{ card.delta }}</em>
        </article>
      </section>

      <section class="main-grid">
        <article class="glass panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">LIVE EVENTS</p>
              <h2>실시간 통행 이벤트</h2>
            </div>
            <span class="live"><i></i>LIVE</span>
          </div>
          <table>
            <thead>
              <tr><th>TIME</th><th>LANE</th><th>PLATE</th><th>CONF</th><th>STATUS</th></tr>
            </thead>
            <tbody>
              <tr v-for="event in filteredEvents" :key="event.id" :class="{ selected: selectedEvent.id === event.id }" @click="selectEvent(event)">
                <td>{{ event.time }}</td>
                <td>{{ event.lane }}</td>
                <td class="plate">{{ event.plate }}</td>
                <td>{{ event.conf }}%</td>
                <td><span class="badge" :class="statusClass(event.status)">{{ event.status }}</span></td>
              </tr>
            </tbody>
          </table>
          <div class="filter-row">
            <button v-for="filter in ['전체', '검수필요', '정산완료']" :key="filter" :class="{ active: activeFilter === filter }" @click="activeFilter = filter">{{ filter }}</button>
          </div>
        </article>

        <article class="glass panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">OCR DETAIL</p>
              <h2>OCR 차량 검출 상세</h2>
            </div>
            <div class="panel-actions">
              <button :class="{ active: !showGpsPanel }" @click="showGpsPanel = false">OCR 원본 보기</button>
              <button :class="{ active: showGpsPanel }" @click="showGpsPanel = true">GPS 경로 분석</button>
            </div>
          </div>
          <div class="vehicle-stage">
            <div class="vehicle-art"><span>{{ selectedEvent.plate }}</span></div>
            <div class="bbox"><span>{{ selectedEvent.plate }}</span><em>{{ selectedEvent.conf }}%</em></div>
          </div>
          <div class="detail-grid">
            <div><span>차량 번호</span><strong>{{ selectedEvent.plate }}</strong></div>
            <div><span>차로</span><strong>{{ selectedEvent.lane }}</strong></div>
            <div><span>검출 시간</span><strong>{{ selectedEvent.time }}</strong></div>
            <div><span>신뢰도</span><strong>{{ selectedEvent.conf }}%</strong></div>
            <div><span>상태</span><strong :class="statusClass(selectedEvent.status)">{{ selectedEvent.status }}</strong></div>
          </div>
          <section v-if="showGpsPanel" class="gps-panel">
            <div class="gps-map">
              <div class="zone"></div>
              <span v-for="point in [18, 32, 48, 64, 78]" :key="point" class="gps-point" :style="{ left: point + '%', top: 74 - point / 2 + '%' }"></span>
              <div class="gps-car">RC</div>
            </div>
            <div class="gps-summary">
              <p><span>GPS 영역 통과 여부</span><strong class="success">통과</strong></p>
              <p><span>단말 ID</span><strong>{{ latestGps?.gpsDeviceId ?? 'PICO2W-NEO7M-RC-01' }}</strong></p>
              <p><span>위도/경도</span><strong>{{ latestGps ? `${fmtCoord(latestGps.latitude)}, ${fmtCoord(latestGps.longitude)}` : `${selectedEvent.gps.lat}, ${selectedEvent.gps.lng}` }}</strong></p>
              <p><span>속도</span><strong>{{ latestGps?.speedKmh ?? selectedEvent.gps.speed }} km/h</strong></p>
              <p><span>통과 시간</span><strong>{{ selectedEvent.time }}</strong></p>
            </div>
          </section>
          <button class="primary wide" @click="simulatePlateRecognition">번호판+GPS 결제 판정</button>
          <p v-if="tollDecision" class="decision">{{ tollDecision.charged ? '결제 인식됨' : '결제 미생성' }} - {{ tollDecision.reason }}</p>
        </article>
      </section>

      <section class="lower-grid">
        <article class="glass panel">
          <div class="panel-head"><h2>검수 대기 목록</h2><span class="pill">12건 대기</span></div>
          <table>
            <thead><tr><th>PLATE</th><th>사유</th><th>신뢰도</th><th>처리 시간</th><th>액션</th></tr></thead>
            <tbody>
              <tr v-for="item in reviewRows" :key="item.plate">
                <td class="plate">{{ item.plate }}</td><td>{{ item.reason }}</td><td class="warning">{{ item.conf }}%</td><td>{{ item.time }}</td><td><button class="mini">수정</button></td>
              </tr>
            </tbody>
          </table>
        </article>
        <article class="glass panel">
          <div class="panel-head"><h2>요금/정산 요약</h2><strong class="money">₩2,450,800</strong></div>
          <div class="settlement"><div><span>미납</span><strong class="danger">₩84,500</strong></div><div><span>결제완료</span><strong class="success">₩2,180,300</strong></div><div><span>보류</span><strong class="warning">₩186,000</strong></div></div>
          <div class="bars">
            <div v-for="lane in laneStats" :key="lane.name"><span>{{ lane.name }}</span><i><b :style="{ width: lane.rate + '%' }"></b></i><strong>{{ lane.count }}</strong></div>
          </div>
        </article>
      </section>

      <section class="glass panel">
        <div class="panel-head"><h2>GPS Telemetry 로그</h2><span class="pill ok"><i></i>실시간 저장 중</span></div>
        <table>
          <thead><tr><th>TIME</th><th>DEVICE</th><th>LAT/LNG</th><th>SPEED</th><th>HEADING</th><th>ALT</th><th>FIX</th><th>SAT</th><th>PROVIDER</th><th>SIGNAL</th></tr></thead>
          <tbody>
            <tr v-for="log in gpsTelemetry.slice(0, 8)" :key="log.id">
              <td>{{ fmtTime(log.capturedAt) }}</td>
              <td>{{ log.gpsDeviceId }}</td>
              <td>{{ fmtCoord(log.latitude) }}, {{ fmtCoord(log.longitude) }}</td>
              <td>{{ Number(log.speedKmh ?? 0).toFixed(1) }} km/h</td>
              <td>{{ log.heading ?? '-' }}</td>
              <td>{{ log.altitudeM ?? '-' }}</td>
              <td><span class="badge success">{{ log.fixType ?? '3D' }}</span></td>
              <td>{{ log.satelliteCount ?? '-' }}</td>
              <td>{{ log.provider ?? 'pico2w-neo-7m' }}</td>
              <td><span class="signal"><i></i><i></i><i></i><i></i></span></td>
            </tr>
            <tr v-if="gpsTelemetry.length === 0"><td colspan="10">수신된 GPS 로그가 없습니다.</td></tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</template>

<style scoped>
.ops-dashboard{min-height:100vh;min-width:1180px;padding:24px;color:#e8f3ff;background:radial-gradient(circle at 18% 12%,rgba(58,190,245,.16),transparent 28%),linear-gradient(135deg,#030711,#07142a 46%,#030711)}
.glass{border:1px solid rgba(79,171,255,.22);border-radius:18px;background:linear-gradient(145deg,rgba(13,24,49,.78),rgba(8,16,35,.55));box-shadow:0 18px 60px rgba(0,0,0,.32);backdrop-filter:blur(18px)}
.ops-top{height:86px;display:flex;align-items:center;justify-content:space-between;padding:0 24px}.brand-block,.header-actions{display:flex;align-items:center;gap:16px}.brand-mark{width:48px;height:48px;display:grid;place-items:center;border-radius:14px;background:#38bef5;color:#06111f;font-weight:900}.eyebrow{margin:0 0 5px;color:#38bef5;font-size:11px;font-weight:800;letter-spacing:.22em}h1,h2{margin:0}.brand-block span{font-size:12px;color:#8ca5c8}.pill{display:inline-flex;align-items:center;gap:8px;padding:9px 12px;border:1px solid rgba(115,179,255,.2);border-radius:999px;background:rgba(7,15,31,.72);font-size:13px}.pill i,.live i{width:8px;height:8px;border-radius:50%;background:#33e6a1;box-shadow:0 0 16px #33e6a1}.ops-main{max-width:1540px;margin:22px auto 0}.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}.kpi{padding:20px}.kpi-icon{width:46px;height:46px;display:grid;place-items:center;border-radius:14px;background:rgba(56,190,245,.14);color:#38bef5;font-weight:900}.kpi-icon.green{color:#33e6a1}.kpi-icon.yellow{color:#ffd166}.kpi-icon.red{color:#ff5d6c}.kpi p,.kpi span{color:#8ca5c8;font-size:12px}.kpi strong{display:block;color:#fff;font-size:30px}.kpi em{font-size:12px;color:#33e6a1}.main-grid,.lower-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:18px;margin-top:18px}.panel{padding:20px;overflow:hidden}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}.live{display:inline-flex;align-items:center;gap:8px;color:#33e6a1;font-size:12px;font-weight:800}table{width:100%;border-collapse:collapse;background:rgba(2,9,22,.22);border-radius:14px;overflow:hidden}th,td{padding:13px 14px;border-bottom:1px solid rgba(137,181,230,.08);text-align:left;font-size:13px}th{color:#7294bd;font-size:11px;letter-spacing:.12em}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.selected{background:rgba(56,190,245,.14)}.plate{color:#fff;font-weight:900}.badge{display:inline-flex;min-width:68px;justify-content:center;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:900}.success{color:#33e6a1!important}.warning{color:#ffd166!important}.pending{color:#38bef5!important}.danger{color:#ff5d6c!important}.badge.success{background:rgba(51,230,161,.1)}.badge.warning{background:rgba(255,209,102,.12)}.badge.pending{background:rgba(56,190,245,.12)}button{border:0;color:inherit;font:inherit;cursor:pointer}.filter-row,.panel-actions{display:flex;gap:10px;margin-top:16px}.filter-row button,.panel-actions button,.mini,.home-btn{height:34px;padding:0 13px;border:1px solid rgba(79,171,255,.24);border-radius:10px;background:rgba(18,42,76,.78);font-size:12px}.filter-row button.active,.panel-actions button.active,.mini:hover,.home-btn:hover{background:rgba(56,190,245,.18);box-shadow:0 0 18px rgba(56,190,245,.22)}.vehicle-stage{position:relative;height:264px;border:1px solid rgba(79,171,255,.16);border-radius:16px;background:radial-gradient(circle at 50% 42%,rgba(56,190,245,.16),transparent 34%),#07101f}.vehicle-art{position:absolute;left:50%;bottom:42px;width:310px;height:150px;transform:translateX(-50%);border-radius:52px 52px 28px 28px;background:linear-gradient(180deg,#1d3764,#09162b);border:1px solid rgba(109,194,255,.4)}.vehicle-art span{position:absolute;left:50%;bottom:18px;transform:translateX(-50%);padding:4px 12px;border-radius:4px;background:#e8f0f7;color:#09111e;font-size:12px;font-weight:900}.bbox{position:absolute;left:50%;bottom:54px;width:128px;height:44px;transform:translateX(-50%);border:2px solid #33e6a1;box-shadow:0 0 24px rgba(51,230,161,.4)}.bbox span,.bbox em{position:absolute;left:-2px;padding:2px 6px;background:#33e6a1;color:#03100b;font-size:11px;font-style:normal;font-weight:900}.bbox span{top:-24px}.bbox em{right:-2px;left:auto;bottom:-23px}.detail-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:14px}.detail-grid div,.settlement div,.gps-summary p{padding:12px;border:1px solid rgba(79,171,255,.12);border-radius:12px;background:rgba(3,10,24,.42)}.detail-grid span,.settlement span{display:block;margin-bottom:6px;color:#8ca5c8;font-size:11px}.gps-panel{display:grid;grid-template-columns:1fr .9fr;gap:14px;margin-top:14px}.gps-map{position:relative;min-height:180px;border:1px solid rgba(56,190,245,.2);border-radius:14px;background:linear-gradient(rgba(70,125,255,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(70,125,255,.1) 1px,transparent 1px),#061326;background-size:24px 24px}.zone{position:absolute;left:18%;top:18%;width:64%;height:58%;border:2px dashed rgba(51,230,161,.68);border-radius:50%}.gps-point{position:absolute;width:8px;height:8px;border-radius:50%;background:#38bef5;box-shadow:0 0 16px #38bef5}.gps-car{position:absolute;left:62%;top:42%;width:32px;height:32px;display:grid;place-items:center;border-radius:50%;background:#33e6a1;color:#02100b;font-size:11px;font-weight:900}.gps-summary{display:grid;gap:8px}.gps-summary p{display:flex;justify-content:space-between;margin:0;font-size:12px}.primary{height:40px;margin-top:14px;border-radius:10px;background:#1b3be8;font-weight:800}.wide{width:100%}.decision{font-size:13px;color:#c6dcf7}.money{font-size:24px}.settlement{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.bars{display:grid;gap:12px;margin-top:18px}.bars div{display:grid;grid-template-columns:72px 1fr 54px;align-items:center;gap:12px;font-size:12px}.bars i{height:12px;border-radius:999px;background:rgba(114,148,189,.14);overflow:hidden}.bars b{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#4f7dff,#38bef5)}.signal{display:inline-flex;align-items:end;gap:3px;height:16px}.signal i{width:4px;border-radius:999px;background:#33e6a1}.signal i:nth-child(1){height:5px}.signal i:nth-child(2){height:8px}.signal i:nth-child(3){height:12px}.signal i:nth-child(4){height:16px}
</style>
