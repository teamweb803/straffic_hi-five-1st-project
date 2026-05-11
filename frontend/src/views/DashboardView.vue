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
const THEME_STORAGE_KEY = 'hifive.dashboard.theme'
const nowText = ref('')
const themeMode = ref(localStorage.getItem(THEME_STORAGE_KEY) || 'dark')
const activeFilter = ref('전체')
const selectedEventId = ref(100)
const selectedLane = ref(1)
const showGpsZoneModal = ref(false)
const gpsTelemetry = ref([])
const tollHistory = ref([])
const tollDecision = ref(null)
const activeMenu = ref('실시간 관제')
const opsSubOpen = ref(true)
const detailTab = ref('plate') // 'plate' | 'gps'
const selectedSubLane = ref(1)
const showReviewModal = ref(false)
const reviewTarget = ref(null)
const reviewAction = ref('확인완료')
const reviewMemo = ref('')
const showEventModal = ref(false)
const eventModalTarget = ref(null)
const isSettingsEditing = ref(false)
const operatorSettings = reactive({
  dashboardId: 'RC-DEMO-CENTER',
  laneCount: 2,
  gpsDeviceId: 'PICO2W-NEO7M-RC-01',
  ocrConfidence: 70,
  reviewThreshold: 65,
  storagePolicy: 'PostgreSQL 저장'
})
const isLightMode = computed(() => themeMode.value === 'light')

function toggleThemeMode() {
  themeMode.value = isLightMode.value ? 'dark' : 'light'
  localStorage.setItem(THEME_STORAGE_KEY, themeMode.value)
}

// ▼ 편집 모드 + 위젯
const editMode = ref(false)
const draggedIdx = ref(null)
const widgets = ref([
  { id: 'kpi',          title: 'KPI 요약',                span: 12 },
  { id: 'frame',        title: 'YOLO 입력 프레임',          span: 7 },
  { id: 'gps',          title: 'GPS Telemetry 실시간 로그',  span: 5 },
  { id: 'stats-traffic',title: '금일 통행량 (시간대별)',     span: 6 },
  { id: 'stats-settle', title: '누적 정산 금액',            span: 3 },
  { id: 'stats-esg',    title: 'ESG 탄소 저감량',          span: 3 },
  { id: 'events',       title: '실시간 통행 이벤트',         span: 7 },
  { id: 'detail',       title: '차량 상세 (번호판 / GPS)',   span: 5 },
  { id: 'lanes',        title: '차로별 실시간 상태',         span: 12 },
  { id: 'anomaly',      title: '이상징후 · 검수 큐',         span: 12 }
])
const defaultLayout = JSON.parse(JSON.stringify(widgets.value))

let timer = null
let gpsTimer = null

const gpsZone = reactive({
  northWestLat: 37.4016, northWestLng: 127.1043,
  northEastLat: 37.4016, northEastLng: 127.1051,
  southEastLat: 37.4010, southEastLng: 127.1051,
  southWestLat: 37.4010, southWestLng: 127.1043
})

// ▼ 30건 더미 (각 이벤트마다 Front/Rear/Fusion + GPS 좌표)
function makeEvent(id, hour, min, sec, lane, plate, conf, status, dir, src, lat, lng, spd) {
  const time = `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
  const fconf = Math.max(40, conf - Math.floor(Math.random() * 6))
  const rconf = Math.max(40, conf - Math.floor(Math.random() * 6))
  const top = lane === 1 ? 24 : 64
  return {
    id, time, lane, plate, conf, status, direction: dir, source: src,
    front: { plate, conf: fconf, ts: `${time}.${String(Math.floor(Math.random()*999)).padStart(3,'0')}` },
    rear:  { plate, conf: rconf, ts: `${time}.${String(Math.floor(Math.random()*999)).padStart(3,'0')}` },
    final: { plate, conf, agreement: src.includes('vote') ? 0.66 : 1.0, source: src },
    bbox: { top, left: 28 + Math.floor(Math.random() * 6), width: 36, height: 18 },
    gps: { lat, lng, speed: spd }
  }
}
const PLATE_POOL = ['12가3456','85라1212','48다7720','33나9029','24허5567','77가0033','92바4421','65사1188','11아2299','48자5566','37차7788','50카9911','83타2244','14파6677','29하8855','67거1234','40너5678','72더9012','15러3456','88머7890','23버1357','56서2468','34어3579','47저4680','90처5791','12커6802','78터7913','56퍼8024','41루2580','69무1357','82구9753','27수8642','13오7531','46루1029','75버3847','38나8264','64다4750','19로6928','51마3186','97보5274']
const STATUS_POOL = [
  { s: '저장완료', confR: [88, 98], src: 'FRONT+REAR' },
  { s: '저장완료', confR: [82, 95], src: 'REAR' },
  { s: '저장완료', confR: [80, 93], src: 'FRONT' },
  { s: '정산대기', confR: [78, 92], src: 'REAR' },
  { s: '정산대기', confR: [70, 88], src: 'FRONT' },
  { s: '검수필요', confR: [55, 68], src: 'FRONT (vote)' }
]
function generateEvents(n) {
  const out = []
  let h = 8, m = 0, s = 0
  for (let i = 1; i <= n; i++) {
    s += 18 + Math.floor(Math.random() * 30)
    while (s >= 60) { m++; s -= 60 }
    while (m >= 60) { h++; m -= 60 }
    if (h >= 24) h = 23
    const plate = PLATE_POOL[(i - 1) % PLATE_POOL.length]
    const lane = (i % 2) + 1
    const sp = STATUS_POOL[i % STATUS_POOL.length]
    const conf = sp.confR[0] + Math.floor(Math.random() * (sp.confR[1] - sp.confR[0] + 1))
    const dir = i % 4 === 0 ? 'OUT' : 'IN'
    const lat = 37.401224 + i * 0.000016
    const lng = 127.104582 + i * 0.000020
    const spd = parseFloat((4.5 + Math.random() * 4.2).toFixed(1))
    out.push(makeEvent(i, h, m, s, lane, plate, conf, sp.s, dir, sp.src, lat, lng, spd))
  }
  return out.reverse() // 최신이 위
}
const events = ref(generateEvents(100))
const selectedEvent = computed(() => events.value.find((e) => e.id === selectedEventId.value) ?? events.value[0])

const dashboardLabel = computed(() => route.query.center ?? auth.assignedDashboardId ?? 'RC-DEMO-CENTER')
const filteredEvents = computed(() => {
  if (activeFilter.value === '전체') return events.value
  if (activeFilter.value === '정산완료') return events.value.filter((e) => e.status === '저장완료')
  return events.value.filter((e) => e.status === activeFilter.value)
})
const latestGps = computed(() => gpsTelemetry.value[0] ?? null)
const activeGpsPoint = computed(() => {
  if (latestGps.value?.latitude != null && latestGps.value?.longitude != null) {
    return { lat: Number(latestGps.value.latitude), lng: Number(latestGps.value.longitude), source: latestGps.value.gpsDeviceId ?? 'GPS' }
  }
  return { lat: Number(selectedEvent.value.gps.lat), lng: Number(selectedEvent.value.gps.lng), source: 'EVENT' }
})
const zoneBounds = computed(() => {
  const lats = [gpsZone.northWestLat, gpsZone.northEastLat, gpsZone.southEastLat, gpsZone.southWestLat].map(Number)
  const lngs = [gpsZone.northWestLng, gpsZone.northEastLng, gpsZone.southEastLng, gpsZone.southWestLng].map(Number)
  return {
    minLat: Math.min(...lats), maxLat: Math.max(...lats),
    minLng: Math.min(...lngs), maxLng: Math.max(...lngs),
    centerLat: (Math.min(...lats) + Math.max(...lats)) / 2,
    centerLng: (Math.min(...lngs) + Math.max(...lngs)) / 2
  }
})
const gpsAnalysis = computed(() => {
  const point = activeGpsPoint.value
  const bounds = zoneBounds.value
  const inside = point.lat >= bounds.minLat && point.lat <= bounds.maxLat && point.lng >= bounds.minLng && point.lng <= bounds.maxLng
  const centerDistanceM = distanceMeters(point.lat, point.lng, bounds.centerLat, bounds.centerLng)
  return { inside, centerDistanceM }
})
const scatterPoints = computed(() => {
  const points = [
    { id: 'center', type: 'center', lat: zoneBounds.value.centerLat, lng: zoneBounds.value.centerLng, label: 'CENTER' },
    { id: 'gps', type: gpsAnalysis.value.inside ? 'actual inside' : 'actual outside', lat: activeGpsPoint.value.lat, lng: activeGpsPoint.value.lng, label: activeGpsPoint.value.source },
    { id: 'trail-1', type: 'trail', lat: activeGpsPoint.value.lat - 0.00008, lng: activeGpsPoint.value.lng - 0.0001, label: '' },
    { id: 'trail-2', type: 'trail', lat: activeGpsPoint.value.lat - 0.00004, lng: activeGpsPoint.value.lng - 0.00005, label: '' }
  ]
  return points.map((p) => ({ ...p, ...projectGpsPoint(p.lat, p.lng) }))
})
// 선택 차량 GPS 산점도
const selectedGpsScatter = computed(() => {
  const e = selectedEvent.value
  const pt = { lat: Number(e.gps.lat), lng: Number(e.gps.lng) }
  const bounds = zoneBounds.value
  const inside = pt.lat >= bounds.minLat && pt.lat <= bounds.maxLat && pt.lng >= bounds.minLng && pt.lng <= bounds.maxLng
  const points = [
    { id: 'center', type: 'center', lat: bounds.centerLat, lng: bounds.centerLng, label: 'CENTER' },
    { id: 'event', type: inside ? 'actual inside' : 'actual outside', lat: pt.lat, lng: pt.lng, label: e.plate },
    { id: 't1', type: 'trail', lat: pt.lat - 0.00008, lng: pt.lng - 0.0001, label: '' },
    { id: 't2', type: 'trail', lat: pt.lat - 0.00004, lng: pt.lng - 0.00005, label: '' }
  ]
  return { inside, points: points.map((p) => ({ ...p, ...projectGpsPoint(p.lat, p.lng) })) }
})
const laneDetections = computed(() => [1, 2].map((lane) => {
  const laneEvents = events.value.filter((event) => event.lane === lane)
  const latest = laneEvents[0] ?? selectedEvent.value
  return {
    lane,
    title: lane === 1 ? 'LANE 1 상단 차선' : 'LANE 2 하단 차선',
    latest,
    count: laneEvents.length,
    reviewCount: laneEvents.filter((event) => event.status === '검수필요').length,
    avgConf: Math.round(laneEvents.reduce((sum, event) => sum + event.conf, 0) / Math.max(1, laneEvents.length))
  }
}))
const activeLaneDetection = computed(() => laneDetections.value.find((lane) => lane.lane === selectedSubLane.value) ?? laneDetections.value[0])
const eventModalGpsScatter = computed(() => {
  const event = eventModalTarget.value ?? selectedEvent.value
  const pt = { lat: Number(event.gps.lat), lng: Number(event.gps.lng) }
  const bounds = zoneBounds.value
  const inside = pt.lat >= bounds.minLat && pt.lat <= bounds.maxLat && pt.lng >= bounds.minLng && pt.lng <= bounds.maxLng
  const points = [
    { id: 'center', type: 'center', lat: bounds.centerLat, lng: bounds.centerLng, label: 'CENTER' },
    { id: 'event', type: inside ? 'actual inside' : 'actual outside', lat: pt.lat, lng: pt.lng, label: event.plate },
    { id: 'trail-1', type: 'trail', lat: pt.lat - 0.00008, lng: pt.lng - 0.0001, label: '' },
    { id: 'trail-2', type: 'trail', lat: pt.lat - 0.00004, lng: pt.lng - 0.00005, label: '' }
  ]
  return { inside, points: points.map((p) => ({ ...p, ...projectGpsPoint(p.lat, p.lng) })) }
})

const kpiCards = [
  { title: '당일 통행량',       value: '1,248',        delta: '전일 대비 ▲ 8.4%',  tone: 'purple', icon: 'flow',    deltaTone: 'up' },
  { title: '총 정산금액',       value: '₩2,450,800',   delta: '전일 대비 ▲ 6.1%',  tone: 'blue',   icon: 'won',     deltaTone: 'up' },
  { title: '미정산 건수',       value: '36',           delta: '전시간 ▼ 3건',      tone: 'yellow', icon: 'review',  deltaTone: 'up' },
  { title: '평균 OCR 감지율',   value: '92.4%',        delta: '베이스라인 +1.2%p', tone: 'green',  icon: 'ocr',     deltaTone: 'up' },
  { title: 'GPS 이탈 건수',     value: '4',            delta: '오늘 누적',         tone: 'cyan',   icon: 'geofence',deltaTone: 'down' }
]

const laneStatus = ref([
  { lane: 1, name: 'LANE 1 (상단)', plate: '12가3456', todayCount: 486, totalCount: 12842, throughput: 8.4, avgConf: 94, tone: 'live',
    hourlySeries: [12,18,24,30,38,42,40,38,42,46,50,52,48,44,42,40,38,36,34,32,28,24,20,16],
    confSeries: [92,93,94,95,93,94,96,95,94,93,94,95,94,93,94,95,94,93,94,95,94,93,94,94] },
  { lane: 2, name: 'LANE 2 (하단)', plate: '85라1212', todayCount: 392, totalCount: 9876, throughput: 6.7, avgConf: 71, tone: 'warn',
    hourlySeries: [8,12,16,22,28,30,32,30,28,32,34,36,32,30,28,26,24,22,20,18,16,14,12,10],
    confSeries: [78,76,74,70,68,72,75,71,68,65,68,70,72,68,65,62,68,72,70,68,65,68,72,71] }
])

const period = ref('today')
const periodLabels = { today: '금일', week: '주간', month: '월간' }
const periodData = {
  today: {
    series: [12,18,24,30,38,42,72,108,138,156,164,178,168,144,138,142,156,168,172,148,124,98,72,46],
    axisFull: Array.from({length:24}, (_, i) => `${i}시`),
    axisLabels: ['00','04','08','12','16','20','24'],
    settlement: { paid: 1827, pending: 36, hold: 14, totalAmount: 2450800, paidAmount: 2180300, pendingAmount: 84500, holdAmount: 186000 }
  },
  week: {
    series: [820, 1102, 1340, 1208, 1456, 980, 624],
    axisFull: ['월요일','화요일','수요일','목요일','금요일','토요일','일요일'],
    axisLabels: ['월','화','수','목','금','토','일'],
    settlement: { paid: 12480, pending: 220, hold: 110, totalAmount: 16842500, paidAmount: 15080300, pendingAmount: 920400, holdAmount: 841800 }
  },
  month: {
    series: [820,945,1102,1208,1340,1456,1180,920,1340,1102,980,1208,1456,1340,1208,1102,980,1340,1456,1208,980,820,1208,1340,1456,1102,980,1208,1340,1248],
    axisFull: Array.from({length:30}, (_, i) => `${i+1}일`),
    axisLabels: ['1','5','10','15','20','25','30'],
    settlement: { paid: 53420, pending: 980, hold: 480, totalAmount: 72485600, paidAmount: 64830200, pendingAmount: 4250400, holdAmount: 3405000 }
  }
}
const currentPeriod = computed(() => periodData[period.value])
const currentSeries = computed(() => currentPeriod.value.series)
const currentMax = computed(() => Math.max(...currentSeries.value))
const currentTotal = computed(() => currentSeries.value.reduce((a, b) => a + b, 0))
const currentSettlement = computed(() => currentPeriod.value.settlement)
const esgSummary = computed(() => {
  const total = currentTotal.value
  return {
    co2Kg: Math.round(total * 0.12),
    idleMinutes: Math.round(total * 0.8),
    paperSheets: Math.round(total * 0.62),
    treeEquivalent: Math.max(1, Math.round((total * 0.12) / 22)),
    score: period.value === 'today' ? 87 : period.value === 'week' ? 91 : 94
  }
})

const anomalyAlerts = [
  { id: 1, severity: 'critical', title: '정차 의심 차량', desc: 'LANE 2 · 33나9029 · 12초 정지', time: '10:22:27' },
  { id: 2, severity: 'warn', title: 'OCR 신뢰도 급락', desc: 'LANE 2 평균 -14%p (최근 100건)', time: '10:21:05' },
  { id: 3, severity: 'warn', title: 'Front/Rear 불일치', desc: 'LANE 2 · 33나9029 ↔ 33나9028', time: '10:20:42' },
  { id: 4, severity: 'info', title: '유령 통행', desc: 'GPS만 통과 · OCR 미검출 1건', time: '10:19:48' },
  { id: 5, severity: 'info', title: 'Edge Spool 정상', desc: 'EDGE-RC-01 재전송 0건', time: '10:18:12' }
]

const systemHealth = [
  { label: 'CPU', value: '38%', tone: 'ok' },
  { label: 'GPU MEM', value: '6.2GB', tone: 'ok' },
  { label: 'EDGE FPS', value: '29.8', tone: 'ok' },
  { label: 'OCR LAT', value: '142ms', tone: 'caution' }
]

function updateTime() {
  const now = new Date()
  const pad = (v) => String(v).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}
function statusClass(s) {
  if (['저장완료', '정상', '통과'].includes(s)) return 'ok'
  if (s === '검수필요') return 'caution'
  if (s === '정산대기') return 'pending'
  return 'danger'
}
function confClass(c) {
  if (c >= 85) return 'ok'
  if (c >= 65) return 'caution'
  return 'danger'
}
function selectEvent(e) {
  selectedEventId.value = e.id
  selectedLane.value = e.lane
}
function openReviewModal(event) {
  reviewTarget.value = event
  reviewAction.value = '확인완료'
  reviewMemo.value = ''
  showReviewModal.value = true
}
function saveReviewAction() {
  if (!reviewTarget.value) return
  reviewTarget.value.status = reviewAction.value === '예외처리' ? '예외처리' : '저장완료'
  showReviewModal.value = false
  alert(`검수 결과가 ${reviewAction.value} 처리되었습니다.`)
}
function openEventModal(event) {
  selectEvent(event)
  eventModalTarget.value = event
  showEventModal.value = true
}
function openAlertEventModal(alert) {
  const plateMatch = alert.desc.match(/[0-9]{2}[가-힣][0-9]{4}/)
  const event = events.value.find((item) => item.plate === plateMatch?.[0])
    ?? events.value.find((item) => item.lane === 2)
    ?? selectedEvent.value
  openEventModal(event)
}
function saveOperatorSettings() {
  isSettingsEditing.value = false
  alert('관제 설정이 저장되었습니다.')
}
function fmtGpsDate(v) {
  if (!v) return '-'
  const d = new Date(v)
  const pad = (n) => String(n).padStart(2, '0')
  return `${String(d.getFullYear()).slice(2)}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function fmtGpsClock(v) {
  if (!v) return '-'
  const d = new Date(v)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
function fmtCoord(v) { if (v == null) return 'NO_FIX'; return Number(v ?? 0).toFixed(6) }
function distanceMeters(la1, ln1, la2, ln2) {
  const lm = 111320, gm = 111320 * Math.cos((la1 * Math.PI) / 180)
  const dy = (la1 - la2) * lm, dx = (ln1 - ln2) * gm
  return Math.sqrt(dx * dx + dy * dy)
}
function projectGpsPoint(lat, lng) {
  const b = zoneBounds.value
  const lr = Math.max(0.000001, b.maxLat - b.minLat)
  const gr = Math.max(0.000001, b.maxLng - b.minLng)
  const x = 20 + ((lng - b.minLng) / gr) * 60
  const y = 78 - ((lat - b.minLat) / lr) * 56
  return { x: Math.max(6, Math.min(94, x)), y: Math.max(6, Math.min(94, y)) }
}
async function fetchGpsTelemetry() {
  const { data } = await gpsApi.latest()
  gpsTelemetry.value = data.map((t) => ({ ...t, capturedAt: normalizeDate(t.capturedAt) }))
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
    plateNumber: selectedEvent.value.final.plate,
    gpsDeviceId: latest.gpsDeviceId,
    laneId: latest.laneId ?? `RC-LANE-${selectedEvent.value.lane}`,
    edgeNodeId: latest.edgeNodeId ?? 'EDGE-RC-01',
    plateConfidence: selectedEvent.value.final.conf / 100
  })
  tollDecision.value = data
  await fetchTollHistory()
}
function normalizeDate(raw) {
  if (!raw) return null
  if (typeof raw === 'string') return raw
  if (Array.isArray(raw)) {
    const [y, m, d, h = 0, mi = 0, s = 0] = raw
    return new Date(y, m - 1, d, h, mi, s).toISOString()
  }
  return raw
}
function activateMenu(menu) {
  activeMenu.value = menu
  if (menu === 'OCR / 검수') opsSubOpen.value = !opsSubOpen.value
}
function logout() { auth.logout().finally(() => router.push('/')) }

