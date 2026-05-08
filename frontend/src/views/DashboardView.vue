<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { gpsApi } from '@/api/gps'
import { tollApi } from '@/api/toll'
import ocrVideoUrl from '@/videos/ocr_h264.mp4'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const nowText = ref('')
const activeFilter = ref('전체')
const selectedId = ref(2)
const showGpsPanel = ref(false)
const detailFocus = ref('split')
const showGpsZoneModal = ref(false)
const gpsTelemetry = ref([])
const tollHistory = ref([])
const tollDecision = ref(null)
let timer = null
let gpsTimer = null

const gpsZone = reactive({
  northWestLat: 37.4016,
  northWestLng: 127.1043,
  northEastLat: 37.4016,
  northEastLng: 127.1051,
  southEastLat: 37.4010,
  southEastLng: 127.1051,
  southWestLat: 37.4010,
  southWestLng: 127.1043
})

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
const activeGpsPoint = computed(() => {
  if (latestGps.value?.latitude != null && latestGps.value?.longitude != null) {
    return {
      lat: Number(latestGps.value.latitude),
      lng: Number(latestGps.value.longitude),
      source: latestGps.value.gpsDeviceId ?? 'GPS'
    }
  }
  return {
    lat: Number(selectedEvent.value.gps.lat),
    lng: Number(selectedEvent.value.gps.lng),
    source: 'DEMO'
  }
})
const zoneBounds = computed(() => {
  const lats = [gpsZone.northWestLat, gpsZone.northEastLat, gpsZone.southEastLat, gpsZone.southWestLat].map(Number)
  const lngs = [gpsZone.northWestLng, gpsZone.northEastLng, gpsZone.southEastLng, gpsZone.southWestLng].map(Number)
  return {
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
    minLng: Math.min(...lngs),
    maxLng: Math.max(...lngs),
    centerLat: (Math.min(...lats) + Math.max(...lats)) / 2,
    centerLng: (Math.min(...lngs) + Math.max(...lngs)) / 2
  }
})
const gpsAnalysis = computed(() => {
  const point = activeGpsPoint.value
  const bounds = zoneBounds.value
  const inside = point.lat >= bounds.minLat && point.lat <= bounds.maxLat && point.lng >= bounds.minLng && point.lng <= bounds.maxLng
  const centerDistanceM = distanceMeters(point.lat, point.lng, bounds.centerLat, bounds.centerLng)
  const northGap = Math.max(0, point.lat - bounds.maxLat)
  const southGap = Math.max(0, bounds.minLat - point.lat)
  const eastGap = Math.max(0, point.lng - bounds.maxLng)
  const westGap = Math.max(0, bounds.minLng - point.lng)
  const outsideMeters = inside ? 0 : Math.max(
    distanceMeters(bounds.maxLat, point.lng, point.lat - northGap, point.lng),
    distanceMeters(bounds.minLat, point.lng, point.lat + southGap, point.lng),
    distanceMeters(point.lat, bounds.maxLng, point.lat, point.lng - eastGap),
    distanceMeters(point.lat, bounds.minLng, point.lat, point.lng + westGap)
  )
  return { inside, centerDistanceM, outsideMeters }
})
const scatterPoints = computed(() => {
  const points = [
    { id: 'center', type: 'center', lat: zoneBounds.value.centerLat, lng: zoneBounds.value.centerLng, label: 'CENTER' },
    { id: 'gps', type: gpsAnalysis.value.inside ? 'actual inside' : 'actual outside', lat: activeGpsPoint.value.lat, lng: activeGpsPoint.value.lng, label: activeGpsPoint.value.source },
    { id: 'trail-1', type: 'trail', lat: activeGpsPoint.value.lat - 0.00008, lng: activeGpsPoint.value.lng - 0.0001, label: '' },
    { id: 'trail-2', type: 'trail', lat: activeGpsPoint.value.lat - 0.00004, lng: activeGpsPoint.value.lng - 0.00005, label: '' }
  ]
  return points.map((point) => ({ ...point, ...projectGpsPoint(point.lat, point.lng) }))
})

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

function toggleDetailFocus(mode) {
  detailFocus.value = detailFocus.value === mode ? 'split' : mode
  showGpsPanel.value = mode === 'gps'
}

function fmtTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleTimeString('ko-KR', { hour12: false })
}

function fmtCoord(value) {
  if (value === null || value === undefined) return 'NO_FIX'
  return Number(value ?? 0).toFixed(6)
}

function distanceMeters(lat1, lng1, lat2, lng2) {
  const latMeter = 111320
  const lngMeter = 111320 * Math.cos((lat1 * Math.PI) / 180)
  const dy = (lat1 - lat2) * latMeter
  const dx = (lng1 - lng2) * lngMeter
  return Math.sqrt(dx * dx + dy * dy)
}

function projectGpsPoint(lat, lng) {
  const bounds = zoneBounds.value
  const latRange = Math.max(0.000001, bounds.maxLat - bounds.minLat)
  const lngRange = Math.max(0.000001, bounds.maxLng - bounds.minLng)
  const x = 20 + ((lng - bounds.minLng) / lngRange) * 60
  const y = 78 - ((lat - bounds.minLat) / latRange) * 56
  return {
    x: Math.max(6, Math.min(94, x)),
    y: Math.max(6, Math.min(94, y))
  }
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
              <button @click="showGpsZoneModal = true">GPS 감지 영역 설정</button>
              <button :class="{ active: detailFocus === 'ocr' }" @click="toggleDetailFocus('ocr')">OCR 원본 보기</button>
              <button :class="{ active: detailFocus === 'gps' }" @click="toggleDetailFocus('gps')">GPS 경로 분석</button>
            </div>
          </div>

          <div class="ocr-gps-detail" :class="`focus-${detailFocus}`">
            <section class="detail-cell ocr-cell">
              <div class="cell-head">
                <span>OCR 원본 영상</span>
                <strong>{{ selectedEvent.plate }}</strong>
              </div>
              <div class="vehicle-stage">
                <video
                  class="ocr-video"
                  :src="ocrVideoUrl"
                  autoplay
                  loop
                  muted
                  controls
                  playsinline
                  preload="metadata"
                  aria-label="OCR vehicle recognition video"
                >
                  OCR video preview
                </video>
              </div>
            </section>

            <section class="detail-cell gps-cell">
              <div class="cell-head">
                <span>GPS 경로 분석</span>
                <strong :class="gpsAnalysis.inside ? 'success' : 'danger'">{{ gpsAnalysis.inside ? '통과' : '이탈' }}</strong>
              </div>
              <div class="gps-map">
                <div class="zone"></div>
                <span
                  v-for="point in scatterPoints"
                  :key="point.id"
                  class="gps-point"
                  :class="point.type"
                  :style="{ left: point.x + '%', top: point.y + '%' }"
                >
                  <em v-if="point.label">{{ point.label }}</em>
                </span>
              </div>
            </section>
          </div>

          <div class="detail-info-grid" :class="`focus-${detailFocus}`">
            <section class="info-card ocr-info">
              <h3>OCR 검출 정보</h3>
              <div class="detail-grid">
                <div><span>차량 번호</span><strong>{{ selectedEvent.plate }}</strong></div>
                <div><span>차로</span><strong>{{ selectedEvent.lane }}</strong></div>
                <div><span>검출 시간</span><strong>{{ selectedEvent.time }}</strong></div>
                <div><span>신뢰도</span><strong>{{ selectedEvent.conf }}%</strong></div>
                <div><span>상태</span><strong :class="statusClass(selectedEvent.status)">{{ selectedEvent.status }}</strong></div>
              </div>
            </section>

            <section class="info-card gps-info">
              <h3>GPS 정보</h3>
              <div class="gps-summary">
                <p><span>GPS 영역 통과 여부</span><strong :class="gpsAnalysis.inside ? 'success' : 'danger'">{{ gpsAnalysis.inside ? '통과' : '이탈' }}</strong></p>
                <p><span>단말 ID</span><strong>{{ latestGps?.gpsDeviceId ?? 'PICO2W-NEO7M-RC-01' }}</strong></p>
                <p><span>위도/경도</span><strong>{{ latestGps ? `${fmtCoord(latestGps.latitude)}, ${fmtCoord(latestGps.longitude)}` : `${selectedEvent.gps.lat}, ${selectedEvent.gps.lng}` }}</strong></p>
                <p><span>중심점 거리</span><strong>{{ gpsAnalysis.centerDistanceM.toFixed(1) }} m</strong></p>
                <p><span>영역 이탈 거리</span><strong>{{ gpsAnalysis.outsideMeters.toFixed(1) }} m</strong></p>
                <p><span>속도</span><strong>{{ latestGps?.speedKmh ?? selectedEvent.gps.speed }} km/h</strong></p>
                <p><span>통과 시간</span><strong>{{ selectedEvent.time }}</strong></p>
              </div>
            </section>
          </div>

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
              <td><span class="badge" :class="log.fixStatus === 'NO_FIX' ? 'warning' : 'success'">{{ log.fixStatus ?? log.fixType ?? 'FIXED' }}</span></td>
              <td>{{ log.satelliteCount ?? '-' }}</td>
              <td>{{ log.provider ?? 'pico2w-neo-7m' }}</td>
              <td><span class="signal"><i></i><i></i><i></i><i></i></span></td>
            </tr>
            <tr v-if="gpsTelemetry.length === 0"><td colspan="10">수신된 GPS 로그가 없습니다.</td></tr>
          </tbody>
        </table>
      </section>
    </main>

    <div v-if="showGpsZoneModal" class="modal-backdrop" @click.self="showGpsZoneModal = false">
      <section class="zone-modal glass">
        <div class="panel-head">
          <div>
            <p class="eyebrow">GPS DETECTION ZONE</p>
            <h2>GPS 감지 영역 좌표 설정</h2>
          </div>
          <button class="mini" @click="showGpsZoneModal = false">닫기</button>
        </div>
        <p class="modal-copy">4개 꼭지점 좌표를 입력하면 GPS 경로 분석의 고정 감지 영역과 산점도 판정이 즉시 갱신됩니다.</p>
        <div class="zone-input-grid">
          <label><span>좌상 위도</span><input v-model.number="gpsZone.northWestLat" type="number" step="0.000001" /></label>
          <label><span>좌상 경도</span><input v-model.number="gpsZone.northWestLng" type="number" step="0.000001" /></label>
          <label><span>우상 위도</span><input v-model.number="gpsZone.northEastLat" type="number" step="0.000001" /></label>
          <label><span>우상 경도</span><input v-model.number="gpsZone.northEastLng" type="number" step="0.000001" /></label>
          <label><span>우하 위도</span><input v-model.number="gpsZone.southEastLat" type="number" step="0.000001" /></label>
          <label><span>우하 경도</span><input v-model.number="gpsZone.southEastLng" type="number" step="0.000001" /></label>
          <label><span>좌하 위도</span><input v-model.number="gpsZone.southWestLat" type="number" step="0.000001" /></label>
          <label><span>좌하 경도</span><input v-model.number="gpsZone.southWestLng" type="number" step="0.000001" /></label>
        </div>
        <button class="primary wide" @click="showGpsZoneModal = false">감지 영역 적용</button>
      </section>
    </div>
  </div>
</template>

<style scoped>
.ops-dashboard{min-height:100vh;min-width:1180px;padding:24px;color:#e8f3ff;background:radial-gradient(circle at 18% 12%,rgba(58,190,245,.16),transparent 28%),linear-gradient(135deg,#030711,#07142a 46%,#030711)}
.glass{border:1px solid rgba(79,171,255,.22);border-radius:18px;background:linear-gradient(145deg,rgba(13,24,49,.78),rgba(8,16,35,.55));box-shadow:0 18px 60px rgba(0,0,0,.32);backdrop-filter:blur(18px)}
.ops-top{height:86px;display:flex;align-items:center;justify-content:space-between;padding:0 24px}.brand-block,.header-actions{display:flex;align-items:center;gap:16px}.brand-mark{width:48px;height:48px;display:grid;place-items:center;border-radius:14px;background:#38bef5;color:#06111f;font-weight:900}.eyebrow{margin:0 0 5px;color:#38bef5;font-size:11px;font-weight:800;letter-spacing:.22em}h1,h2{margin:0}.brand-block span{font-size:12px;color:#8ca5c8}.pill{display:inline-flex;align-items:center;gap:8px;padding:9px 12px;border:1px solid rgba(115,179,255,.2);border-radius:999px;background:rgba(7,15,31,.72);font-size:13px}.pill i,.live i{width:8px;height:8px;border-radius:50%;background:#33e6a1;box-shadow:0 0 16px #33e6a1}.ops-main{max-width:1540px;margin:22px auto 0}.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}.kpi{padding:20px}.kpi-icon{width:46px;height:46px;display:grid;place-items:center;border-radius:14px;background:rgba(56,190,245,.14);color:#38bef5;font-weight:900}.kpi-icon.green{color:#33e6a1}.kpi-icon.yellow{color:#ffd166}.kpi-icon.red{color:#ff5d6c}.kpi p,.kpi span{color:#8ca5c8;font-size:12px}.kpi strong{display:block;color:#fff;font-size:30px}.kpi em{font-size:12px;color:#33e6a1}.main-grid,.lower-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:18px;margin-top:18px}.panel{padding:20px;overflow:hidden}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}.live{display:inline-flex;align-items:center;gap:8px;color:#33e6a1;font-size:12px;font-weight:800}table{width:100%;border-collapse:collapse;background:rgba(2,9,22,.22);border-radius:14px;overflow:hidden}th,td{padding:13px 14px;border-bottom:1px solid rgba(137,181,230,.08);text-align:left;font-size:13px}th{color:#7294bd;font-size:11px;letter-spacing:.12em}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.selected{background:rgba(56,190,245,.14)}.plate{color:#fff;font-weight:900}.badge{display:inline-flex;min-width:68px;justify-content:center;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:900}.success{color:#33e6a1!important}.warning{color:#ffd166!important}.pending{color:#38bef5!important}.danger{color:#ff5d6c!important}.badge.success{background:rgba(51,230,161,.1)}.badge.warning{background:rgba(255,209,102,.12)}.badge.pending{background:rgba(56,190,245,.12)}button{border:0;color:inherit;font:inherit;cursor:pointer}.filter-row,.panel-actions{display:flex;gap:10px;margin-top:16px}.filter-row button,.panel-actions button,.mini,.home-btn{height:34px;padding:0 13px;border:1px solid rgba(79,171,255,.24);border-radius:10px;background:rgba(18,42,76,.78);font-size:12px}.filter-row button.active,.panel-actions button.active,.mini:hover,.home-btn:hover{background:rgba(56,190,245,.18);box-shadow:0 0 18px rgba(56,190,245,.22)}.vehicle-stage{position:relative;height:264px;overflow:hidden;border:1px solid rgba(79,171,255,.16);border-radius:16px;background:radial-gradient(circle at 50% 42%,rgba(56,190,245,.16),transparent 34%),#07101f}.ocr-video{display:block;width:100%;height:100%;border-radius:15px;background:#020916;object-fit:contain}.detail-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:14px}.detail-grid div,.settlement div,.gps-summary p{padding:12px;border:1px solid rgba(79,171,255,.12);border-radius:12px;background:rgba(3,10,24,.42)}.detail-grid span,.settlement span{display:block;margin-bottom:6px;color:#8ca5c8;font-size:11px}.gps-panel{display:grid;grid-template-columns:1fr .9fr;gap:14px;margin-top:14px}.gps-map{position:relative;min-height:180px;border:1px solid rgba(56,190,245,.2);border-radius:14px;background:linear-gradient(rgba(70,125,255,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(70,125,255,.1) 1px,transparent 1px),#061326;background-size:24px 24px}.zone{position:absolute;left:18%;top:18%;width:64%;height:58%;border:2px dashed rgba(51,230,161,.68);border-radius:50%}.gps-point{position:absolute;width:8px;height:8px;border-radius:50%;background:#38bef5;box-shadow:0 0 16px #38bef5}.gps-car{position:absolute;left:62%;top:42%;width:32px;height:32px;display:grid;place-items:center;border-radius:50%;background:#33e6a1;color:#02100b;font-size:11px;font-weight:900}.gps-summary{display:grid;gap:8px}.gps-summary p{display:flex;justify-content:space-between;margin:0;font-size:12px}.primary{height:40px;margin-top:14px;border-radius:10px;background:#1b3be8;font-weight:800}.wide{width:100%}.decision{font-size:13px;color:#c6dcf7}.money{font-size:24px}.settlement{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.bars{display:grid;gap:12px;margin-top:18px}.bars div{display:grid;grid-template-columns:72px 1fr 54px;align-items:center;gap:12px;font-size:12px}.bars i{height:12px;border-radius:999px;background:rgba(114,148,189,.14);overflow:hidden}.bars b{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#4f7dff,#38bef5)}.signal{display:inline-flex;align-items:end;gap:3px;height:16px}.signal i{width:4px;border-radius:999px;background:#33e6a1}.signal i:nth-child(1){height:5px}.signal i:nth-child(2){height:8px}.signal i:nth-child(3){height:12px}.signal i:nth-child(4){height:16px}
.ops-main{max-width:none;width:100%;margin:22px 0 0}
.zone-config{margin-top:18px}
.zone-input-grid{display:grid;grid-template-columns:repeat(4,