// ▼ Sparkline helpers
function sparkPath(data, w = 100, h = 30) {
  if (!data?.length) return ''
  const min = Math.min(...data), max = Math.max(...data)
  const range = max - min || 1
  const step = w / (data.length - 1)
  return data.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`).join(' ')
}
function sparkArea(data, w = 100, h = 30) {
  const path = sparkPath(data, w, h)
  if (!path) return ''
  return `${path} L${w},${h} L0,${h} Z`
}
const settlementCircum = 2 * Math.PI * 50
const settlementSegs = computed(() => {
  const sb = currentSettlement.value
  const total = sb.paid + sb.pending + sb.hold
  let off = 0
  return [
    { color: '#33e6a1', value: sb.paid, ratio: sb.paid / total },
    { color: '#ffd166', value: sb.pending, ratio: sb.pending / total },
    { color: '#ff5d6c', value: sb.hold, ratio: sb.hold / total }
  ].map((s) => { const o = off; off += s.ratio; return { ...s, dashOff: -o * settlementCircum, dashArr: `${s.ratio * settlementCircum} ${settlementCircum}` } })
})
const settlementPaidPct = computed(() => {
  const sb = currentSettlement.value
  return ((sb.paid / (sb.paid + sb.pending + sb.hold)) * 100).toFixed(0)
})

// ▼ 위젯 편집
function toggleEdit() { editMode.value = !editMode.value }
function resetLayout() { widgets.value = JSON.parse(JSON.stringify(defaultLayout)) }
function onDragStart(idx, ev) {
  if (!editMode.value) return
  draggedIdx.value = idx
  ev.dataTransfer.effectAllowed = 'move'
}
function onDragOver(ev) { if (editMode.value) ev.preventDefault() }
function onDrop(idx) {
  if (!editMode.value || draggedIdx.value === null || draggedIdx.value === idx) return
  const arr = [...widgets.value]
  const [moved] = arr.splice(draggedIdx.value, 1)
  arr.splice(idx, 0, moved)
  widgets.value = arr
  draggedIdx.value = null
}
function onDragEnd() { draggedIdx.value = null }
const sizeSteps = [3, 4, 6, 8, 9, 12]
function resizeWidget(idx, dir) {
  const cur = widgets.value[idx].span
  const i = sizeSteps.indexOf(cur)
  if (dir === '+' && i < sizeSteps.length - 1) widgets.value[idx].span = sizeSteps[i + 1]
  if (dir === '-' && i > 0) widgets.value[idx].span = sizeSteps[i - 1]
}
function moveWidget(idx, delta) {
  const newIdx = idx + delta
  if (newIdx < 0 || newIdx >= widgets.value.length) return
  const arr = [...widgets.value]
  ;[arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]]
  widgets.value = arr
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
onBeforeUnmount(() => { clearInterval(timer); clearInterval(gpsTimer) })
</script>

<template>
  <div class="ops-shell" :class="{ light: isLightMode }">
    <div class="bg-particles">
      <span v-for="n in 60" :key="n" class="particle" :style="{ left: ((n*41)%100)+'%', top: ((n*47)%100)+'%', animationDelay: (n*0.11)+'s' }"></span>
    </div>

    <!-- ▼ Sidebar -->
    <aside class="sidebar">
      <div class="brand-header">
        <span class="brand-mark">◆</span>
        <div>
          <strong>HI-FIVE<small>Operator</small></strong>
          <span>Smart Tolling Console</span>
        </div>
      </div>

      <nav class="side-nav">
        <button :class="{ active: activeMenu === '실시간 관제' }" @click="activateMenu('실시간 관제')"><i class="ico">⌂</i>실시간 관제</button>
        <button class="has-sub" :class="{ active: activeMenu === 'OCR / 검수' }" @click="activateMenu('OCR / 검수')"><i class="ico">▤</i>OCR / 검수<em>{{ opsSubOpen ? '∧' : '∨' }}</em></button>
        <div v-if="opsSubOpen" class="submenu">
          <button :class="{ active: activeMenu === 'OCR 분석' }" @click="activateMenu('OCR 분석')">차량 인식 상세</button>
          <button :class="{ active: activeMenu === '검수 큐' }" @click="activateMenu('검수 큐')">검수 큐</button>
        </div>
        <button :class="{ active: activeMenu === '차로 현황' }" @click="activateMenu('차로 현황')"><i class="ico">◎</i>차로 현황 (2차선)</button>
        <button :class="{ active: activeMenu === '통행 이벤트' }" @click="activateMenu('통행 이벤트')"><i class="ico">≡</i>통행 이벤트</button>
        <button :class="{ active: activeMenu === '이상징후 알림' }" @click="activateMenu('이상징후 알림')"><i class="ico">▢</i>이상징후 알림</button>
        <button :class="{ active: activeMenu === '단말 상태' }" @click="activateMenu('단말 상태')"><i class="ico">⚙</i>단말 상태</button>
        <button :class="{ active: activeMenu === '설정' }" @click="activateMenu('설정')"><i class="ico">✦</i>설정</button>
      </nav>

      <div class="quick-section">
        <p>빠른 작업</p>
        <button class="quick-pill" :class="{ on: editMode }" @click="toggleEdit">{{ editMode ? '✓ 편집 종료' : '✎ 레이아웃 편집' }}</button>
        <button v-if="editMode" class="quick-pill" @click="resetLayout">↺ 기본 레이아웃</button>
        <button class="quick-pill" @click="showGpsZoneModal = true">GPS 영역 설정</button>
        <button class="quick-pill primary" @click="simulatePlateRecognition">결제 판정 실행</button>
      </div>
      <p class="copyright">© 2025 HI-FIVE All rights reserved.</p>
    </aside>

    <!-- ▼ Content -->
    <div class="content">
      <header class="topbar">
        <div class="top-brand">
          <span class="brand-mark sm">◆</span>
          <strong>HI-FIVE</strong>
          <span class="top-sub">Operator Dashboard · {{ dashboardLabel }} · 2-Lane</span>
          <span v-if="editMode" class="edit-badge">레이아웃 편집 모드</span>
        </div>
        <div class="top-right">
          <span class="top-info"><i>⏱</i>{{ nowText }}</span>
          <span class="top-info ok"><i class="dot"></i>서버 정상</span>
          <span class="top-info live"><i class="dot live-dot"></i>LIVE</span>
          <span class="admin-info">
            <span class="avatar"></span>
            <strong>{{ auth.member?.memberName ?? '관리자' }}</strong>
            <small>관제센터</small>
          </span>
          <button v-if="auth.isMasterAdmin" class="top-btn admin-btn" @click="router.push('/master-admin')">회원 대시보드 ↗</button>
          <button class="top-btn theme-btn" type="button" :title="isLightMode ? '다크 모드' : '라이트 모드'" :aria-label="isLightMode ? '다크 모드' : '라이트 모드'" @click="toggleThemeMode">
            <span>{{ isLightMode ? '☾' : '☀' }}</span>
          </button>
          <button class="top-btn" @click="router.push('/')">홈</button>
          <button class="top-btn" @click="logout">로그아웃</button>
        </div>
      </header>

      <main>
        <p v-if="editMode" class="edit-hint">편집 모드 — 위젯 헤더를 드래그해 순서를 바꾸거나 −/＋ 로 크기를 조절하세요. 위젯 너비는 12-그리드 기준입니다.</p>

        <section v-if="activeMenu === '실시간 관제'" class="widget-grid">
          <article v-for="(w, idx) in widgets" :key="w.id"
            class="widget panel"
            :class="[`widget-${w.id}`, { dragging: draggedIdx === idx, editing: editMode }]"
            :style="{ gridColumn: `span ${w.span}` }"
            :draggable="editMode"
            @dragstart="onDragStart(idx, $event)"
            @dragover="onDragOver"
            @drop.prevent="onDrop(idx)"
            @dragend="onDragEnd">

            <header v-if="editMode" class="widget-edit-bar">
              <span class="drag-grip">⋮⋮</span>
              <strong>{{ w.title }}</strong>
              <div class="widget-controls">
                <button class="ctrl" @click.stop="resizeWidget(idx, '-')" :disabled="w.span <= 3">−</button>
                <span class="ctrl-size mono">{{ w.span }}/12</span>
                <button class="ctrl" @click.stop="resizeWidget(idx, '+')" :disabled="w.span >= 12">＋</button>
                <button class="ctrl" @click.stop="moveWidget(idx, -1)" :disabled="idx === 0">↑</button>
                <button class="ctrl" @click.stop="moveWidget(idx, 1)" :disabled="idx === widgets.length - 1">↓</button>
              </div>
            </header>

            <!-- ▼ KPI Widget -->
            <div v-if="w.id === 'kpi'" class="kpi-row">
              <article v-for="card in kpiCards" :key="card.title" class="kpi-card">
                <div class="kpi-icon" :class="card.tone">
                  <span v-if="card.icon === 'flow'">⇄</span>
                  <span v-else-if="card.icon === 'review'">⚠</span>
                  <span v-else-if="card.icon === 'won'">₩</span>
                  <span v-else-if="card.icon === 'ocr'">◎</span>
                  <span v-else-if="card.icon === 'geofence'">⌖</span>
                </div>
                <div class="kpi-body">
                  <p class="kpi-title">{{ card.title }}</p>
                  <strong class="kpi-value">{{ card.value }}</strong>
                  <em class="kpi-delta" :class="card.deltaTone">{{ card.delta }}</em>
                </div>
              </article>
            </div>

            <!-- ▼ YOLO Frame -->
            <template v-else-if="w.id === 'frame'">
              <div class="panel-head"><h2><span class="bar"></span>YOLO 입력 프레임 (960×960)</h2><div class="panel-actions"><span class="chip"><i class="dot"></i>Camera × 1</span><span class="chip live"><i class="dot live-dot"></i>LIVE</span></div></div>
              <div class="frame-stage">
                <video class="frame-video" :src="ocrVideoUrl" autoplay loop muted controls playsinline preload="metadata">stream</video>
                <div class="lane-divider"></div>
                <span class="lane-tag top" :class="{ active: selectedLane === 1 }">LANE 1 · 960×480 (상단)</span>
                <span class="lane-tag bottom" :class="{ active: selectedLane === 2 }">LANE 2 · 960×480 (하단)</span>
                <div class="bbox" :style="{ top: selectedEvent.bbox.top+'%', left: selectedEvent.bbox.left+'%', width: selectedEvent.bbox.width+'%', height: selectedEvent.bbox.height+'%', borderColor: selectedEvent.final.conf > 85 ? '#33e6a1' : selectedEvent.final.conf > 65 ? '#ffd166' : '#ff5d6c' }">
                  <span class="bbox-label">L{{ selectedEvent.lane }} · {{ selectedEvent.final.plate }} · {{ selectedEvent.final.conf }}%</span>
                </div>
              </div>
              <div class="frame-foot">
                <div><span>입력 해상도</span><strong class="mono">1920×1080</strong></div>
                <div><span>YOLO 입력</span><strong class="mono">960×960</strong></div>
                <div><span>차로 수</span><strong class="mono">2</strong></div>
                <div><span>FPS</span><strong class="mono">29.8</strong></div>
              </div>
            </template>

            <!-- ▼ GPS 실시간 로그 (영역 가득) -->
            <template v-else-if="w.id === 'gps'">
              <div class="panel-head">
                <h2><span class="bar"></span>GPS Telemetry 실시간 로그</h2>
                <div class="panel-actions">
                  <span class="chip ok"><i class="dot"></i>저장 중</span>
                  <button class="link-btn" @click="showGpsZoneModal = true">영역 설정</button>
                </div>
              </div>
              <div class="gps-log-fill">
                <table class="log-table">
                  <thead><tr><th>TIME</th><th>DEVICE</th><th>LAT/LNG</th><th>SPD</th><th>HEAD</th><th>ALT</th><th>FIX</th><th>SAT</th></tr></thead>
                  <tbody>
                    <tr v-for="log in gpsTelemetry" :key="log.id">
                      <td class="mono time-cell"><span>{{ fmtGpsDate(log.capturedAt) }}</span><span>{{ fmtGpsClock(log.capturedAt) }}</span></td>
                      <td class="mono">{{ log.gpsDeviceId }}</td>
                      <td class="mono">{{ fmtCoord(log.latitude) }}, {{ fmtCoord(log.longitude) }}</td>
                      <td class="mono">{{ Number(log.speedKmh ?? 0).toFixed(1) }}</td>
                      <td class="mono">{{ log.heading ?? '-' }}</td>
                      <td class="mono">{{ log.altitudeM ?? '-' }}</td>
                      <td><span class="status" :class="log.fixStatus === 'NO_FIX' ? 'caution' : 'ok'">{{ log.fixStatus ?? log.fixType ?? 'FIXED' }}</span></td>
                      <td class="mono">{{ log.satelliteCount ?? '-' }}</td>
                    </tr>
                    <tr v-if="gpsTelemetry.length === 0"><td colspan="8" class="empty">수신된 GPS 로그가 없습니다.</td></tr>
                  </tbody>
                </table>
              </div>
            </template>

            <!-- ▼ 통행량 (금일/주간/월간) -->
            <template v-else-if="w.id === 'stats-traffic'">
              <div class="panel-head">
                <h2><span class="bar"></span>{{ periodLabels[period] }} 통행량</h2>
                <div class="period-tabs">
                  <button :class="{ active: period === 'today' }" @click="period = 'today'">금일</button>
                  <button :class="{ active: period === 'week' }" @click="period = 'week'">주간</button>
                  <button :class="{ active: period === 'month' }" @click="period = 'month'">월간</button>
                </div>
                <strong class="big-num">{{ currentTotal.toLocaleString() }}<span class="muted ml-sm">대</span></strong>
              </div>
              <div class="hour-chart">
                <div v-for="(v, i) in currentSeries" :key="i" class="bar-item" :style="{ height: ((v / currentMax) * 100) + '%' }"><span class="bar-tip">{{ currentPeriod.axisFull[i] }} · {{ v.toLocaleString() }}대</span></div>
              </div>
              <div class="hour-axis"><span v-for="a in currentPeriod.axisLabels" :key="a">{{ a }}</span></div>
            </template>

            <!-- ▼ 정산 -->
            <template v-else-if="w.id === 'stats-settle'">
              <div class="panel-head"><h2><span class="bar"></span>{{ periodLabels[period] }} 정산 금액</h2></div>
              <strong class="big-num center">₩{{ currentSettlement.totalAmount.toLocaleString() }}</strong>
              <div class="donut-row">
                <svg class="donut-svg" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(56,120,245,.14)" stroke-width="14"/>
                  <circle v-for="(s, i) in settlementSegs" :key="i" cx="60" cy="60" r="50" fill="none" :stroke="s.color" stroke-width="14" :stroke-dasharray="s.dashArr" :stroke-dashoffset="s.dashOff" transform="rotate(-90 60 60)"/>
                  <text x="60" y="56" text-anchor="middle" fill="#fff" font-size="18" font-weight="700">{{ settlementPaidPct }}%</text>
                  <text x="60" y="74" text-anchor="middle" fill="#7290b8" font-size="9">결제율</text>
                </svg>
              </div>
              <ul class="donut-legend">
                <li><i style="background:#33e6a1"></i><span>완료</span><strong>₩{{ currentSettlement.paidAmount.toLocaleString() }}</strong></li>
                <li><i style="background:#ffd166"></i><span>미정산</span><strong>₩{{ currentSettlement.pendingAmount.toLocaleString() }}</strong></li>
                <li><i style="background:#ff5d6c"></i><span>보류</span><strong>₩{{ currentSettlement.holdAmount.toLocaleString() }}</strong></li>
              </ul>
            </template>

            <!-- ▼ ESG 탄소 저감량 -->
            <template v-else-if="w.id === 'stats-esg'">
              <div class="panel-head">
                <h2><span class="bar"></span>{{ periodLabels[period] }} ESG 탄소 저감량</h2>
                <strong class="big-num">{{ esgSummary.co2Kg.toLocaleString() }}<span class="muted ml-sm">kgCO₂</span></strong>
              </div>
              <div class="esg-score">
                <span>ESG Impact</span>
                <strong>{{ esgSummary.score }}</strong>
              </div>
              <ul class="esg-list">
                <li>
                  <span class="esg-dot green"></span>
                  <div><strong>{{ esgSummary.idleMinutes.toLocaleString() }}분</strong><em>무정차 통과 기반 공회전 절감</em></div>
                </li>
                <li>
                  <span class="esg-dot blue"></span>
                  <div><strong>{{ esgSummary.paperSheets.toLocaleString() }}장</strong><em>전자 정산 기반 종이 영수증 절감</em></div>
                </li>
                <li>
                  <span class="esg-dot yellow"></span>
                  <div><strong>{{ esgSummary.treeEquivalent.toLocaleString() }}그루</strong><em>연간 흡수량 환산 기준</em></div>
                </li>
              </ul>
            </template>

            <!-- ▼ 통행 이벤트 (스크롤 — 상위 15 가시) -->
            <template v-else-if="w.id === 'events'">
              <div class="panel-head">
                <h2><span class="bar"></span>실시간 통행 이벤트<span class="muted ml-sm small">총 {{ events.length }}건</span></h2>
                <div class="filter-row">
                  <button v-for="f in ['전체', '검수필요', '정산완료']" :key="f" :class="{ active: activeFilter === f }" @click="activeFilter = f">{{ f }}</button>
                </div>
              </div>
              <div class="event-scroll">
                <table class="sticky-head">
                  <thead><tr><th>TIME</th><th>L</th><th>PLATE</th><th>방향</th><th>채택</th><th>CONF</th><th>STATUS</th></tr></thead>
                  <tbody>
                    <tr v-for="e in filteredEvents" :key="e.id" :class="{ selected: selectedEventId === e.id }" @click="selectEvent(e)">
                      <td class="mono">{{ e.time }}</td>
                      <td>L{{ e.lane }}</td>
                      <td class="plate mono">{{ e.plate }}</td>
                      <td>{{ e.direction }}</td>
                      <td class="mono small">{{ e.source }}</td>
                      <td class="mono">{{ e.conf }}%</td>
                      <td><span class="status" :class="statusClass(e.status)">{{ e.status }}</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>

            <!-- ▼ Detail (Plate / GPS toggle) -->
            <template v-else-if="w.id === 'detail'">
              <div class="panel-head">
                <h2><span class="bar"></span>차량 상세<span class="muted ml-sm small">{{ selectedEvent.plate }} · {{ selectedEvent.time }}</span></h2>
                <span class="lane-badge">LANE {{ selectedEvent.lane }}</span>
              </div>
              <div class="detail-tabs">
                <button :class="{ active: detailTab === 'plate' }" @click="detailTab = 'plate'">번호판 인식</button>
                <button :class="{ active: detailTab === 'gps' }" @click="detailTab = 'gps'">GPS 경로 분석</button>
              </div>

              <div v-if="detailTab === 'plate'" class="detail-stack">
                <div class="detail-card">
                  <div class="detail-head"><p class="eyebrow">FRONT 앞 번호판</p><span class="badge" :class="confClass(selectedEvent.front.conf)">{{ selectedEvent.front.conf }}%</span></div>
                  <div class="plate-img"><div class="plate-placeholder"><span class="placeholder-tag">FRONT CROP</span><span class="placeholder-meta mono">960×480 · top half</span></div></div>
                  <div class="plate-result mono">{{ selectedEvent.front.plate }}</div>
                  <span class="capture-ts mono">{{ selectedEvent.front.ts }}</span>
                </div>
                <div class="detail-card">
                  <div class="detail-head"><p class="eyebrow">REAR 뒷 번호판</p><span class="badge" :class="confClass(selectedEvent.rear.conf)">{{ selectedEvent.rear.conf }}%</span></div>
                  <div class="plate-img"><div class="plate-placeholder"><span class="placeholder-tag">REAR CROP</span><span class="placeholder-meta mono">960×480 · bottom half</span></div></div>
                  <div class="plate-result mono">{{ selectedEvent.rear.plate }}</div>
                  <span class="capture-ts mono">{{ selectedEvent.rear.ts }}</span>
                </div>
                <div class="detail-card final">
                  <div class="detail-head"><p class="eyebrow">FUSION 최종</p><span class="badge" :class="confClass(selectedEvent.final.conf)">{{ selectedEvent.final.conf }}%</span></div>
                  <div class="plate-final mono">{{ selectedEvent.final.plate }}</div>
                  <div class="fusion-meta">
                    <p><span>합의도</span><strong>{{ (selectedEvent.final.agreement*100).toFixed(0) }}%</strong></p>
                    <p><span>채택</span><strong>{{ selectedEvent.final.source }}</strong></p>
                  </div>
                  <div class="conf-bar"><b :style="{ width: selectedEvent.final.conf + '%' }"></b></div>
                </div>
              </div>

              <div v-else class="detail-stack">
                <div class="detail-card">
                  <div class="detail-head"><p class="eyebrow">선택 차량 GPS 경로</p><span class="status" :class="selectedGpsScatter.inside ? 'ok' : 'danger'">{{ selectedGpsScatter.inside ? '영역 통과' : '영역 이탈' }}</span></div>
                  <div class="gps-map mini">
                    <div class="zone"></div>
                    <span v-for="p in selectedGpsScatter.points" :key="p.id" class="gps-point" :class="p.type" :style="{ left: p.x + '%', top: p.y + '%' }">
                      <em v-if="p.label">{{ p.label }}</em>
                    </span>
                  </div>
                </div>
                <div class="detail-card">
                  <div class="detail-head"><p class="eyebrow">GPS 정보</p></div>
                  <div class="gps-info">
                    <p><span>차량</span><strong class="mono">{{ selectedEvent.plate }}</strong></p>
                    <p><span>위도</span><strong class="mono">{{ Number(selectedEvent.gps.lat).toFixed(6) }}</strong></p>
                    <p><span>경도</span><strong class="mono">{{ Number(selectedEvent.gps.lng).toFixed(6) }}</strong></p>
                    <p><span>속도</span><strong class="mono">{{ selectedEvent.gps.speed }} km/h</strong></p>
                    <p><span>방향</span><strong>{{ selectedEvent.direction }}</strong></p>
                    <p><span>통과 시각</span><strong class="mono">{{ selectedEvent.time }}</strong></p>
                  </div>
                </div>
              </div>

              <button class="primary-btn small wide" @click="simulatePlateRecognition">{{ detailTab === 'plate' ? '번호판 + GPS 결제 판정' : '이 GPS로 결제 판정 실행' }}</button>
              <p v-if="tollDecision" class="decision">{{ tollDecision.charged ? '✓ 결제 인식' : '✗ 결제 미생성' }} — {{ tollDecision.reason }}</p>
            </template>

            <!-- ▼ Lane status with charts -->
            <template v-else-if="w.id === 'lanes'">
              <div class="panel-head"><h2><span class="bar"></span>차로별 실시간 상태 (2차선)</h2><span class="chip">{{ laneStatus.reduce((a,b)=>a+b.todayCount,0).toLocaleString() }} 대 / 금일</span></div>
              <div class="lane-detail-grid">
                <article v-for="lane in laneStatus" :key="lane.lane" class="lane-detail" :class="`tone-${lane.tone}`" @click="selectedLane = lane.lane">
                  <div class="lane-detail-head">
                    <div><p class="lane-name">{{ lane.name }}</p><strong class="lane-current mono">{{ lane.plate }}</strong></div>
                    <span class="status" :class="lane.tone === 'live' ? 'ok' : lane.tone === 'warn' ? 'caution' : 'danger'">{{ lane.tone === 'live' ? 'LIVE' : lane.tone === 'warn' ? 'WARN' : 'IDLE' }}</span>
                  </div>
                  <div class="metric-grid">
                    <div class="metric"><p>금일 처리량</p><strong class="mono">{{ lane.todayCount.toLocaleString() }}<small>대</small></strong>
                      <div class="metric-bars"><span v-for="(v, i) in lane.hourlySeries" :key="i" :style="{ height: ((v / Math.max(...lane.hourlySeries)) * 100) + '%' }"></span></div>
                      <em class="muted">시간대별 (24h)</em>
                    </div>
                    <div class="metric"><p>누적 통행량</p><strong class="mono">{{ lane.totalCount.toLocaleString() }}<small>대</small></strong>
                      <div class="cumulative-bar"><b :style="{ width: ((lane.todayCount / lane.totalCount) * 100) + '%' }"></b></div>
                      <em class="muted">금일 비중 {{ ((lane.todayCount / lane.totalCount) * 100).toFixed(1) }}%</em>
                    </div>
                    <div class="metric"><p>평균 신뢰도</p><strong class="mono" :class="confClass(lane.avgConf)">{{ lane.avgConf }}<small>%</small></strong>
                      <svg class="metric-spark" viewBox="0 0 100 30" preserveAspectRatio="none">
                        <path :d="sparkArea(lane.confSeries)" :fill="lane.avgConf >= 85 ? 'rgba(51,230,161,.25)' : lane.avgConf >= 65 ? 'rgba(255,209,102,.25)' : 'rgba(255,93,108,.25)'"/>
                        <path :d="sparkPath(lane.confSeries)" fill="none" :stroke="lane.avgConf >= 85 ? '#33e6a1' : lane.avgConf >= 65 ? '#ffd166' : '#ff5d6c'" stroke-width="1.6"/>
                      </svg>
                      <em class="muted">처리량 {{ lane.throughput }}/min</em>
                    </div>
                  </div>
                </article>
              </div>
            </template>

            <!-- ▼ Anomaly Queue -->
            <template v-else-if="w.id === 'anomaly'">
              <div class="panel-head"><h2><span class="bar"></span>이상징후 · 검수 큐</h2><span class="chip danger"><i class="dot live-dot"></i>{{ anomalyAlerts.filter(a => a.severity === 'critical').length }} CRITICAL</span></div>
              <ul class="alert-list">
                <li v-for="a in anomalyAlerts" :key="a.id" :class="a.severity">
                  <span class="alert-bar"></span>
                  <div class="alert-body">
                    <div class="alert-row"><strong>{{ a.title }}</strong><span class="mono muted">{{ a.time }}</span></div>
                    <p>{{ a.desc }}</p>
                  </div>
                  <button class="row-btn">처리</button>
                </li>
              </ul>
            </template>
          </article>
        </section>

        <section v-else class="ops-subpage">
          <article class="panel subpage-hero">
            <div>
              <p class="subpage-kicker">OPERATOR CONSOLE</p>
              <h2>{{ activeMenu }}</h2>
              <span>{{ dashboardLabel }} 관제센터 운영 데이터를 메뉴별로 집중 확인합니다.</span>
            </div>
            <button class="primary-btn small" type="button" @click="activeMenu = '실시간 관제'">실시간 관제로 이동</button>
          </article>

          <article v-if="activeMenu === 'OCR / 검수' || activeMenu === 'OCR 분석'" class="panel subpage-panel">
            <div class="panel-head">
              <h2><span class="bar"></span>OCR 차량 인식 상세</h2>
              <span class="chip">선택 차량 {{ selectedEvent.plate }}</span>
            </div>
            <div class="lane-ocr-layout">
              <div class="lane-detect-list">
                <button v-for="lane in laneDetections" :key="lane.lane" class="lane-detect-card" :class="{ active: selectedSubLane === lane.lane }" type="button" @click="selectedSubLane = lane.lane; selectEvent(lane.latest)">
                  <span class="lane-detect-title">{{ lane.title }}</span>
                  <strong class="mono">{{ lane.latest.plate }}</strong>
                  <em :class="confClass(lane.avgConf)">평균 {{ lane.avgConf }}%</em>
                  <small>검출 {{ lane.count }}건 · 검수 {{ lane.reviewCount }}건</small>
                </button>
              </div>
              <div class="lane-detect-detail">
                <div class="frame-stage subpage-frame">
                  <video class="frame-video" :src="ocrVideoUrl" autoplay loop muted controls playsinline preload="metadata">stream</video>
                  <div class="bbox" :style="{ top: activeLaneDetection.latest.bbox.top+'%', left: activeLaneDetection.latest.bbox.left+'%', width: activeLaneDetection.latest.bbox.width+'%', height: activeLaneDetection.latest.bbox.height+'%', borderColor: activeLaneDetection.latest.final.conf > 85 ? '#33e6a1' : activeLaneDetection.latest.final.conf > 65 ? '#ffd166' : '#ff5d6c' }">
                    <span class="bbox-label">L{{ activeLaneDetection.lane }} · {{ activeLaneDetection.latest.final.plate }} · {{ activeLaneDetection.latest.final.conf }}%</span>
                  </div>
                </div>
                <div class="subpage-info-grid">
                  <p><span>차량 번호</span><strong>{{ activeLaneDetection.latest.plate }}</strong></p>
                  <p><span>차로</span><strong>LANE {{ activeLaneDetection.lane }}</strong></p>
                  <p><span>검출 시간</span><strong>{{ activeLaneDetection.latest.time }}</strong></p>
                  <p><span>신뢰도</span><strong :class="confClass(activeLaneDetection.latest.conf)">{{ activeLaneDetection.latest.conf }}%</strong></p>
                  <p><span>상태</span><strong>{{ activeLaneDetection.latest.status }}</strong></p>
                  <p><span>판정 소스</span><strong>{{ activeLaneDetection.latest.source }}</strong></p>
                </div>
              </div>
            </div>
          </article>

          <article v-else-if="activeMenu === '검수 큐'" class="panel subpage-panel">
            <div class="panel-head">
              <h2><span class="bar"></span>검수 큐</h2>
              <span class="chip caution">{{ events.filter(e => e.status === '검수필요').length }}건 대기</span>
            </div>
            <div class="event-scroll subpage-table-scroll">
              <table class="sticky-head">
                <thead><tr><th>TIME</th><th>LANE</th><th>PLATE</th><th>CONF</th><th>사유</th><th>액션</th></tr></thead>
                <tbody>
                  <tr v-for="event in events.filter(e => e.status === '검수필요')" :key="event.id" @click="selectEvent(event)">
                    <td class="mono">{{ event.time }}</td>
                    <td>LANE {{ event.lane }}</td>
                    <td class="mono strong">{{ event.plate }}</td>
                    <td :class="confClass(event.conf)">{{ event.conf }}%</td>
                    <td>OCR 저신뢰 / Front-Rear 확인 필요</td>
                    <td><button class="row-btn" type="button" @click.stop="openReviewModal(event)">수정</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article v-else-if="activeMenu === '차로 현황'" class="panel subpage-panel">
            <div class="panel-head"><h2><span class="bar"></span>차로별 실시간 상태</h2><span class="chip">{{ laneStatus.length }}개 차로 운영 중</span></div>
            <div class="lane-detail-grid">
              <article v-for="lane in laneStatus" :key="lane.lane" class="lane-detail" :class="`tone-${lane.tone}`">
                <div class="lane-detail-head">
                  <div><p class="lane-name">{{ lane.name }}</p><strong class="lane-current">{{ lane.plate }}</strong></div>
                  <span class="status ok">정상</span>
                </div>
                <div class="metric-grid">
                  <div class="metric"><p>금일 통행</p><strong>{{ lane.todayCount }}</strong><em>대</em></div>
                  <div class="metric"><p>누적 통행</p><strong>{{ lane.totalCount.toLocaleString() }}</strong><em>대</em></div>
                  <div class="metric"><p>평균 신뢰도</p><strong :class="confClass(lane.avgConf)">{{ lane.avgConf }}%</strong></div>
                </div>
              </article>
            </div>
          </article>

          <article v-else-if="activeMenu === '통행 이벤트'" class="panel subpage-panel">
            <div class="panel-head"><h2><span class="bar"></span>통행 이벤트 전체 목록</h2><span class="chip">총 {{ events.length }}건</span></div>
            <div class="event-scroll subpage-table-scroll">
              <table class="sticky-head">
                <thead><tr><th>TIME</th><th>LANE</th><th>PLATE</th><th>CONF</th><th>STATUS</th><th>GPS</th></tr></thead>
                <tbody>
                  <tr v-for="event in events" :key="event.id" :class="{ selected: selectedEventId === event.id }" @click="openEventModal(event)">
                    <td class="mono">{{ event.time }}</td>
                    <td>{{ event.lane }}</td>
                    <td class="mono strong">{{ event.plate }}</td>
                    <td>{{ event.conf }}%</td>
                    <td><span class="status" :class="statusClass(event.status)">{{ event.status }}</span></td>
                    <td class="mono">{{ Number(event.gps.lat).toFixed(6) }}, {{ Number(event.gps.lng).toFixed(6) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article v-else-if="activeMenu === '이상징후 알림'" class="panel subpage-panel">
            <div class="panel-head"><h2><span class="bar"></span>이상징후 알림</h2><span class="chip danger">{{ anomalyAlerts.filter(a => a.severity === 'critical').length }} CRITICAL</span></div>
            <ul class="alert-list subpage-alerts">
              <li v-for="a in anomalyAlerts" :key="a.id" :class="a.severity">
                <span class="alert-bar"></span>
                <div class="alert-body"><div class="alert-row"><strong>{{ a.title }}</strong><span class="mono muted">{{ a.time }}</span></div><p>{{ a.desc }}</p></div>
                <button class="row-btn" type="button" @click="openAlertEventModal(a)">상세</button>
              </li>
            </ul>
          </article>

          <article v-else-if="activeMenu === '단말 상태'" class="panel subpage-panel">
            <div class="panel-head"><h2><span class="bar"></span>단말 상태</h2><span class="chip ok">EDGE-RC-01 연결됨</span></div>
            <div class="health-grid subpage-health">
              <div v-for="h in systemHealth" :key="h.label" class="health-cell">
                <span>{{ h.label }}</span>
                <strong :class="h.tone">{{ h.value }}</strong>
              </div>
              <div class="health-cell"><span>GPS DEVICE</span><strong>PICO2W-NEO7M-RC-01</strong></div>
              <div class="health-cell"><span>최근 GPS 로그</span><strong>{{ gpsTelemetry.length }}건</strong></div>
              <div class="health-cell"><span>Spring API</span><strong class="ok">8585 OK</strong></div>
              <div class="health-cell"><span>FastAPI Edge</span><strong class="ok">READY</strong></div>
            </div>
          </article>

          <article v-else class="panel subpage-panel">
            <div class="panel-head">
              <h2><span class="bar"></span>관제 설정</h2>
              <div class="panel-actions">
                <button class="link-btn" type="button" @click="showGpsZoneModal = true">GPS 감지 영역 설정</button>
                <button v-if="!isSettingsEditing" class="link-btn" type="button" @click="isSettingsEditing = true">편집</button>
                <button v-else class="primary-btn small" type="button" @click="saveOperatorSettings">설정 저장</button>
              </div>
            </div>
            <div class="settings-grid">
              <label><span>대시보드 ID</span><input v-model="operatorSettings.dashboardId" :readonly="!isSettingsEditing" /></label>
              <label><span>관제 차로 수</span><input v-model.number="operatorSettings.laneCount" type="number" min="1" max="8" :readonly="!isSettingsEditing" /></label>
              <label><span>GPS 단말 ID</span><input v-model="operatorSettings.gpsDeviceId" :readonly="!isSettingsEditing" /></label>
              <label><span>OCR confidence 기준</span><input v-model.number="operatorSettings.ocrConfidence" type="number" min="0" max="100" :readonly="!isSettingsEditing" /></label>
              <label><span>검수 큐 기준</span><input v-model.number="operatorSettings.reviewThreshold" type="number" min="0" max="100" :readonly="!isSettingsEditing" /></label>
              <label><span>통행 이벤트 보관</span><input v-model="operatorSettings.storagePolicy" :readonly="!isSettingsEditing" /></label>
            </div>
          </article>
        </section>
      </main>
    </div>

    <div v-if="showReviewModal" class="modal-bg" @click.self="showReviewModal = false">
      <section class="modal panel">
        <div class="panel-head">
          <h2><span class="bar"></span>검수 결과 처리</h2>
          <button class="link-btn" type="button" @click="showReviewModal = false">닫기</button>
        </div>
        <div v-if="reviewTarget" class="review-modal-body">
          <div class="subpage-info-grid">
            <p><span>차량 번호</span><strong class="mono">{{ reviewTarget.plate }}</strong></p>
            <p><span>차로</span><strong>LANE {{ reviewTarget.lane }}</strong></p>
            <p><span>신뢰도</span><strong :class="confClass(reviewTarget.conf)">{{ reviewTarget.conf }}%</strong></p>
            <p><span>현재 상태</span><strong>{{ reviewTarget.status }}</strong></p>
          </div>
          <label class="modal-field">
            <span>처리 유형</span>
            <select v-model="reviewAction">
              <option>확인완료</option>
              <option>예외처리</option>
            </select>
          </label>
          <label class="modal-field">
            <span>처리 메모</span>
            <textarea v-model="reviewMemo" rows="4" placeholder="예외 사유 또는 확인 내용을 입력하세요."></textarea>
          </label>
          <button class="primary-btn" type="button" @click="saveReviewAction">검수 결과 저장</button>
        </div>
      </section>
    </div>

    <div v-if="showEventModal" class="modal-bg" @click.self="showEventModal = false">
      <section class="modal panel event-modal">
        <div class="panel-head">
          <h2><span class="bar"></span>차량 통행 상세</h2>
          <button class="link-btn" type="button" @click="showEventModal = false">닫기</button>
        </div>
        <div v-if="eventModalTarget" class="event-modal-grid">
          <div class="detail-card">
            <div class="detail-head"><p class="eyebrow">FRONT 앞 번호판</p><span class="badge" :class="confClass(eventModalTarget.front.conf)">{{ eventModalTarget.front.conf }}%</span></div>
            <div class="plate-img"><div class="plate-placeholder"><span class="placeholder-tag">FRONT CROP</span><span class="placeholder-meta mono">960×480 · top half</span></div></div>
            <div class="plate-result mono">{{ eventModalTarget.front.plate }}</div>
            <span class="capture-ts mono">{{ eventModalTarget.front.ts }}</span>
          </div>
          <div class="detail-card">
            <div class="detail-head"><p class="eyebrow">REAR 뒷 번호판</p><span class="badge" :class="confClass(eventModalTarget.rear.conf)">{{ eventModalTarget.rear.conf }}%</span></div>
            <div class="plate-img"><div class="plate-placeholder"><span class="placeholder-tag">REAR CROP</span><span class="placeholder-meta mono">960×480 · bottom half</span></div></div>
            <div class="plate-result mono">{{ eventModalTarget.rear.plate }}</div>
            <span class="capture-ts mono">{{ eventModalTarget.rear.ts }}</span>
          </div>
          <div class="detail-card final">
            <div class="detail-head"><p class="eyebrow">FUSION 최종 판정</p><span class="badge" :class="confClass(eventModalTarget.final.conf)">{{ eventModalTarget.final.conf }}%</span></div>
            <div class="plate-final mono">{{ eventModalTarget.final.plate }}</div>
            <div class="fusion-meta">
              <p><span>차로</span><strong>LANE {{ eventModalTarget.lane }}</strong></p>
              <p><span>통과 시각</span><strong class="mono">{{ eventModalTarget.time }}</strong></p>
              <p><span>상태</span><strong>{{ eventModalTarget.status }}</strong></p>
              <p><span>소스</span><strong>{{ eventModalTarget.source }}</strong></p>
            </div>
          </div>
          <div class="detail-card gps-modal-card">
            <div class="detail-head"><p class="eyebrow">GPS 경로 분석</p><span class="badge" :class="eventModalGpsScatter.inside ? 'ok' : 'danger'">{{ eventModalGpsScatter.inside ? '통과' : '이탈' }}</span></div>
            <div class="gps-map modal-gps-map">
              <div class="zone"></div>
              <span v-for="p in eventModalGpsScatter.points" :key="p.id" class="gps-point" :class="p.type" :style="{ left: p.x + '%', top: p.y + '%' }"><em v-if="p.label">{{ p.label }}</em></span>
            </div>
            <div class="gps-info modal-gps-info">
              <p><span>차량</span><strong class="mono">{{ eventModalTarget.plate }}</strong></p>
              <p><span>위도</span><strong class="mono">{{ Number(eventModalTarget.gps.lat).toFixed(6) }}</strong></p>
              <p><span>경도</span><strong class="mono">{{ Number(eventModalTarget.gps.lng).toFixed(6) }}</strong></p>
              <p><span>속도</span><strong class="mono">{{ eventModalTarget.gps.speed }} km/h</strong></p>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="showGpsZoneModal" class="modal-bg" @click.self="showGpsZoneModal = false">
      <section class="modal panel">
        <div class="panel-head"><h2><span class="bar"></span>GPS 감지 영역 좌표 설정</h2><button class="link-btn" @click="showGpsZoneModal = false">닫기</button></div>
        <p class="modal-copy">4개 꼭지점 좌표를 입력하면 GPS 경로 분석 영역과 산점도 판정이 즉시 갱신됩니다.</p>
        <div class="zone-grid">
          <label><span>좌상 위도</span><input v-model.number="gpsZone.northWestLat" type="number" step="0.000001" /></label>
          <label><span>좌상 경도</span><input v-model.number="gpsZone.northWestLng" type="number" step="0.000001" /></label>
          <label><span>우상 위도</span><input v-model.number="gpsZone.northEastLat" type="number" step="0.000001" /></label>
          <label><span>우상 경도</span><input v-model.number="gpsZone.northEastLng" type="number" step="0.000001" /></label>
          <label><span>우하 위도</span><input v-model.number="gpsZone.southEastLat" type="number" step="0.000001" /></label>
          <label><span>우하 경도</span><input v-model.number="gpsZone.southEastLng" type="number" step="0.000001" /></label>
          <label><span>좌하 위도</span><input v-model.number="gpsZone.southWestLat" type="number" step="0.000001" /></label>
          <label><span>좌하 경도</span><input v-model.number="gpsZone.southWestLng" type="number" step="0.000001" /></label>
        </div>
        <button class="primary-btn" @click="showGpsZoneModal = false">감지 영역 적용</button>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ===== Shell — base tokens ===== */
.ops-shell{position:relative;min-height:100vh;min-width:1280px;display:grid;grid-template-columns:240px 1fr;color:#dcecff;background:radial-gradient(ellipse at 20% 10%,rgba(56,120,245,.18),transparent 40%),radial-gradient(ellipse at 80% 90%,rgba(120,80,200,.14),transparent 40%),#070b1a;font-family:'Inter','Pretendard',ui-sans-serif,system-ui,-apple-system,sans-serif;font-size:13px;line-height:1.5;overflow-x:hidden}
.bg-particles{position:fixed;inset:0;pointer-events:none;z-index:0}
.particle{position:absolute;width:2px;height:2px;border-radius:50%;background:rgba(180,210,255,.4);box-shadow:0 0 6px rgba(120,180,255,.4);animation:twinkle 4s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}
button,input,select{font:inherit;color:inherit;cursor:pointer}
h1,h2{margin:0;font-weight:600}
.mono{font-family:'JetBrains Mono','SF Mono',ui-monospace,Menlo,monospace;font-feature-settings:'tnum'}
.muted{color:#7290b8}
.eyebrow{margin:0;color:#38bef5;font-size:10.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase}
.small{font-size:11px}
.ml-sm{margin-left:6px}
.center{text-align:center;display:block}

.sidebar{position:relative;z-index:2;padding:22px 16px;display:flex;flex-direction:column;gap:18px;background:linear-gradient(180deg,rgba(8,14,32,.92),rgba(8,14,32,.78));border-right:1px solid rgba(56,120,245,.18);min-width:0}
.brand-header{display:flex;align-items:center;gap:12px;padding:6px 8px}
.brand-mark{display:grid;place-items:center;width:34px;height:34px;border:2px solid #38bef5;border-radius:8px;color:#38bef5;font-size:16px;background:rgba(56,190,245,.06)}
.brand-mark.sm{width:28px;height:28px;font-size:13px}
.brand-header strong{display:block;font-size:15px;color:#fff;font-weight:700}
.brand-header strong small{font-weight:400;color:#8aa6cc;margin-left:4px;font-size:11px}
.brand-header span{display:block;color:#8aa6cc;font-size:11px}
.side-nav{display:flex;flex-direction:column;gap:2px}
.side-nav button{display:flex;align-items:center;gap:12px;padding:10px 12px;border:0;background:transparent;color:#a8c4e8;border-radius:8px;text-align:left;font-size:13px;transition:all .15s}
.side-nav button:hover{background:rgba(56,120,245,.08);color:#fff}
.side-nav button.active{background:rgba(56,190,245,.16);color:#fff;font-weight:600;box-shadow:inset 0 0 0 1px rgba(56,190,245,.3)}
.side-nav button .ico{width:18px;text-align:center;color:#5a7da8;font-size:13px}
.side-nav button.active .ico{color:#38bef5}
.side-nav button.has-sub em{margin-left:auto;font-style:normal;color:#5a7da8;font-size:11px}
.submenu{display:flex;flex-direction:column;gap:1px;margin:2px 0 4px 18px;padding-left:14px;border-left:1px solid rgba(56,120,245,.2)}
.submenu button{padding:7px 12px;font-size:12.5px;color:#88a4cc}
.submenu button.active{background:rgba(56,190,245,.1);color:#38bef5;font-weight:600}
.quick-section{margin-top:8px;padding:14px;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:rgba(8,14,32,.6);display:flex;flex-direction:column;gap:8px}
.quick-section p{margin:0 0 4px;color:#8aa6cc;font-size:11px}
.quick-pill{padding:10px;border:1px solid rgba(56,120,245,.22);border-radius:8px;background:rgba(20,36,68,.58);color:#dcecff;font-size:12.5px;text-align:center}
.quick-pill:hover{background:rgba(56,190,245,.18);border-color:rgba(56,190,245,.4)}
.quick-pill.on{background:rgba(146,100,224,.22);border-color:rgba(146,100,224,.5);color:#fff;font-weight:600}
.quick-pill.primary{background:linear-gradient(135deg,#1b3be8,#38bef5);border-color:rgba(56,190,245,.5);color:#fff;font-weight:600}
.copyright{margin:auto 0 0;color:#5a7da8;font-size:10.5px;text-align:center;padding-top:12px}

.content{position:relative;z-index:1;display:flex;flex-direction:column;min-width:0}
.topbar{height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid rgba(56,120,245,.18);background:rgba(8,14,32,.7);backdrop-filter:blur(8px)}
.top-brand{display:flex;align-items:center;gap:10px}
.top-brand strong{font-size:16px;color:#fff;font-weight:700}
.top-sub{color:#a8c4e8;font-size:13px}
.edit-badge{margin-left:8px;padding:4px 10px;border-radius:999px;background:rgba(146,100,224,.18);color:#c8a8f0;border:1px solid rgba(146,100,224,.4);font-size:11px;font-weight:600}
.top-right{display:flex;align-items:center;gap:14px}
.top-info{display:inline-flex;align-items:center;gap:6px;color:#a8c4e8;font-size:12.5px}
.top-info i{font-style:normal;color:#5a7da8}
.top-info.ok{color:#7be9b8}
.top-info.live{color:#ff8a9a}
.top-info .dot{width:8px;height:8px;border-radius:50%;background:#33e6a1;box-shadow:0 0 10px #33e6a1}
.top-info .live-dot{background:#ff5d6c;box-shadow:0 0 10px #ff5d6c;animation:blink 1.4s infinite}
@keyframes blink{50%{opacity:.3}}
.admin-info{display:flex;align-items:center;gap:8px;padding-left:14px;border-left:1px solid rgba(56,120,245,.2)}
.avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#5a7da8,#2c4870)}
.admin-info strong{font-size:13px;color:#fff}
.admin-info small{color:#8aa6cc;font-size:11px}
.top-btn{padding:8px 18px;border:1px solid rgba(56,120,245,.3);border-radius:8px;background:rgba(20,36,68,.58);color:#dcecff;font-size:12.5px}
.top-btn:hover{background:rgba(56,190,245,.18)}
.top-btn.theme-btn{width:34px;height:34px;padding:0;display:grid;place-items:center;border-radius:50%;font-weight:800;color:#fff;background:linear-gradient(135deg,rgba(56,190,245,.32),rgba(51,230,161,.18));border-color:rgba(56,190,245,.58);box-shadow:0 0 14px rgba(56,190,245,.18)}
.top-btn.theme-btn span{display:block;font-size:16px;line-height:1}
.top-btn.admin-btn{background:linear-gradient(135deg,rgba(146,100,224,.28),rgba(108,63,184,.22));border-color:rgba(146,100,224,.5);color:#e0c8ff;font-weight:600}
.top-btn.admin-btn:hover{background:linear-gradient(135deg,rgba(146,100,224,.4),rgba(108,63,184,.32));color:#fff}

.period-tabs{display:inline-flex;border:1px solid rgba(56,120,245,.22);border-radius:8px;overflow:hidden;background:rgba(8,14,32,.5)}
.period-tabs button{padding:6px 14px;border:0;background:transparent;color:#a8c4e8;font-size:12px;border-right:1px solid rgba(56,120,245,.14);font-weight:500}
.period-tabs button:last-child{border-right:0}
.period-tabs button:hover{background:rgba(56,190,245,.1);color:#fff}
.period-tabs button.active{background:rgba(56,190,245,.22);color:#fff;font-weight:700}

main{padding:22px 24px;display:flex;flex-direction:column;gap:14px;min-width:0}
.edit-hint{margin:0;padding:10px 14px;border:1px dashed rgba(146,100,224,.4);border-radius:10px;background:rgba(146,100,224,.06);color:#c8a8f0;font-size:12.5px}

/* ===== Widget grid (12-col) ===== */
.widget-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:18px;min-width:0}
.widget{position:relative;display:flex;flex-direction:column;gap:14px;min-width:0;height:100%;transition:opacity .15s,transform .15s}
.widget-gps{align-self:stretch}
.widget.editing{cursor:grab;outline:1px dashed rgba(146,100,224,.35);outline-offset:-1px}
.widget.editing:hover{outline-color:rgba(146,100,224,.6)}
.widget.dragging{opacity:.45;transform:scale(.98)}
.widget-edit-bar{display:flex;align-items:center;gap:10px;padding:8px 12px;margin:-20px -20px 0;border-bottom:1px solid rgba(146,100,224,.3);background:rgba(146,100,224,.08)}
.drag-grip{cursor:grab;color:#c8a8f0;font-size:14px;letter-spacing:-2px}
.widget-edit-bar strong{color:#fff;font-size:12.5px;flex:1}
.widget-controls{display:flex;align-items:center;gap:4px}
.ctrl{width:26px;height:24px;padding:0;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(20,36,68,.58);color:#dcecff;font-size:12px;display:grid;place-items:center}
.ctrl:hover:not(:disabled){background:rgba(56,190,245,.18)}
.ctrl:disabled{opacity:.35;cursor:not-allowed}
.ctrl-size{padding:0 6px;font-size:11px;color:#a8c4e8;min-width:34px;text-align:center}

.panel{border:1px solid rgba(56,120,245,.18);border-radius:12px;background:linear-gradient(145deg,rgba(20,30,58,.7),rgba(12,20,42,.55));backdrop-filter:blur(10px);padding:20px;overflow:hidden}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.panel-head h2{display:flex;align-items:center;gap:10px;font-size:15px;color:#fff;font-weight:600}
.bar{display:inline-block;width:3px;height:16px;border-radius:2px;background:linear-gradient(180deg,#38bef5,#3a78ed)}
.panel-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.link-btn{padding:5px 10px;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(20,36,68,.58);color:#a8c4e8;font-size:11.5px}
.link-btn:hover{background:rgba(56,190,245,.18);color:#fff}
.chip{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border:1px solid rgba(56,120,245,.22);border-radius:999px;background:rgba(8,14,32,.6);font-size:11.5px;color:#a8c4e8}
.chip.live{color:#ff8a9a;border-color:rgba(255,93,108,.3)}
.chip.ok{color:#7be9b8;border-color:rgba(51,230,161,.3)}
.chip.danger{color:#ff8a9a;border-color:rgba(255,93,108,.4);background:rgba(255,93,108,.08)}
.chip .dot{width:6px;height:6px;border-radius:50%;background:#33e6a1;box-shadow:0 0 8px #33e6a1}
.chip .live-dot{background:#ff5d6c;box-shadow:0 0 8px #ff5d6c;animation:blink 1.4s infinite}
.big-num{font-size:18px;color:#fff;font-weight:700}
.big-num.center{font-size:22px;text-align:center;display:block;margin:6px 0}

/* ===== KPI ===== */
.kpi-row{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}
.kpi-card{position:relative;display:flex;align-items:center;gap:14px;padding:16px 18px;border:1px solid rgba(56,120,245,.18);border-radius:12px;background:rgba(8,14,32,.4);min-width:0;overflow:hidden}
.kpi-icon{width:50px;height:50px;flex-shrink:0;border-radius:50%;display:grid;place-items:center;font-size:22px;font-weight:800;color:#fff;z-index:1}
.kpi-icon.purple{background:linear-gradient(135deg,#9264e0,#6d3fb8);box-shadow:0 0 22px rgba(146,100,224,.4)}
.kpi-icon.blue{background:linear-gradient(135deg,#3a78ed,#1f4fbf);box-shadow:0 0 22px rgba(58,120,237,.4)}
.kpi-icon.green{background:linear-gradient(135deg,#33e6a1,#1ba974);box-shadow:0 0 22px rgba(51,230,161,.35)}
.kpi-icon.yellow{background:linear-gradient(135deg,#ffd166,#e0a934);box-shadow:0 0 22px rgba(255,209,102,.35);color:#3a2700}
.kpi-icon.cyan{background:linear-gradient(135deg,#38bef5,#1a8bc4);box-shadow:0 0 22px rgba(56,190,245,.4)}
.kpi-body{flex:1;min-width:0;z-index:1;overflow:hidden}
.kpi-title{margin:0 0 3px;color:#a8c4e8;font-size:11.5px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi-value{display:block;font-size:clamp(15px,1.6vw,22px);font-weight:700;color:#fff;letter-spacing:-.02em;line-height:1.15;margin:2px 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi-delta{font-size:11px;color:#7be9b8;font-style:normal;font-weight:500}
.kpi-delta.down{color:#ff8a9a}
.kpi-spark{position:absolute;right:0;bottom:0;width:60%;height:36px;opacity:.55;pointer-events:none}

/* ===== Frame ===== */
.frame-stage{position:relative;aspect-ratio:1/1;max-height:480px;border-radius:10px;overflow:hidden;background:#020916;border:1px solid rgba(56,120,245,.22)}
.frame-video{display:block;width:100%;height:100%;object-fit:cover;background:#020916}
.lane-divider{position:absolute;left:0;right:0;top:50%;height:0;border-top:1.5px dashed rgba(56,190,245,.55);box-shadow:0 0 12px rgba(56,190,245,.25);pointer-events:none;z-index:2}
.lane-tag{position:absolute;left:12px;padding:5px 10px;border-radius:6px;background:rgba(2,9,22,.78);border:1px solid rgba(56,120,245,.3);color:#dcecff;font-size:11px;font-weight:700;z-index:3}
.lane-tag.top{top:10px}.lane-tag.bottom{bottom:10px}
.lane-tag.active{background:rgba(56,190,245,.2);border-color:#38bef5;box-shadow:0 0 14px rgba(56,190,245,.35)}
.bbox{position:absolute;border:2px solid #33e6a1;border-radius:4px;box-shadow:0 0 18px rgba(51,230,161,.3),inset 0 0 6px rgba(51,230,161,.1);pointer-events:none;z-index:2;transition:all .25s}
.bbox-label{position:absolute;top:-22px;left:0;padding:2px 8px;border-radius:4px;background:rgba(2,9,22,.92);color:#fff;font-size:10.5px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap;border:1px solid rgba(56,190,245,.3)}
.frame-foot{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.frame-foot div{padding:10px 12px;border-radius:8px;background:rgba(2,9,22,.5);border:1px solid rgba(56,120,245,.14)}
.frame-foot span{display:block;color:#7290b8;font-size:10.5px;letter-spacing:.04em;text-transform:uppercase;margin-bottom:3px}
.frame-foot strong{font-size:13px;color:#fff;font-weight:700}

/* ===== GPS panel + log ===== */
.gps-map{position:relative;height:220px;border-radius:10px;border:1px solid rgba(56,120,245,.2);background:linear-gradient(rgba(70,125,255,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(70,125,255,.1) 1px,transparent 1px),#040820;background-size:24px 24px}
.gps-map.mini{height:180px}
.zone{position:absolute;left:18%;top:18%;width:64%;height:58%;border:1.5px dashed rgba(51,230,161,.6);border-radius:10px;background:rgba(51,230,161,.06)}
.gps-point{position:absolute;width:10px;height:10px;border-radius:50%;background:#7799b3;transform:translate(-50%,-50%);box-shadow:0 0 0 3px rgba(119,153,179,.18)}
.gps-point.center{background:#ffd166;box-shadow:0 0 0 3px rgba(255,209,102,.2)}
.gps-point.actual.inside{background:#33e6a1;box-shadow:0 0 12px rgba(51,230,161,.5)}
.gps-point.actual.outside{background:#ff5d6c;box-shadow:0 0 12px rgba(255,93,108,.5)}
.gps-point.trail{width:6px;height:6px;opacity:.55;box-shadow:none}
.gps-point em{position:absolute;left:14px;top:-4px;font-style:normal;font-size:10px;color:#cfe5ff;white-space:nowrap}
.health-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.health-cell{padding:8px 10px;border-radius:8px;background:rgba(2,9,22,.5);border:1px solid rgba(56,120,245,.14);display:flex;flex-direction:column;gap:2px}
.health-cell span{color:#7290b8;font-size:10px;letter-spacing:.06em}
.health-cell strong{font-size:13px;color:#fff;font-family:'JetBrains Mono',monospace}
.health-cell strong.ok{color:#33e6a1}.health-cell strong.caution{color:#ffd166}.health-cell strong.danger{color:#ff5d6c}
.gps-log-fill{flex:0 0 552px;min-height:0;height:552px;max-height:552px;overflow:scroll;border-radius:8px;border:1px solid rgba(56,120,245,.14);background:rgba(2,9,22,.4)}
.gps-log-fill::-webkit-scrollbar{width:9px;height:9px}
.gps-log-fill::-webkit-scrollbar-thumb{border-radius:999px;background:rgba(56,120,245,.45)}
.gps-log-fill::-webkit-scrollbar-track{background:rgba(2,9,22,.35)}
.log-table{width:max-content;min-width:100%;table-layout:auto;border-collapse:collapse;font-size:11.5px}
.log-table thead th{position:sticky;top:0;z-index:1;padding:7px 8px;color:#7290b8;font-size:10px;font-weight:700;background:rgba(8,14,32,.95);border-bottom:1px solid rgba(56,120,245,.18)}
.log-table th,.log-table td{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.log-table th:nth-child(1),.log-table td:nth-child(1){min-width:92px}
.log-table th:nth-child(2),.log-table td:nth-child(2){min-width:210px}
.log-table th:nth-child(3),.log-table td:nth-child(3){min-width:210px}
.log-table th:nth-child(4),.log-table td:nth-child(4){min-width:58px}
.log-table th:nth-child(5),.log-table td:nth-child(5){min-width:52px}
.log-table th:nth-child(6),.log-table td:nth-child(6){min-width:64px}
.log-table th:nth-child(7),.log-table td:nth-child(7){min-width:124px}
.log-table th:nth-child(8),.log-table td:nth-child(8){min-width:48px}
.log-table tbody tr{height:42px}
.log-table tbody td{padding:7px 8px;border-bottom:1px solid rgba(56,120,245,.06);color:#dcecff}
.log-table .time-cell{white-space:normal;line-height:1.25;text-overflow:clip}
.log-table .time-cell span{display:block}
.gps-info{display:flex;flex-direction:column;gap:6px}
.gps-info p{margin:0;display:flex;justify-content:space-between;padding:7px 12px;border-radius:8px;background:rgba(2,9,22,.5);border:1px solid rgba(56,120,245,.14);font-size:12px}
.gps-info span{color:#7290b8}

.primary-btn{padding:11px 16px;border:0;border-radius:8px;background:linear-gradient(135deg,#1b3be8,#38bef5);color:#fff;font-weight:600;font-size:13px;cursor:pointer}
.primary-btn:hover{filter:brightness(1.08)}
.primary-btn.small{padding:8px 14px;font-size:12px}
.primary-btn.wide{width:100%}

/* ===== Stats ===== */
.hour-chart{display:flex;align-items:flex-end;gap:3px;height:160px;padding:8px 0;border-bottom:1px solid rgba(56,120,245,.14)}
.bar-item{position:relative;flex:1;background:linear-gradient(180deg,#38bef5,#3a78ed);border-radius:2px 2px 0 0;min-height:2px;transition:all .15s}
.bar-item:hover{background:linear-gradient(180deg,#7be9ff,#38bef5);box-shadow:0 0 8px rgba(56,190,245,.5)}
.bar-tip{position:absolute;top:-22px;left:50%;transform:translateX(-50%);padding:2px 6px;border-radius:4px;background:rgba(2,9,22,.92);color:#fff;font-size:10px;font-family:'JetBrains Mono',monospace;white-space:nowrap;opacity:0;pointer-events:none;border:1px solid rgba(56,190,245,.3)}
.bar-item:hover .bar-tip{opacity:1}
.hour-axis{display:flex;justify-content:space-between;font-size:10px;color:#7290b8;font-family:'JetBrains Mono',monospace;padding-top:4px}

.donut-row{display:flex;justify-content:center;align-items:center;gap:18px}
.donut-svg{width:130px;height:130px;flex-shrink:0}
.donut-legend{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.donut-legend li{display:grid;grid-template-columns:10px 50px 1fr;align-items:center;gap:8px;font-size:11.5px}
.donut-legend i{width:10px;height:10px;border-radius:50%;display:inline-block}
.donut-legend span{color:#a8c4e8}
.donut-legend strong{color:#fff;text-align:right;font-weight:600;font-family:'JetBrains Mono',monospace;font-size:11px}

.esg-score{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border:1px solid rgba(51,230,161,.22);border-radius:10px;background:linear-gradient(135deg,rgba(51,230,161,.16),rgba(56,190,245,.08))}
.esg-score span{color:#7be9b8;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.esg-score strong{font-size:34px;line-height:1;color:#fff;font-weight:900;text-shadow:0 0 18px rgba(51,230,161,.28)}
.esg-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.esg-list li{display:grid;grid-template-columns:12px 1fr;gap:10px;align-items:center;padding:10px 12px;border-radius:9px;background:rgba(2,9,22,.48);border:1px solid rgba(56,120,245,.12)}
.esg-dot{width:10px;height:10px;border-radius:50%;display:inline-block;box-shadow:0 0 10px currentColor}
.esg-dot.green{background:#33e6a1;color:#33e6a1}
.esg-dot.blue{background:#38bef5;color:#38bef5}
.esg-dot.yellow{background:#ffd166;color:#ffd166}
.esg-list strong{display:block;color:#fff;font-size:14px;font-family:'JetBrains Mono',monospace;font-weight:800}
.esg-list em{display:block;margin-top:2px;color:#8aa6cc;font-size:10.5px;font-style:normal;line-height:1.35}

/* ===== Events ===== */
.event-scroll{flex:1 1 600px;min-height:600px;overflow-y:auto;border-radius:8px;border:1px solid rgba(56,120,245,.12);background:rgba(2,9,22,.3)}
.sticky-head thead th{position:sticky;top:0;z-index:1;background:rgba(8,14,32,.96);box-shadow:0 1px 0 rgba(56,120,245,.18)}
.filter-row{display:inline-flex;border:1px solid rgba(56,120,245,.22);border-radius:8px;overflow:hidden;background:rgba(8,14,32,.5)}
.filter-row button{padding:6px 12px;border:0;background:transparent;color:#a8c4e8;font-size:12px;border-right:1px solid rgba(56,120,245,.14)}
.filter-row button:last-child{border-right:0}
.filter-row button.active{background:rgba(56,190,245,.2);color:#fff;font-weight:600}

table{width:100%;border-collapse:collapse}
thead th{text-align:left;padding:9px 10px;color:#7290b8;font-size:11px;font-weight:600;border-bottom:1px solid rgba(56,120,245,.16);background:rgba(8,14,32,.4)}
tbody td{padding:10px 10px;border-bottom:1px solid rgba(56,120,245,.08);color:#dcecff;font-size:12px}
tbody tr{cursor:pointer;transition:background .12s}
tbody tr:hover,tbody tr.selected{background:rgba(56,190,245,.12)}
tbody tr:last-child td{border-bottom:0}
.empty{text-align:center;color:#5a7da8;padding:24px}
.plate{color:#fff;font-weight:700}
.status{display:inline-flex;min-width:54px;justify-content:center;padding:3px 10px;border-radius:999px;font-size:10.5px;font-weight:700;background:rgba(255,255,255,.04)}
.status.ok{background:rgba(51,230,161,.14);color:#33e6a1;border:1px solid rgba(51,230,161,.3)}
.status.caution{background:rgba(255,209,102,.14);color:#ffd166;border:1px solid rgba(255,209,102,.3)}
.status.danger{background:rgba(255,93,108,.14);color:#ff5d6c;border:1px solid rgba(255,93,108,.3)}
.status.pending{background:rgba(56,190,245,.14);color:#38bef5;border:1px solid rgba(56,190,245,.3)}

/* ===== Detail (tabs) ===== */
.detail-tabs{display:inline-flex;border:1px solid rgba(56,120,245,.22);border-radius:8px;overflow:hidden;background:rgba(8,14,32,.5);align-self:flex-start}
.detail-tabs button{padding:7px 14px;border:0;background:transparent;color:#a8c4e8;font-size:12px;border-right:1px solid rgba(56,120,245,.14);font-weight:500}
.detail-tabs button:last-child{border-right:0}
.detail-tabs button.active{background:rgba(56,190,245,.22);color:#fff;font-weight:600}
.lane-badge{display:inline-block;padding:5px 12px;border-radius:6px;background:linear-gradient(135deg,#1b3be8,#38bef5);color:#fff;font-size:11.5px;font-weight:700}
.detail-stack{display:flex;flex-direction:column;gap:12px;flex:1;min-height:0;overflow-y:auto;padding-right:4px}
.detail-card{display:flex;flex-direction:column;gap:8px;padding:12px;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:rgba(2,9,22,.5)}
.detail-card.final{background:linear-gradient(145deg,rgba(56,190,245,.12),rgba(27,59,232,.08));border-color:rgba(56,190,245,.4)}
.detail-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.badge{display:inline-flex;align-items:center;justify-content:center;padding:3px 9px;border-radius:6px;font-size:10.5px;font-weight:700;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06)}
.badge.ok{background:rgba(51,230,161,.14);color:#33e6a1;border-color:rgba(51,230,161,.3)}
.badge.caution{background:rgba(255,209,102,.14);color:#ffd166;border-color:rgba(255,209,102,.3)}
.badge.danger{background:rgba(255,93,108,.14);color:#ff5d6c;border-color:rgba(255,93,108,.3)}
.plate-img{position:relative;width:100%;aspect-ratio:5/2;border-radius:6px;overflow:hidden;background:#040820;border:1px dashed rgba(56,120,245,.28)}
.plate-img img{display:block;width:100%;height:100%;object-fit:cover}
.plate-placeholder{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:repeating-linear-gradient(45deg,rgba(56,120,245,.05) 0 6px,transparent 6px 12px),#04081a}
.placeholder-tag{padding:2px 8px;border:1px solid rgba(56,190,245,.3);border-radius:4px;color:#7be9ff;font-size:10px;font-weight:700;letter-spacing:.12em;background:rgba(56,190,245,.06)}
.placeholder-meta{color:#5a7da8;font-size:9.5px}
.plate-result{font-size:18px;font-weight:800;color:#fff;text-align:center;padding:8px;border-radius:6px;background:rgba(2,9,22,.65);letter-spacing:.04em}
.plate-final{font-size:24px;font-weight:800;color:#fff;text-align:center;padding:12px;border-radius:8px;background:rgba(2,9,22,.7);letter-spacing:.06em;border:1px solid rgba(56,190,245,.3);text-shadow:0 0 12px rgba(56,190,245,.35)}
.capture-ts{display:block;text-align:right;font-size:10px;color:#7290b8}
.fusion-meta{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.fusion-meta p{margin:0;display:flex;flex-direction:column;gap:1px;padding:6px 10px;border-radius:6px;background:rgba(2,9,22,.5)}
.fusion-meta span{color:#7290b8;font-size:10px}
.fusion-meta strong{color:#fff;font-size:12px;font-weight:600}
.conf-bar{position:relative;height:8px;border-radius:999px;background:rgba(56,120,245,.14);overflow:hidden}
.conf-bar b{display:block;height:100%;background:linear-gradient(90deg,#33e6a1,#38bef5)}
.decision{margin:0;padding:8px 12px;border-radius:8px;background:rgba(2,9,22,.5);font-size:12px;color:#a8c4e8;border:1px solid rgba(56,120,245,.18)}

/* ===== Lane ===== */
.lane-detail-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.lane-detail{padding:16px;border:1px solid rgba(56,120,245,.18);border-radius:12px;background:rgba(8,14,32,.55);display:flex;flex-direction:column;gap:14px;cursor:pointer;transition:all .15s}
.lane-detail:hover{border-color:rgba(56,190,245,.4)}
.lane-detail.tone-warn{border-color:rgba(255,209,102,.3)}
.lane-detail.tone-live{border-color:rgba(56,190,245,.3)}
.lane-detail-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.lane-name{margin:0;font-size:11.5px;color:#a8c4e8;font-weight:600;letter-spacing:.06em}
.lane-current{display:block;margin-top:4px;font-size:18px;color:#fff;font-weight:800}
.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.metric{padding:12px;border-radius:10px;background:rgba(2,9,22,.55);border:1px solid rgba(56,120,245,.14);display:flex;flex-direction:column;gap:6px}
.metric p{margin:0;color:#7290b8;font-size:10.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.metric strong{font-size:22px;color:#fff;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-.02em}
.metric strong small{font-size:11px;color:#a8c4e8;font-weight:500;margin-left:2px}
.metric strong.ok{color:#33e6a1}.metric strong.caution{color:#ffd166}.metric strong.danger{color:#ff5d6c}
.metric em{font-style:normal;font-size:10.5px;color:#7290b8}
.metric-bars{display:flex;align-items:flex-end;gap:1.5px;height:36px;padding:2px 0}
.metric-bars span{flex:1;background:linear-gradient(180deg,#38bef5,#3a78ed);border-radius:1px 1px 0 0;min-height:2px}
.cumulative-bar{height:8px;border-radius:999px;background:rgba(56,120,245,.14);overflow:hidden;margin-top:8px}
.cumulative-bar b{display:block;height:100%;background:linear-gradient(90deg,#33e6a1,#38bef5)}
.metric-spark{width:100%;height:36px}

/* ===== Anomaly ===== */
.alert-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px;max-height:380px;overflow-y:auto}
.alert-list li{display:grid;grid-template-columns:4px 1fr auto;gap:12px;align-items:center;padding:12px;border-radius:10px;background:rgba(8,14,32,.55);border:1px solid rgba(56,120,245,.16)}
.alert-bar{width:4px;align-self:stretch;border-radius:999px;background:#7799b3}
.alert-list li.critical{background:rgba(255,93,108,.08);border-color:rgba(255,93,108,.32)}
.alert-list li.critical .alert-bar{background:#ff5d6c}
.alert-list li.warn{background:rgba(255,209,102,.08);border-color:rgba(255,209,102,.32)}
.alert-list li.warn .alert-bar{background:#ffd166}
.alert-list li.info .alert-bar{background:#38bef5}
.alert-row{display:flex;justify-content:space-between;gap:8px;align-items:center}
.alert-row strong{font-size:13px;color:#fff;font-weight:600}
.alert-body p{margin:2px 0 0;font-size:12px;color:#a8c4e8}
.row-btn{padding:5px 12px;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(20,36,68,.58);color:#a8c4e8;font-size:11.5px}
.row-btn:hover{background:rgba(56,190,245,.18);color:#fff}

/* ===== Operator subpages ===== */
.ops-subpage{display:flex;flex-direction:column;gap:16px}
.subpage-hero{display:flex;align-items:center;justify-content:space-between;gap:20px;min-height:118px}
.subpage-kicker{margin:0 0 6px;color:#38bef5;font-size:11px;font-weight:800;letter-spacing:.16em}
.subpage-hero h2{margin:0 0 6px;color:#fff;font-size:26px;font-weight:800}
.subpage-hero span{color:#a8c4e8;font-size:13px}
.subpage-panel{min-height:560px;display:flex;flex-direction:column;gap:16px}
.subpage-two{display:grid;grid-template-columns:minmax(420px,1.05fr) minmax(320px,.95fr);gap:16px;align-items:stretch}
.lane-ocr-layout{display:grid;grid-template-columns:320px 1fr;gap:16px;align-items:stretch}
.lane-detect-list{display:flex;flex-direction:column;gap:12px}
.lane-detect-card{min-height:136px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:7px;padding:16px;border:1px solid rgba(56,120,245,.18);border-radius:12px;background:rgba(2,9,22,.5);text-align:left}
.lane-detect-card:hover,.lane-detect-card.active{border-color:rgba(56,190,245,.55);background:rgba(56,190,245,.12)}
.lane-detect-title{color:#8aa6cc;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.lane-detect-card strong{color:#fff;font-size:22px}
.lane-detect-card em{font-style:normal;font-weight:800}
.lane-detect-card small{color:#7290b8;font-size:11.5px}
.lane-detect-detail{display:grid;grid-template-columns:minmax(420px,1.05fr) minmax(320px,.95fr);gap:16px;align-items:stretch}
.subpage-frame{aspect-ratio:16/9;max-height:none}
.subpage-info-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.subpage-info-grid p{margin:0;display:flex;flex-direction:column;justify-content:center;gap:6px;min-height:84px;padding:14px;border:1px solid rgba(56,120,245,.16);border-radius:10px;background:rgba(2,9,22,.5)}
.subpage-info-grid span{color:#7290b8;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.subpage-info-grid strong{color:#fff;font-size:17px;font-weight:800}
.subpage-table-scroll{min-height:520px;max-height:620px}
.subpage-alerts{max-height:none}
.subpage-health{grid-template-columns:repeat(4,minmax(0,1fr))}
.settings-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.settings-grid label{display:flex;flex-direction:column;gap:7px;padding:14px;border:1px solid rgba(56,120,245,.16);border-radius:10px;background:rgba(2,9,22,.5)}
.settings-grid span{color:#7290b8;font-size:11px;font-weight:700;letter-spacing:.06em}
.settings-grid input{height:38px;border:1px solid rgba(56,120,245,.22);border-radius:8px;background:rgba(8,14,32,.72);color:#fff;padding:0 12px}
.review-modal-body{display:flex;flex-direction:column;gap:14px}
.modal-field{display:flex;flex-direction:column;gap:6px}
.modal-field span{color:#7290b8;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.modal-field select,.modal-field textarea{border:1px solid rgba(56,120,245,.22);border-radius:8px;background:rgba(2,9,22,.5);color:#fff;padding:10px 12px;resize:vertical}
.modal{width:min(720px,94vw)}
.event-modal{width:min(1220px,96vw);max-height:90vh;overflow:auto}
.event-modal-grid{display:grid;grid-template-columns:repeat(2,minmax(540px,1fr));gap:16px}
.gps-modal-card{min-width:0;overflow:hidden}
.modal-gps-map{height:230px}
.modal-gps-info{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
.settings-grid input[readonly]{cursor:default;opacity:.72}
.event-modal .detail-card{min-width:0}
.event-modal .detail-head,
.event-modal .fusion-meta p,
.event-modal .gps-info p,
.review-modal-body .subpage-info-grid p{white-space:nowrap}
.event-modal .plate-result,
.event-modal .plate-final{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.event-modal .placeholder-meta,
.event-modal .capture-ts,
.modal-field span{white-space:nowrap}

.modal-bg{position:fixed;inset:0;display:grid;place-items:center;background:rgba(2,8,20,.72);backdrop-filter:blur(6px);z-index:50}
.modal-copy{margin:0;font-size:12.5px;color:#a8c4e8}
.zone-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.zone-grid label{display:flex;flex-direction:column;gap:4px;font-size:11px;color:#7290b8}
.zone-grid input{padding:8px 10px;border:1px solid rgba(56,120,245,.22);border-radius:8px;background:rgba(2,9,22,.5);color:#fff;font-size:13px}
.zone-grid input:focus{outline:0;border-color:#38bef5}

/* ===== Light mode ===== */
.ops-shell.light{color:#223245;background:radial-gradient(ellipse at 18% 8%,rgba(56,120,245,.14),transparent 38%),radial-gradient(ellipse at 82% 92%,rgba(51,230,161,.10),transparent 38%),#eef5ff}
.ops-shell.light .particle{background:rgba(52,102,168,.32);box-shadow:0 0 6px rgba(52,102,168,.22)}
.ops-shell.light .sidebar,.ops-shell.light .topbar{background:rgba(248,251,255,.86);border-color:rgba(42,113,190,.2);box-shadow:0 14px 38px rgba(24,57,100,.08)}
.ops-shell.light .panel,.ops-shell.light .kpi-card,.ops-shell.light .lane-detail,.ops-shell.light .metric,.ops-shell.light .detail-card,.ops-shell.light .health-cell,.ops-shell.light .quick-section{background:rgba(255,255,255,.78);border-color:rgba(42,113,190,.18);box-shadow:0 12px 34px rgba(24,57,100,.08)}
.ops-shell.light .top-brand strong,.ops-shell.light .brand-header strong,.ops-shell.light .panel-head h2,.ops-shell.light .big-num,.ops-shell.light .kpi-value,.ops-shell.light .admin-info strong,.ops-shell.light .frame-foot strong,.ops-shell.light .health-cell strong,.ops-shell.light .esg-list strong,.ops-shell.light .donut-legend strong,.ops-shell.light .plate-result,.ops-shell.light .plate-final,.ops-shell.light .fusion-meta strong,.ops-shell.light .lane-current,.ops-shell.light .metric strong,.ops-shell.light .alert-row strong{color:#102033;text-shadow:none}
.ops-shell.light .top-sub,.ops-shell.light .top-info,.ops-shell.light .brand-header span,.ops-shell.light .brand-header strong small,.ops-shell.light .side-nav button,.ops-shell.light .submenu button,.ops-shell.light .quick-section p,.ops-shell.light .kpi-title,.ops-shell.light .chip,.ops-shell.light .muted,.ops-shell.light .capture-ts,.ops-shell.light .modal-copy{color:#526b88}
.ops-shell.light .top-btn,.ops-shell.light .link-btn,.ops-shell.light .quick-pill,.ops-shell.light .ctrl,.ops-shell.light .row-btn,.ops-shell.light .filter-row,.ops-shell.light .period-tabs,.ops-shell.light .detail-tabs{background:rgba(235,243,255,.9);border-color:rgba(42,113,190,.24);color:#24425f}
.ops-shell.light .top-btn.theme-btn{color:#05233d;background:linear-gradient(135deg,#ffffff,#dcecff);border-color:rgba(33,98,170,.42);box-shadow:0 4px 14px rgba(24,57,100,.14)}
.ops-shell.light .top-info.ok,.ops-shell.light .chip.ok{color:#087a50}
.ops-shell.light .gps-map,.ops-shell.light .plate-img,.ops-shell.light .plate-placeholder{background-color:#dfeeff}
.ops-shell.light .frame-stage{background:#d9e8f7;border-color:rgba(34,93,156,.28);box-shadow:inset 0 0 0 1px rgba(255,255,255,.72)}
.ops-shell.light .frame-video{background:#d9e8f7}
.ops-shell.light .lane-tag,.ops-shell.light .bbox-label{background:rgba(255,255,255,.9);border-color:rgba(34,93,156,.28);color:#102033;text-shadow:none}
.ops-shell.light .lane-tag.active{background:rgba(22,131,255,.16);border-color:#1683ff;color:#073a68;box-shadow:0 0 12px rgba(22,131,255,.18)}
.ops-shell.light .frame-foot div{background:rgba(255,255,255,.84);border-color:rgba(34,93,156,.16);box-shadow:0 8px 18px rgba(24,57,100,.06)}
.ops-shell.light .frame-foot span,.ops-shell.light .health-cell span,.ops-shell.light .gps-info span,.ops-shell.light .fusion-meta span,.ops-shell.light .hour-axis,.ops-shell.light .placeholder-meta{color:#49637f}
.ops-shell.light .gps-log-fill,.ops-shell.light .event-scroll,.ops-shell.light .detail-stack,.ops-shell.light .gps-info p,.ops-shell.light .fusion-meta p,.ops-shell.light .decision{background:rgba(248,251,255,.82);border-color:rgba(42,113,190,.16)}
.ops-shell.light .log-table thead th,.ops-shell.light .sticky-head thead th{background:rgba(229,240,255,.96);color:#4d6887;border-color:rgba(42,113,190,.2)}
.ops-shell.light .log-table tbody td,.ops-shell.light .data-table td{color:#223245;border-color:rgba(42,113,190,.08)}
.ops-shell.light .zone-grid input{background:#fff;color:#102033;border-color:rgba(42,113,190,.24)}
.ops-shell.light .side-nav button:hover,.ops-shell.light .side-nav button.active,.ops-shell.light .submenu button.active{background:rgba(22,131,255,.12);color:#073a68;box-shadow:inset 0 0 0 1px rgba(22,131,255,.18)}
.ops-shell.light .side-nav button .ico,.ops-shell.light .submenu button{color:#49637f}
.ops-shell.light .quick-pill,.ops-shell.light .quick-pill.on{color:#143653}
.ops-shell.light .quick-pill.primary,.ops-shell.light .primary-btn{color:#fff;background:linear-gradient(135deg,#1769d8,#16a6d8)}
.ops-shell.light .chip{background:rgba(255,255,255,.76);border-color:rgba(42,113,190,.18);color:#38536f}
.ops-shell.light .chip.live,.ops-shell.light .top-info.live{color:#b3203a}
.ops-shell.light .status.ok,.ops-shell.light .badge.ok,.ops-shell.light .health-cell strong.ok{color:#087a50}
.ops-shell.light .status.caution,.ops-shell.light .badge.caution,.ops-shell.light .health-cell strong.caution{color:#9a6700}
.ops-shell.light .status.danger,.ops-shell.light .badge.danger,.ops-shell.light .health-cell strong.danger{color:#b3203a}
.ops-shell.light .kpi-card{background:linear-gradient(145deg,rgba(255,255,255,.9),rgba(239,247,255,.82));border-color:rgba(34,93,156,.18)}
.ops-shell.light .kpi-delta,.ops-shell.light .top-info.ok{color:#087a50}
.ops-shell.light .kpi-delta.down{color:#b3203a}
.ops-shell.light .bar-item,.ops-shell.light .metric-bars span,.ops-shell.light .cumulative-bar b,.ops-shell.light .conf-bar b{filter:saturate(1.05)}
.ops-shell.light .cumulative-bar,.ops-shell.light .conf-bar{background:rgba(42,113,190,.14)}
.ops-shell.light .detail-card.final{background:linear-gradient(145deg,rgba(22,131,255,.12),rgba(51,230,161,.08));border-color:rgba(22,131,255,.24)}
.ops-shell.light .plate-final,.ops-shell.light .plate-result{background:rgba(255,255,255,.82);border-color:rgba(34,93,156,.18)}
.ops-shell.light .alert-list li{background:rgba(255,255,255,.74);border-color:rgba(42,113,190,.14)}
.ops-shell.light .alert-body p,.ops-shell.light .decision{color:#38536f}
.ops-shell.light .modal{background:rgba(255,255,255,.94)}
.ops-shell.light .subpage-hero h2,
.ops-shell.light .subpage-info-grid strong,
.ops-shell.light .settings-grid input,
.ops-shell.light .lane-detect-card strong,
.ops-shell.light .modal-field select,
.ops-shell.light .modal-field textarea{color:#102033}
.ops-shell.light .subpage-hero span,
.ops-shell.light .subpage-info-grid span,
.ops-shell.light .settings-grid span,
.ops-shell.light .lane-detect-title,
.ops-shell.light .lane-detect-card small,
.ops-shell.light .modal-field span{color:#425b78}
.ops-shell.light .subpage-info-grid p,
.ops-shell.light .settings-grid label,
.ops-shell.light .lane-detect-card{background:rgba(255,255,255,.78);border-color:rgba(42,113,190,.18)}
.ops-shell.light .settings-grid input,
.ops-shell.light .modal-field select,
.ops-shell.light .modal-field textarea{background:#fff;border-color:rgba(42,113,190,.24)}
.ops-shell.light .lane-detect-card.active{background:rgba(22,131,255,.12);border-color:rgba(22,131,255,.34)}
.ops-shell.light .settings-grid input[readonly]{background:rgba(239,247,255,.78)}

/* 라이트 모드 최종 대비 보정 */
.ops-shell.light .panel *,
.ops-shell.light .sidebar *,
.ops-shell.light .topbar *,
.ops-shell.light .modal * {
  text-shadow: none;
}

.ops-shell.light .panel,
.ops-shell.light .panel p,
.ops-shell.light .panel span,
.ops-shell.light .panel strong,
.ops-shell.light .panel em,
.ops-shell.light .panel td,
.ops-shell.light .panel th,
.ops-shell.light .sidebar,
.ops-shell.light .sidebar p,
.ops-shell.light .sidebar span,
.ops-shell.light .topbar,
.ops-shell.light .topbar span,
.ops-shell.light .modal,
.ops-shell.light .modal p,
.ops-shell.light .modal span {
  color: #17283b;
}

.ops-shell.light .muted,
.ops-shell.light .small,
.ops-shell.light .kpi-title,
.ops-shell.light .top-sub,
.ops-shell.light .capture-ts,
.ops-shell.light .hour-axis,
.ops-shell.light .placeholder-meta,
.ops-shell.light .frame-foot span,
.ops-shell.light .gps-info span,
.ops-shell.light .fusion-meta span,
.ops-shell.light .health-cell span,
.ops-shell.light .metric p,
.ops-shell.light .metric em,
.ops-shell.light .donut-legend span,
.ops-shell.light .esg-list em {
  color: #425b78;
}

.ops-shell.light button,
.ops-shell.light .top-btn,
.ops-shell.light .link-btn,
.ops-shell.light .row-btn,
.ops-shell.light .ctrl,
.ops-shell.light .quick-pill,
.ops-shell.light .filter-row button,
.ops-shell.light .period-tabs button,
.ops-shell.light .detail-tabs button {
  color: #12324f;
  background-color: rgba(239, 247, 255, 0.95);
}

.ops-shell.light button.active,
.ops-shell.light .filter-row button.active,
.ops-shell.light .period-tabs button.active,
.ops-shell.light .detail-tabs button.active,
.ops-shell.light .quick-pill.on {
  color: #063963;
  background: rgba(22, 131, 255, 0.16);
  border-color: rgba(22, 131, 255, 0.34);
}

.ops-shell.light .primary-btn,
.ops-shell.light .quick-pill.primary,
.ops-shell.light .lane-badge {
  color: #fff;
}

.ops-shell.light .chip,
.ops-shell.light .status,
.ops-shell.light .badge,
.ops-shell.light .lane-badge,
.ops-shell.light .edit-badge {
  color: #17324f;
  background-color: rgba(255, 255, 255, 0.82);
}

.ops-shell.light .status.caution,
.ops-shell.light .badge.caution,
.ops-shell.light .chip.caution,
.ops-shell.light .health-cell strong.caution {
  color: #7a5200;
}

.ops-shell.light .status.ok,
.ops-shell.light .badge.ok,
.ops-shell.light .chip.ok,
.ops-shell.light .health-cell strong.ok,
.ops-shell.light .top-info.ok {
  color: #066c47;
}

.ops-shell.light .status.danger,
.ops-shell.light .badge.danger,
.ops-shell.light .chip.danger,
.ops-shell.light .top-info.live {
  color: #a31932;
}

.ops-shell.light .kpi-icon,
.ops-shell.light .brand-mark,
.ops-shell.light .lane-badge,
.ops-shell.light .primary-btn {
  color: #fff;
}

.ops-shell.light .bar-tip {
  color: #102033;
  background: rgba(255, 255, 255, 0.96);
  border-color: rgba(22, 131, 255, 0.28);
  box-shadow: 0 8px 20px rgba(24, 57, 100, 0.14);
}
</style>
