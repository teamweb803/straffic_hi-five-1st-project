<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const THEME_STORAGE_KEY = 'hifive.dashboard.theme'
const themeMode = ref(localStorage.getItem(THEME_STORAGE_KEY) || 'dark')
const nowText = ref('')
const selectedEvent = ref(null)
const selectedResolution = ref(null)
const selectedPeriod = ref('day')
const eventListMode = ref('all')

const isLightMode = computed(() => themeMode.value === 'light')

const centerName = computed(() => {
  const center = String(route.query.center ?? 'SEOUL-TOLL')
  const names = {
    'SEOUL-TOLL': '서울 톨게이트',
    'SUWON-TOLL': '수원 톨게이트',
    'DAEJEON-TOLL': '대전 톨게이트',
    'DAEGU-TOLL': '대구 톨게이트',
    'BUSAN-TOLL': '부산 톨게이트',
    'GWANGJU-TOLL': '광주 톨게이트',
    'GANGNEUNG-TOLL': '강릉 톨게이트',
    'JEJU-TOLL': '제주 톨게이트'
  }
  return names[center] ?? '서울 톨게이트'
})

const alertCards = [
  { title: '미정산 차량', value: 36, note: '즉시 확인 8건', tone: 'danger', icon: 'PAY' },
  { title: 'OCR 검수', value: 12, note: '신뢰도 70% 미만', tone: 'warn', icon: 'OCR' },
  { title: 'GPS 구역 경고', value: 5, note: '통과 판정 보류', tone: 'orange', icon: 'GPS' },
  { title: '시스템 지연', value: 2, note: 'Edge 1, DB 1', tone: 'violet', icon: 'SYS' }
]

const events = [
  { id: 1, time: '10:21:03', lane: '1차로', plate: '12가3456', front: { plate: '12가3456', conf: 97 }, rear: { plate: '12가3456', conf: 95 }, final: { plate: '12가3456', conf: 97, source: 'front/rear match', agreement: 1.0 }, status: '정상처리', severity: 'normal', issue: '없음', settlement: '결제완료', gps: { result: '통과', offset: '0.9m', speed: 42, inside: true, latlng: '37.401073 / 127.104272' } },
  { id: 2, time: '10:22:15', lane: '2차로', plate: '33나9029', front: { plate: '33나9029', conf: 62 }, rear: { plate: '33나902?', conf: 54 }, final: { plate: '33나9029', conf: 62, source: 'front priority', agreement: 0.66 }, status: 'OCR 검수', severity: 'warning', issue: '전후면 번호판 불일치', settlement: '미정산', gps: { result: '통과', offset: '1.8m', speed: 35, inside: true, latlng: '37.401079 / 127.104279' } },
  { id: 3, time: '10:23:07', lane: '1차로', plate: '48다7720', front: { plate: '48다7720', conf: 91 }, rear: { plate: '48다7720', conf: 88 }, final: { plate: '48다7720', conf: 91, source: 'vote fusion', agreement: 1.0 }, status: '정산대기', severity: 'caution', issue: '결제 승인 지연', settlement: '승인대기', gps: { result: '통과', offset: '1.2m', speed: 38, inside: true, latlng: '37.401084 / 127.104286' } },
  { id: 4, time: '10:24:42', lane: '2차로', plate: '71라1208', front: { plate: '71라1208', conf: 81 }, rear: { plate: '71라1208', conf: 79 }, final: { plate: '71라1208', conf: 81, source: 'front/rear match', agreement: 1.0 }, status: 'GPS 경고', severity: 'danger', issue: 'GPS 구역 경계 이탈', settlement: '보류', gps: { result: '구역 이탈', offset: '6.7m', speed: 44, inside: false, latlng: '37.401298 / 127.104710' } },
  { id: 5, time: '10:25:19', lane: '1차로', plate: '미검출', front: { plate: '미검출', conf: 38 }, rear: { plate: '19바7781', conf: 73 }, final: { plate: '19바7781', conf: 73, source: 'rear fallback', agreement: 0.42 }, status: '오류', severity: 'danger', issue: '전면 번호판 미검출', settlement: '미정산', gps: { result: '통과', offset: '2.4m', speed: 31, inside: true, latlng: '37.401236 / 127.104540' } },
  { id: 6, time: '10:26:04', lane: '2차로', plate: '82사3310', front: { plate: '82사3310', conf: 76 }, rear: { plate: '82사3310', conf: 71 }, final: { plate: '82사3310', conf: 76, source: 'edge delayed', agreement: 0.94 }, status: '전송지연', severity: 'warning', issue: 'Edge 전송 지연', settlement: '보류', gps: { result: '통과', offset: '1.5m', speed: 33, inside: true, latlng: '37.401248 / 127.104552' } },
  { id: 7, time: '10:26:38', lane: '1차로', plate: '29하6712', front: { plate: '29하6712', conf: 86 }, rear: { plate: '29하6712', conf: 83 }, final: { plate: '29하6712', conf: 86, source: 'vote fusion', agreement: 1.0 }, status: '정산대기', severity: 'caution', issue: '정산 API 응답 지연', settlement: '승인대기', gps: { result: '통과', offset: '1.1m', speed: 37, inside: true, latlng: '37.401260 / 127.104568' } },
  { id: 8, time: '10:27:12', lane: '2차로', plate: '55고2281', front: { plate: '55고2281', conf: 69 }, rear: { plate: '55고2281', conf: 67 }, final: { plate: '55고2281', conf: 69, source: 'low confidence', agreement: 0.82 }, status: 'OCR 검수', severity: 'warning', issue: '야간 프레임 흔들림', settlement: '미정산', gps: { result: '통과', offset: '2.0m', speed: 29, inside: true, latlng: '37.401271 / 127.104579' } }
]

const criticalEvents = computed(() => events.filter((event) => event.severity !== 'normal'))
const displayedEvents = computed(() => eventListMode.value === 'instant' ? criticalEvents.value : events)
const selectedPreviewEvent = ref(events[1])
const displayLaneDetections = computed(() => {
  const event = selectedPreviewEvent.value ?? events[0]
  const oppositeLane = events.find((item) => item.lane !== event.lane && item.severity !== 'normal') ?? events.find((item) => item.lane !== event.lane) ?? event
  return [event, oppositeLane].map((item) => ({
    lane: item.lane,
    plate: item.final.plate,
    status: item.issue,
    time: item.time,
    confidence: item.final.conf,
    tone: item.severity,
    note: `${item.status} · ${item.settlement}`,
    event: item
  }))
})

const settlementByPeriod = {
  day: {
    label: '일간',
    total: '₩2,450,800',
    count: '1,248',
    paid: 2104600,
    unpaid: 220400,
    hold: 125800,
    bars: [
      { label: '08시', ratio: 32, paidCount: 108, amount: 210400, unpaidCount: 4, holdCount: 2 },
      { label: '10시', ratio: 58, paidCount: 184, amount: 362800, unpaidCount: 7, holdCount: 4 },
      { label: '12시', ratio: 75, paidCount: 246, amount: 481600, unpaidCount: 9, holdCount: 5 },
      { label: '14시', ratio: 66, paidCount: 211, amount: 420200, unpaidCount: 6, holdCount: 3 },
      { label: '16시', ratio: 84, paidCount: 269, amount: 530700, unpaidCount: 8, holdCount: 4 },
      { label: '18시', ratio: 48, paidCount: 156, amount: 294900, unpaidCount: 2, holdCount: 1 }
    ]
  },
  week: {
    label: '주간',
    total: '₩16,824,200',
    count: '8,936',
    paid: 14982000,
    unpaid: 1126500,
    hold: 715700,
    bars: [
      { label: '월', ratio: 64, paidCount: 1186, amount: 2240800, unpaidCount: 132, holdCount: 42 },
      { label: '화', ratio: 72, paidCount: 1328, amount: 2504200, unpaidCount: 146, holdCount: 51 },
      { label: '수', ratio: 69, paidCount: 1274, amount: 2391200, unpaidCount: 138, holdCount: 48 },
      { label: '목', ratio: 81, paidCount: 1490, amount: 2816200, unpaidCount: 151, holdCount: 59 },
      { label: '금', ratio: 92, paidCount: 1698, amount: 3198800, unpaidCount: 176, holdCount: 66 },
      { label: '토', ratio: 58, paidCount: 1034, amount: 1942200, unpaidCount: 119, holdCount: 35 },
      { label: '일', ratio: 44, paidCount: 812, amount: 1502800, unpaidCount: 91, holdCount: 28 }
    ]
  },
  month: {
    label: '월간',
    total: '₩72,618,900',
    count: '38,402',
    paid: 65431200,
    unpaid: 4902300,
    hold: 2285400,
    bars: [
      { label: '1주', ratio: 74, paidCount: 7120, amount: 13288400, unpaidCount: 812, holdCount: 286 },
      { label: '2주', ratio: 82, paidCount: 7984, amount: 15142600, unpaidCount: 904, holdCount: 321 },
      { label: '3주', ratio: 88, paidCount: 8520, amount: 16230500, unpaidCount: 980, holdCount: 352 },
      { label: '4주', ratio: 79, paidCount: 7630, amount: 14408600, unpaidCount: 872, holdCount: 304 },
      { label: '5주', ratio: 66, paidCount: 6392, amount: 11930800, unpaidCount: 704, holdCount: 242 }
    ]
  }
}

const selectedSettlement = computed(() => settlementByPeriod[selectedPeriod.value])
const settlementTotalNumber = computed(() => selectedSettlement.value.paid + selectedSettlement.value.unpaid + selectedSettlement.value.hold)
const settlementSlices = computed(() => {
  const item = selectedSettlement.value
  return [
    { label: '결제완료', value: item.paid, tone: 'ok', width: Math.round((item.paid / settlementTotalNumber.value) * 100) },
    { label: '미납', value: item.unpaid, tone: 'danger', width: Math.round((item.unpaid / settlementTotalNumber.value) * 100) },
    { label: '보류', value: item.hold, tone: 'caution', width: Math.round((item.hold / settlementTotalNumber.value) * 100) }
  ]
})

const exceptionQueue = [
  { eventId: 2, plate: '33나9029', type: 'OCR', reason: '전후면 번호판 불일치', age: '2분 전', level: 'warn' },
  { eventId: 5, plate: '미검출', type: 'OCR', reason: '전면 번호판 미검출', age: '4분 전', level: 'danger' },
  { eventId: 4, plate: '71라1208', type: 'GPS', reason: '감지 구역 6.7m 이탈', age: '6분 전', level: 'danger' },
  { eventId: 3, plate: '48다7720', type: 'PAY', reason: '결제 승인 지연', age: '8분 전', level: 'caution' },
  { eventId: 6, plate: '82사3310', type: 'SYS', reason: 'Edge 전송 지연', age: '12분 전', level: 'warn' },
  { eventId: 7, plate: '29하6712', type: 'PAY', reason: '정산 API 응답 지연', age: '15분 전', level: 'caution' },
  { eventId: 8, plate: '55고2281', type: 'OCR', reason: '야간 프레임 흔들림', age: '18분 전', level: 'warn' }
]

const laneDetections = [
  {
    lane: '1차로',
    plate: '19바7781',
    status: '전면 미검출',
    time: '10:25:19',
    confidence: 73,
    tone: 'danger',
    note: '후면 번호판 기준 보정 필요'
  },
  {
    lane: '2차로',
    plate: '33나9029',
    status: '전후면 불일치',
    time: '10:22:15',
    confidence: 62,
    tone: 'warn',
    note: '앞/뒤 번호판 재검수 필요'
  }
]

const gpsLogs = [
  { time: '26-05-12 10:25:19', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401236 / 127.104540', speed: '31.0', heading: '89.1', fix: '3D', sat: 9, signal: 'GOOD' },
  { time: '26-05-12 10:24:42', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401298 / 127.104710', speed: '44.0', heading: '91.6', fix: '3D', sat: 8, signal: 'OUT' },
  { time: '26-05-12 10:23:07', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401084 / 127.104286', speed: '38.0', heading: '87.2', fix: '3D', sat: 9, signal: 'GOOD' },
  { time: '26-05-12 10:22:15', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401079 / 127.104279', speed: '35.0', heading: '90.0', fix: '3D', sat: 9, signal: 'GOOD' },
  { time: '26-05-12 10:21:03', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401073 / 127.104272', speed: '42.0', heading: '84.4', fix: '3D', sat: 10, signal: 'GOOD' },
  { time: '26-05-12 10:20:31', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401061 / 127.104251', speed: '39.0', heading: '86.3', fix: '3D', sat: 8, signal: 'GOOD' },
  { time: '26-05-12 10:19:52', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401048 / 127.104229', speed: '29.0', heading: '88.0', fix: '2D', sat: 6, signal: 'LOW' },
  { time: '26-05-12 10:19:10', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401038 / 127.104214', speed: '27.0', heading: '88.5', fix: '3D', sat: 8, signal: 'GOOD' },
  { time: '26-05-12 10:18:41', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401021 / 127.104188', speed: '25.0', heading: '87.1', fix: '3D', sat: 8, signal: 'GOOD' },
  { time: '26-05-12 10:18:03', device: 'PICO2W-NEO7M-RC-01', latlng: '37.400998 / 127.104160', speed: '22.0', heading: '86.2', fix: '3D', sat: 7, signal: 'GOOD' }
]

let timer = null

function toggleThemeMode() {
  themeMode.value = isLightMode.value ? 'dark' : 'light'
  localStorage.setItem(THEME_STORAGE_KEY, themeMode.value)
}

function updateTime() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function formatWon(value) {
  return `₩${Number(value).toLocaleString()}`
}

function confClass(conf) {
  if (conf >= 85) return 'ok'
  if (conf >= 70) return 'caution'
  return 'danger'
}

function toneClass(value) {
  const text = String(value)
  if (['정상처리', '결제완료', '통과', '3D', 'GOOD', 'normal'].includes(text)) return 'ok'
  if (['정산대기', '승인대기', 'caution'].includes(text)) return 'caution'
  if (['OCR 검수', '전송지연', 'warning', 'LOW'].includes(text)) return 'warn'
  if (['GPS 경고', '오류', '미정산', '보류', '구역 이탈', 'OUT', 'danger'].includes(text)) return 'danger'
  return 'info'
}

function openEventDetail(event) {
  selectedEvent.value = event
}

function selectPreviewEvent(event) {
  selectedPreviewEvent.value = event
}

function openRowDetail(event) {
  if (eventListMode.value === 'instant') {
    selectedResolution.value = event
    return
  }
  selectedEvent.value = event
}

function openQueueDetail(item) {
  const event = events.find((target) => target.id === item.eventId)
  if (event) selectedResolution.value = event
}

function closeEventDetail() {
  selectedEvent.value = null
}

function closeResolution() {
  selectedResolution.value = null
}

function handleResolution(action) {
  const labels = {
    approve: '승인 처리되었습니다.',
    exception: '예외 처리되었습니다.',
    recheck: '재검수 대기열로 이동했습니다.'
  }
  window.alert(labels[action])
  selectedResolution.value = null
}

function logout() {
  window.alert('로그아웃 되었습니다.')
  router.push('/')
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
  <div class="compact-dashboard" :class="{ light: isLightMode }">
    <header class="compact-header">
      <div class="brand">
        <span class="brand-mark">H</span>
        <div>
          <strong>HI-FIVE Control Center</strong>
          <small>{{ centerName }} · 정산/이상징후 집중 관제</small>
        </div>
      </div>

      <div class="header-meta">
        <span>{{ nowText }}</span>
        <span><i class="live-dot"></i>서버 정상</span>
        <span>관리자 admin</span>
        <button class="icon-btn" type="button" :title="isLightMode ? '다크 모드' : '라이트 모드'" @click="toggleThemeMode">
          {{ isLightMode ? '☾' : '☀' }}
        </button>
        <button type="button" @click="router.push('/master-admin')">회원 대시보드</button>
        <button type="button" @click="logout">로그아웃</button>
      </div>
    </header>

    <main class="compact-main">
      <section class="alert-row">
        <article v-for="card in alertCards" :key="card.title" class="alert-card" :class="card.tone">
          <i>{{ card.icon }}</i>
          <div>
            <span>{{ card.title }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.note }}</small>
          </div>
        </article>
      </section>

      <section class="control-grid">
        <article class="panel event-panel">
          <div class="panel-title with-tabs">
            <div>
              <h2>실시간 통행 이벤트</h2>
              <p>{{ eventListMode === 'all' ? '기존 통행 이벤트 로그' : '즉시 처리 대상 리스트' }} · 행 클릭 시 상세 팝업</p>
            </div>
            <div class="period-tabs">
              <button type="button" :class="{ active: eventListMode === 'all' }" @click="eventListMode = 'all'">통행 이벤트</button>
              <button type="button" :class="{ active: eventListMode === 'instant' }" @click="eventListMode = 'instant'">즉시 처리</button>
            </div>
          </div>

          <div v-if="eventListMode === 'all'" class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th class="open-col"></th>
                  <th>TIME</th>
                  <th>LANE</th>
                  <th>PLATE</th>
                  <th>CONF</th>
                  <th>STATUS</th>
                  <th>PAY</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="event in displayedEvents" :key="event.id" :class="[toneClass(event.severity), { selected: selectedPreviewEvent?.id === event.id }]" @click="selectPreviewEvent(event)">
                  <td class="row-open-cell">
                    <button type="button" @click.stop="openEventDetail(event)">열기</button>
                  </td>
                  <td>{{ event.time }}</td>
                  <td>{{ event.lane }}</td>
                  <td class="mono strong">{{ event.plate }}</td>
                  <td>{{ event.final.conf }}%</td>
                  <td><span :class="toneClass(event.status)">{{ event.status }}</span></td>
                  <td><span :class="toneClass(event.settlement)">{{ event.settlement }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="instant-scroll">
            <button
              v-for="event in criticalEvents"
              :key="`instant-${event.id}`"
              class="instant-card"
              :class="toneClass(event.severity)"
              type="button"
              @click="openRowDetail(event)"
            >
              <i>{{ event.status }}</i>
              <div class="instant-main">
                <div>
                  <strong class="mono">{{ event.final.plate }}</strong>
                  <span>{{ event.lane }} · {{ event.time }}</span>
                </div>
                <p>{{ event.issue }}</p>
                <small>
                  앞 {{ event.front.plate }} / {{ event.front.conf }}%
                  · 뒤 {{ event.rear.plate }} / {{ event.rear.conf }}%
                  · GPS {{ event.gps.result }} {{ event.gps.offset }}
                </small>
              </div>
              <em :class="toneClass(event.settlement)">{{ event.settlement }}</em>
            </button>
          </div>
        </article>

        <article class="panel issue-panel">
          <div class="panel-title">
            <div>
              <h2>오류 처리 통계</h2>
              <p>즉시 처리 대상은 좌측 리스트에서 확인</p>
            </div>
          </div>

          <div class="priority-meter">
            <div class="meter-core">
              <strong>55</strong>
              <span>전체 이슈</span>
            </div>
            <div class="meter-ring"></div>
          </div>

          <div class="issue-visual-list">
            <p><span class="danger">미정산</span><i style="--w: 75%"></i><b>36</b></p>
            <p><span class="warn">OCR</span><i style="--w: 60%"></i><b>12</b></p>
            <p><span class="danger">GPS</span><i style="--w: 42%"></i><b>5</b></p>
            <p><span class="caution">시스템</span><i style="--w: 25%"></i><b>2</b></p>
          </div>

          <div class="stat-cards">
            <div><b>처리율</b><strong>68%</strong></div>
            <div><b>평균 지연</b><strong>4.8분</strong></div>
          </div>
        </article>

        <article class="panel settlement-panel">
          <div class="panel-title with-tabs">
            <div>
              <h2>요금 정산 내역</h2>
              <p>일간/주간/월간 시각화</p>
            </div>
            <div class="period-tabs">
              <button type="button" :class="{ active: selectedPeriod === 'day' }" @click="selectedPeriod = 'day'">일간</button>
              <button type="button" :class="{ active: selectedPeriod === 'week' }" @click="selectedPeriod = 'week'">주간</button>
              <button type="button" :class="{ active: selectedPeriod === 'month' }" @click="selectedPeriod = 'month'">월간</button>
            </div>
          </div>

          <div class="settlement-visual">
            <section class="settlement-summary">
              <span>{{ selectedSettlement.label }} 총 요금</span>
              <strong>{{ selectedSettlement.total }}</strong>
              <em>{{ selectedSettlement.count }}건</em>
              <div class="stacked-bar">
                <i v-for="slice in settlementSlices" :key="slice.label" :class="slice.tone" :style="{ width: `${slice.width}%` }"></i>
              </div>
              <p v-for="slice in settlementSlices" :key="slice.label">
                <span :class="slice.tone">{{ slice.label }}</span>
                <b>{{ formatWon(slice.value) }}</b>
              </p>
            </section>

            <section class="bar-chart">
              <div v-for="bar in selectedSettlement.bars" :key="bar.label">
                <i
                  :style="{ height: `${bar.ratio}%` }"
                  :data-label="`${bar.label} / 결제 ${bar.paidCount}건 / ${formatWon(bar.amount)} / 미납 ${bar.unpaidCount}건 / 보류 ${bar.holdCount}건`"
                ></i>
                <span>{{ bar.label }}</span>
              </div>
            </section>
          </div>
        </article>
      </section>

      <section class="bottom-grid">
        <article class="panel lane-detection-panel">
          <div class="panel-title">
            <div>
              <h2>실시간 인식 상황</h2>
              <p>통행 이벤트에서 선택한 차량 기준 차로별 번호판 검출</p>
            </div>
          </div>
          <div class="lane-preview-grid">
            <button
              v-for="lane in displayLaneDetections"
              :key="lane.lane"
              class="lane-preview"
              :class="toneClass(lane.tone)"
              type="button"
              @click="openEventDetail(lane.event)"
            >
              <div class="lane-frame">
                <span class="scan-line"></span>
                <span class="vehicle-shape"></span>
                <span class="plate-box">{{ lane.plate }}</span>
              </div>
              <div class="lane-caption">
                <b>{{ lane.lane }}</b>
                <span :class="toneClass(lane.tone)">{{ lane.status }}</span>
                <small>{{ lane.time }} · 신뢰도 {{ lane.confidence }}% · {{ lane.note }}</small>
              </div>
            </button>
          </div>
        </article>

        <article class="panel gps-log-panel">
          <div class="panel-title">
            <div>
              <h2>GPS 로그 기록</h2>
              <p>가로/세로 스크롤로 전체 로그 확인</p>
            </div>
            <span>PICO2W-NEO7M-RC-01</span>
          </div>

          <div class="log-scroll">
            <table>
              <thead>
                <tr>
                  <th>TIME</th>
                  <th>DEVICE</th>
                  <th>LAT/LNG</th>
                  <th>SPEED</th>
                  <th>HEAD</th>
                  <th>FIX</th>
                  <th>SAT</th>
                  <th>SIGNAL</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in gpsLogs" :key="`${log.time}-${log.latlng}`">
                  <td>{{ log.time }}</td>
                  <td>{{ log.device }}</td>
                  <td>{{ log.latlng }}</td>
                  <td>{{ log.speed }}</td>
                  <td>{{ log.heading }}</td>
                  <td><span :class="toneClass(log.fix)">{{ log.fix }}</span></td>
                  <td>{{ log.sat }}</td>
                  <td><span :class="toneClass(log.signal)">{{ log.signal }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>

    <div v-if="selectedEvent" class="modal-backdrop" @click.self="closeEventDetail">
      <article class="event-modal panel">
        <div class="modal-head">
          <div>
            <p>EVENT DETAIL</p>
            <h2>{{ selectedEvent.final.plate }} · {{ selectedEvent.status }}</h2>
          </div>
          <button type="button" @click="closeEventDetail">닫기</button>
        </div>

        <div class="event-modal-grid">
          <div class="detail-card">
            <div class="detail-head"><p class="eyebrow">FRONT 앞 번호판</p><span class="badge" :class="confClass(selectedEvent.front.conf)">{{ selectedEvent.front.conf }}%</span></div>
            <div class="plate-img"><div class="plate-placeholder"><span class="placeholder-tag">FRONT CROP</span><span class="placeholder-meta mono">960x480 · top half</span></div></div>
            <div class="plate-result mono">{{ selectedEvent.front.plate }}</div>
          </div>

          <div class="detail-card">
            <div class="detail-head"><p class="eyebrow">REAR 뒷 번호판</p><span class="badge" :class="confClass(selectedEvent.rear.conf)">{{ selectedEvent.rear.conf }}%</span></div>
            <div class="plate-img"><div class="plate-placeholder"><span class="placeholder-tag">REAR CROP</span><span class="placeholder-meta mono">960x480 · bottom half</span></div></div>
            <div class="plate-result mono">{{ selectedEvent.rear.plate }}</div>
          </div>

          <div class="detail-card final">
            <div class="detail-head"><p class="eyebrow">FUSION 최종 판정</p><span class="badge" :class="confClass(selectedEvent.final.conf)">{{ selectedEvent.final.conf }}%</span></div>
            <div class="plate-final mono">{{ selectedEvent.final.plate }}</div>
            <div class="fusion-meta">
              <p><span>일치율</span><strong>{{ Math.round(selectedEvent.final.agreement * 100) }}%</strong></p>
              <p><span>판정 방식</span><strong>{{ selectedEvent.final.source }}</strong></p>
            </div>
          </div>

          <div class="detail-card gps-modal-card">
            <div class="detail-head"><p class="eyebrow">GPS 구역 통과</p><span class="badge" :class="selectedEvent.gps.inside ? 'ok' : 'danger'">{{ selectedEvent.gps.result }}</span></div>
            <div class="gps-map modal-gps-map">
              <div class="zone"></div>
              <span class="gps-dot p1"></span>
              <span class="gps-dot p2"></span>
              <span class="gps-dot p3" :class="selectedEvent.gps.inside ? 'ok' : 'danger'"></span>
            </div>
            <div class="gps-info modal-gps-info">
              <p><span>차량</span><strong class="mono">{{ selectedEvent.final.plate }}</strong></p>
              <p><span>좌표</span><strong>{{ selectedEvent.gps.latlng }}</strong></p>
              <p><span>중심 오차</span><strong :class="selectedEvent.gps.inside ? 'ok' : 'danger'">{{ selectedEvent.gps.offset }}</strong></p>
              <p><span>속도</span><strong>{{ selectedEvent.gps.speed }}km/h</strong></p>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="selectedResolution" class="modal-backdrop" @click.self="closeResolution">
      <article class="resolution-modal panel">
        <div class="modal-head">
          <div>
            <p>EXCEPTION WORKFLOW</p>
            <h2>{{ selectedResolution.final.plate }} · {{ selectedResolution.issue }}</h2>
          </div>
          <button type="button" @click="closeResolution">닫기</button>
        </div>

        <div class="resolution-grid">
          <section class="resolution-plate-review">
            <article class="plate-review-card">
              <span>앞 번호판</span>
              <strong class="mono">{{ selectedResolution.front.plate }}</strong>
              <em :class="confClass(selectedResolution.front.conf)">{{ selectedResolution.front.conf }}%</em>
              <small>FRONT OCR crop</small>
            </article>
            <article class="plate-review-card">
              <span>뒤 번호판</span>
              <strong class="mono">{{ selectedResolution.rear.plate }}</strong>
              <em :class="confClass(selectedResolution.rear.conf)">{{ selectedResolution.rear.conf }}%</em>
              <small>REAR OCR crop</small>
            </article>
            <article class="plate-review-card final">
              <span>최종 판정</span>
              <strong class="mono">{{ selectedResolution.final.plate }}</strong>
              <em :class="confClass(selectedResolution.final.conf)">{{ selectedResolution.final.conf }}%</em>
              <small>{{ selectedResolution.final.source }} · 일치 {{ Math.round(selectedResolution.final.agreement * 100) }}%</small>
            </article>
          </section>

          <section class="resolution-summary">
            <div><span>차량 번호</span><strong class="mono">{{ selectedResolution.final.plate }}</strong></div>
            <div><span>현재 상태</span><strong :class="toneClass(selectedResolution.status)">{{ selectedResolution.status }}</strong></div>
            <div><span>정산 상태</span><strong :class="toneClass(selectedResolution.settlement)">{{ selectedResolution.settlement }}</strong></div>
            <div><span>GPS 구역</span><strong :class="selectedResolution.gps.inside ? 'ok' : 'danger'">{{ selectedResolution.gps.result }}</strong></div>
          </section>

          <section class="resolution-actions">
            <button type="button" class="approve" @click="handleResolution('approve')">
              <b>승인</b>
              <span>최종 번호판과 GPS 통과 기준으로 정산 승인</span>
            </button>
            <button type="button" class="exception" @click="handleResolution('exception')">
              <b>예외 처리</b>
              <span>시연용 예외 건으로 보류 해제 또는 수동 처리</span>
            </button>
            <button type="button" class="recheck" @click="handleResolution('recheck')">
              <b>재검수</b>
              <span>OCR/GPS 재검수 큐로 되돌리기</span>
            </button>
          </section>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.compact-dashboard{height:100vh;overflow:hidden;color:#eaf6ff;background:radial-gradient(circle at 16% 0%,rgba(42,137,255,.20),transparent 34%),linear-gradient(135deg,#020814 0%,#071323 54%,#02050b 100%);font-family:Pretendard,Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.compact-header{height:68px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid rgba(62,169,255,.24);background:rgba(2,9,20,.9);backdrop-filter:blur(18px)}
.brand,.header-meta,.panel-title,.alert-card,.queue-item,.modal-head,.detail-head{display:flex;align-items:center}.brand{gap:12px}.brand-mark{width:30px;height:30px;display:grid;place-items:center;color:#eaf6ff;border:2px solid #2294ff;border-radius:7px;box-shadow:0 0 14px rgba(34,148,255,.42);font-size:13px;font-weight:900}.brand strong{display:block;font-size:22px;letter-spacing:0}.brand small,.header-meta span,.panel-title p,.panel-title span,.alert-card small,.placeholder-meta{color:#a8bed6}.header-meta{gap:12px;font-size:13px}.header-meta button,.modal-head button{height:32px;padding:0 12px;color:#f3fbff;border:1px solid rgba(74,159,255,.45);border-radius:7px;background:rgba(10,42,82,.72);cursor:pointer}.header-meta .icon-btn{width:32px;padding:0;border-radius:50%;font-weight:900}.live-dot{display:inline-block;width:9px;height:9px;margin-right:7px;border-radius:50%;background:#42e07c;box-shadow:0 0 12px #42e07c}
.compact-main{height:calc(100vh - 68px);padding:14px 20px 14px;display:grid;grid-template-rows:92px minmax(0,1fr) 292px;gap:12px}.alert-row,.control-grid,.bottom-grid,.event-modal-grid{display:grid;gap:12px}.alert-row{grid-template-columns:repeat(4,minmax(0,1fr))}.control-grid{min-height:0;grid-template-columns:1.05fr .8fr 1.35fr}.bottom-grid{min-height:0;grid-template-columns:1.05fr 2.15fr}
.alert-card,.panel,.event-modal{border:1px solid rgba(65,163,255,.24);border-radius:8px;background:linear-gradient(145deg,rgba(12,27,48,.9),rgba(4,13,25,.82));box-shadow:0 12px 34px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.04)}.panel{min-width:0;min-height:0;padding:13px;overflow:hidden}.alert-card{gap:12px;padding:12px 14px}.alert-card i,.queue-item i{display:grid;place-items:center;width:40px;height:40px;flex:none;border-radius:8px;background:rgba(40,130,255,.18);color:#9bd2ff;font-size:12px;font-style:normal;font-weight:900}.alert-card span{display:block;color:#d9ecff;font-size:13px}.alert-card strong{display:block;margin-top:4px;font-size:28px;line-height:1}.alert-card.danger{border-color:rgba(255,91,103,.52)}.alert-card.warn{border-color:rgba(255,216,77,.55)}.alert-card.orange{border-color:rgba(255,137,64,.5)}.alert-card.violet{border-color:rgba(168,119,255,.5)}
.panel-title{justify-content:space-between;gap:10px;margin-bottom:10px}.panel-title h2,.modal-head h2{margin:0;font-size:16px;letter-spacing:0}.panel-title p,.modal-head p{margin:4px 0 0;font-size:12px}.count-chip{padding:6px 10px;border-radius:999px;color:#ffd84d;background:rgba(255,216,77,.12)}
.table-scroll,.queue-scroll,.log-scroll{overflow:auto;scrollbar-color:rgba(90,170,255,.7) rgba(5,16,30,.8);scrollbar-width:thin}.table-scroll{height:calc(100% - 50px)}.queue-scroll{height:calc(100% - 50px);display:grid;align-content:start;gap:8px;padding-right:4px}.log-scroll{height:calc(100% - 50px)}
table{width:100%;min-width:760px;border-collapse:collapse;table-layout:fixed;font-size:13px}th{position:sticky;top:0;z-index:1;height:33px;color:#9eb9d6;font-weight:800;background:rgba(30,67,106,.96)}td{height:39px;color:#d8e6f5;border-bottom:1px solid rgba(114,165,221,.12);text-align:center;white-space:nowrap}tbody tr{cursor:pointer}tbody tr:hover{background:rgba(30,129,255,.16)}tbody tr.warning,tbody tr.caution{background:rgba(255,216,77,.06)}tbody tr.danger{background:rgba(255,91,103,.08)}
.ok{color:#55e58c}.warn{color:#ffd84d}.caution{color:#5ca8ff}.info{color:#9bd2ff}.danger{color:#ff6f7d}.mono{font-family:'Roboto Mono','Consolas',monospace}.strong{font-weight:800}
.priority-meter{position:relative;display:grid;place-items:center;height:116px}.meter-ring{position:absolute;width:112px;height:112px;border-radius:50%;background:conic-gradient(#ff6f7d 0 58%,#ffd84d 58% 80%,#5ca8ff 80% 91%,rgba(80,140,210,.22) 91% 100%);filter:drop-shadow(0 0 18px rgba(255,111,125,.16))}.meter-core{position:relative;z-index:1;display:grid;place-items:center;width:78px;height:78px;border-radius:50%;background:rgba(5,18,34,.92);border:1px solid rgba(255,255,255,.08)}.meter-core strong{font-size:26px}.meter-core span{font-size:11px;color:#a8bed6}.issue-visual-list{display:grid;gap:8px}.issue-visual-list p{display:grid;grid-template-columns:58px 1fr 28px;align-items:center;gap:8px;margin:0;color:#bcd2e9}.issue-visual-list i{height:8px;border-radius:99px;background:rgba(76,136,200,.2);overflow:hidden}.issue-visual-list i::after{content:'';display:block;width:var(--w);height:100%;border-radius:inherit;background:linear-gradient(90deg,#ff6f7d,#ffd84d)}.focus-card{margin-top:10px;padding:10px;border:1px solid rgba(255,111,125,.28);border-radius:8px;background:rgba(255,111,125,.08)}.focus-card b,.focus-card strong,.focus-card span{display:block}.focus-card b{color:#ffb1b8;font-size:12px}.focus-card strong{margin:4px 0;font-size:20px}.focus-card span{color:#c6d8eb;font-size:12px}
.issue-action-list{height:calc(100% - 92px);min-height:126px;display:grid;gap:8px;overflow:auto;padding-right:3px}.issue-action{display:grid;grid-template-columns:40px minmax(0,1fr) 52px;align-items:center;gap:9px;width:100%;min-height:44px;padding:8px;color:#eaf6ff;border:1px solid rgba(82,159,239,.20);border-radius:8px;background:rgba(28,58,95,.34);cursor:pointer;text-align:left}.issue-action i{display:grid;place-items:center;width:34px;height:34px;border-radius:8px;background:rgba(40,130,255,.18);color:#9bd2ff;font-style:normal;font-size:11px;font-weight:900}.issue-action b,.issue-action small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.issue-action small{margin-top:2px;color:#bdd0e5}.issue-action em{color:#9eb9d6;font-style:normal;font-size:11px;text-align:right}.issue-action.danger{border-color:rgba(255,111,125,.42);background:rgba(255,111,125,.10)}.issue-action.warn{border-color:rgba(255,216,77,.38);background:rgba(255,216,77,.08)}.issue-visual-list.compact{margin-top:10px}
.stat-cards{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}.stat-cards div{padding:10px;border:1px solid rgba(74,159,255,.18);border-radius:8px;background:rgba(30,68,110,.18)}.stat-cards b{display:block;color:#9fb8d4;font-size:12px}.stat-cards strong{display:block;margin-top:4px;font-size:20px;color:#fff}
.with-tabs{align-items:flex-start}.period-tabs{display:flex;border:1px solid rgba(56,120,245,.22);border-radius:8px;overflow:hidden;background:rgba(8,14,32,.5)}.period-tabs button{height:30px;padding:0 12px;border:0;border-right:1px solid rgba(56,120,245,.16);background:transparent;color:#a8c4e8;cursor:pointer}.period-tabs button:last-child{border-right:0}.period-tabs button.active{background:rgba(56,190,245,.22);color:#fff;font-weight:800}.settlement-visual{display:grid;grid-template-columns:.9fr 1.1fr;gap:12px;height:calc(100% - 54px)}.settlement-summary{min-width:0;padding:12px;border:1px solid rgba(74,159,255,.2);border-radius:8px;background:rgba(30,68,110,.24)}.settlement-summary>span{color:#9fb8d4}.settlement-summary>strong{display:block;margin:5px 0;font-size:26px}.settlement-summary>em{color:#9fb8d4;font-style:normal}.stacked-bar{display:flex;height:16px;margin:12px 0;border-radius:999px;overflow:hidden;background:rgba(76,136,200,.18)}.stacked-bar i.ok{background:#55e58c}.stacked-bar i.danger{background:#ff6f7d}.stacked-bar i.caution{background:#5ca8ff}.settlement-summary p{display:flex;justify-content:space-between;margin:8px 0;color:#bcd2e9}.bar-chart{display:grid;grid-auto-flow:column;align-items:end;gap:10px;padding:12px;border:1px solid rgba(74,159,255,.2);border-radius:8px;background:rgba(30,68,110,.14)}.bar-chart div{height:100%;display:grid;grid-template-rows:1fr 18px;align-items:end;gap:6px}.bar-chart i{width:100%;min-height:12px;border-radius:7px 7px 3px 3px;background:linear-gradient(180deg,#38bef5,#1769d8);box-shadow:0 0 14px rgba(56,190,245,.2)}.bar-chart span{text-align:center;color:#a8c4e8;font-size:12px}
.queue-item{width:100%;justify-content:space-between;gap:10px;min-height:42px;padding:8px;color:#eaf6ff;border:1px solid rgba(82,159,239,.2);border-radius:7px;background:rgba(28,58,95,.34);cursor:pointer}.queue-item b{min-width:78px;text-align:left}.queue-item span{flex:1;color:#bdd0e5;text-align:left}.queue-item em{color:#9eb9d6;font-style:normal}.queue-item.danger{border-color:rgba(255,111,125,.42);background:rgba(255,111,125,.1)}.queue-item.warn{border-color:rgba(255,216,77,.38);background:rgba(255,216,77,.08)}
.gps-log-panel table{min-width:1040px}.gps-log-panel th:nth-child(1),.gps-log-panel td:nth-child(1){width:136px}.gps-log-panel th:nth-child(2),.gps-log-panel td:nth-child(2){width:190px;text-align:left}.gps-log-panel th:nth-child(3),.gps-log-panel td:nth-child(3){width:210px;text-align:left}
.bar-chart i{position:relative;cursor:pointer}.bar-chart i::after{content:attr(data-label);position:absolute;left:50%;bottom:calc(100% + 8px);transform:translateX(-50%) translateY(4px);z-index:5;min-width:max-content;padding:5px 8px;border:1px solid rgba(56,190,245,.42);border-radius:7px;background:rgba(3,11,24,.94);color:#eaf6ff;font-size:11px;font-style:normal;font-weight:800;opacity:0;pointer-events:none;transition:opacity .14s ease,transform .14s ease;box-shadow:0 10px 22px rgba(0,0,0,.24)}.bar-chart i:hover::after{opacity:1;transform:translateX(-50%) translateY(0)}
.modal-backdrop{position:fixed;inset:0;z-index:50;display:grid;place-items:center;padding:26px;background:rgba(2,8,20,.72);backdrop-filter:blur(6px)}.event-modal{width:min(1220px,96vw);max-height:90vh;overflow:auto}.modal-head{justify-content:space-between;margin-bottom:16px}.event-modal-grid{grid-template-columns:repeat(2,minmax(520px,1fr))}.detail-card{display:flex;flex-direction:column;gap:8px;padding:12px;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:rgba(2,9,22,.5)}.detail-card.final{background:linear-gradient(145deg,rgba(56,190,245,.12),rgba(27,59,232,.08));border-color:rgba(56,190,245,.4)}.detail-head{justify-content:space-between;gap:8px}.eyebrow{margin:0;color:#8eb1da;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.badge{padding:4px 8px;border-radius:999px;background:rgba(255,255,255,.08);font-size:12px;font-weight:800}.plate-img{position:relative;width:100%;aspect-ratio:5/2;border-radius:6px;overflow:hidden;background:#040820;border:1px dashed rgba(56,120,245,.28)}.plate-placeholder{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:repeating-linear-gradient(45deg,rgba(56,120,245,.05) 0 6px,transparent 6px 12px),#04081a}.plate-result{font-size:18px;font-weight:800;color:#fff;text-align:center;padding:8px;border-radius:6px;background:rgba(2,9,22,.65);letter-spacing:.04em}.plate-final{font-size:24px;font-weight:800;color:#fff;text-align:center;padding:12px;border-radius:8px;background:rgba(2,9,22,.7);letter-spacing:.06em;border:1px solid rgba(56,190,245,.3);text-shadow:0 0 12px rgba(56,190,245,.35)}.fusion-meta,.modal-gps-info{display:grid;grid-template-columns:1fr 1fr;gap:6px}.fusion-meta p,.gps-info p{margin:0;display:flex;flex-direction:column;gap:1px;padding:6px 10px;border-radius:6px;background:rgba(2,9,22,.5)}.fusion-meta span,.gps-info span{color:#7290b8;font-size:10px}.fusion-meta strong,.gps-info strong{color:#fff;font-size:12px;font-weight:700}
.gps-map{position:relative;height:230px;overflow:hidden;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:linear-gradient(rgba(56,120,245,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(56,120,245,.08) 1px,transparent 1px),#071322;background-size:26px 26px}.zone{position:absolute;left:18%;top:18%;width:64%;height:58%;border:1.5px dashed rgba(51,230,161,.65);border-radius:10px;background:rgba(51,230,161,.06)}.gps-dot{position:absolute;width:10px;height:10px;border-radius:50%;background:#38bef5;box-shadow:0 0 14px #38bef5}.gps-dot.p1{left:32%;top:68%}.gps-dot.p2{left:48%;top:54%}.gps-dot.p3{left:58%;top:45%}.gps-dot.p3.danger{left:82%;top:28%;background:#ff6f7d;box-shadow:0 0 16px #ff6f7d}.gps-dot.p3.ok{background:#55e58c;box-shadow:0 0 16px #55e58c}
.resolution-modal{width:min(1060px,96vw);max-height:88vh;overflow:auto}.resolution-grid{display:grid;grid-template-columns:1.2fr .95fr 1fr;gap:14px}.resolution-summary{display:grid;grid-template-columns:1fr 1fr;gap:10px}.resolution-summary div{padding:12px;border:1px solid rgba(56,120,245,.18);border-radius:8px;background:rgba(2,9,22,.5)}.resolution-summary span{display:block;color:#7290b8;font-size:11px;font-weight:800}.resolution-summary strong{display:block;margin-top:6px;font-size:18px}.resolution-actions{display:grid;gap:10px}.resolution-actions button{padding:14px;border:1px solid rgba(56,120,245,.22);border-radius:9px;color:#eaf6ff;background:rgba(28,58,95,.34);text-align:left;cursor:pointer}.resolution-actions b,.resolution-actions span{display:block}.resolution-actions b{font-size:17px}.resolution-actions span{margin-top:4px;color:#a8c4e8}.resolution-actions .approve{border-color:rgba(85,229,140,.38);background:rgba(85,229,140,.10)}.resolution-actions .exception{border-color:rgba(255,111,125,.38);background:rgba(255,111,125,.10)}.resolution-actions .recheck{border-color:rgba(255,216,77,.38);background:rgba(255,216,77,.08)}
.instant-scroll{height:calc(100% - 50px);display:grid;align-content:start;gap:9px;overflow:auto;padding-right:4px}.instant-card{display:grid;grid-template-columns:72px minmax(0,1fr) 76px;align-items:center;gap:10px;width:100%;min-height:76px;padding:10px;border:1px solid rgba(82,159,239,.22);border-radius:9px;color:#eaf6ff;background:rgba(28,58,95,.34);cursor:pointer;text-align:left}.instant-card:hover{background:rgba(42,112,190,.25)}.instant-card i{display:grid;place-items:center;min-height:44px;padding:0 7px;border-radius:8px;background:rgba(40,130,255,.18);font-style:normal;font-size:11px;font-weight:900;text-align:center}.instant-card.danger{border-color:rgba(255,111,125,.48);background:rgba(255,111,125,.10)}.instant-card.warn{border-color:rgba(255,216,77,.42);background:rgba(255,216,77,.08)}.instant-card.caution{border-color:rgba(92,168,255,.4);background:rgba(92,168,255,.08)}.instant-main{min-width:0}.instant-main>div{display:flex;align-items:center;justify-content:space-between;gap:8px}.instant-main strong{font-size:17px}.instant-main span,.instant-main small{color:#a8bed6}.instant-main p{margin:4px 0;color:#f3fbff;font-weight:800}.instant-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.instant-card em{justify-self:end;font-style:normal;font-size:12px;font-weight:900}
.lane-preview-grid{height:calc(100% - 50px);display:grid;grid-template-columns:1fr 1fr;gap:10px}.lane-preview{min-width:0;display:grid;grid-template-rows:minmax(0,1fr) auto;gap:8px;padding:10px;border:1px solid rgba(82,159,239,.24);border-radius:9px;color:#eaf6ff;background:rgba(28,58,95,.28);cursor:pointer;text-align:left}.lane-preview:hover{background:rgba(42,112,190,.24)}.lane-frame{position:relative;min-height:124px;overflow:hidden;border:1px solid rgba(56,120,245,.26);border-radius:8px;background:linear-gradient(160deg,rgba(8,22,42,.95),rgba(4,11,22,.92)),repeating-linear-gradient(90deg,rgba(255,255,255,.05) 0 1px,transparent 1px 18px)}.lane-frame::before{content:'';position:absolute;inset:18% 8%;border:1px dashed rgba(91,169,245,.34);border-radius:10px}.scan-line{position:absolute;left:0;right:0;top:42%;height:2px;background:linear-gradient(90deg,transparent,#38bef5,transparent);box-shadow:0 0 14px rgba(56,190,245,.7)}.vehicle-shape{position:absolute;left:50%;top:48%;width:54%;height:42%;transform:translate(-50%,-50%);border-radius:44% 44% 18% 18%;background:linear-gradient(180deg,#34495e,#101a28);border:1px solid rgba(170,220,255,.24)}.plate-box{position:absolute;left:50%;bottom:22%;transform:translateX(-50%);padding:4px 10px;border:2px solid #55e58c;border-radius:4px;background:rgba(1,8,16,.82);color:#fff;font-size:13px;font-weight:900;letter-spacing:.04em}.lane-caption{display:grid;gap:3px}.lane-caption b{font-size:14px}.lane-caption span{font-size:12px;font-weight:900}.lane-caption small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#a8bed6}
.resolution-plate-review{display:grid;gap:10px}.plate-review-card{position:relative;display:grid;grid-template-columns:1fr auto;gap:5px;padding:12px;border:1px solid rgba(56,120,245,.22);border-radius:9px;background:rgba(2,9,22,.5)}.plate-review-card::before{content:'';grid-column:1/-1;height:58px;border:1px dashed rgba(91,169,245,.26);border-radius:7px;background:repeating-linear-gradient(45deg,rgba(56,120,245,.05) 0 6px,transparent 6px 12px),rgba(4,10,22,.78)}.plate-review-card span,.plate-review-card small{color:#8eb1da}.plate-review-card strong{font-size:22px}.plate-review-card em{font-style:normal;font-size:13px;font-weight:900}.plate-review-card small{grid-column:1/-1}.plate-review-card.final{border-color:rgba(85,229,140,.42);background:linear-gradient(145deg,rgba(85,229,140,.10),rgba(56,190,245,.08))}
.compact-dashboard.light{color:#203348;background:#eef5ff}.compact-dashboard.light .compact-header{background:rgba(248,251,255,.94);border-color:rgba(42,113,190,.20)}.compact-dashboard.light .alert-card,.compact-dashboard.light .panel,.compact-dashboard.light .event-modal,.compact-dashboard.light .detail-card,.compact-dashboard.light .settlement-summary,.compact-dashboard.light .bar-chart{background:rgba(255,255,255,.88);border-color:rgba(42,113,190,.18);box-shadow:0 12px 34px rgba(24,57,100,.08)}.compact-dashboard.light .brand strong,.compact-dashboard.light .panel-title h2,.compact-dashboard.light .alert-card strong,.compact-dashboard.light td,.compact-dashboard.light .settlement-summary>strong,.compact-dashboard.light .plate-result,.compact-dashboard.light .plate-final,.compact-dashboard.light .fusion-meta strong,.compact-dashboard.light .gps-info strong,.compact-dashboard.light .modal-head h2{color:#102033;text-shadow:none}.compact-dashboard.light .brand small,.compact-dashboard.light .header-meta span,.compact-dashboard.light .panel-title p,.compact-dashboard.light .panel-title span,.compact-dashboard.light .alert-card small,.compact-dashboard.light .alert-card span,.compact-dashboard.light .queue-item span,.compact-dashboard.light .queue-item em,.compact-dashboard.light .placeholder-meta,.compact-dashboard.light .eyebrow,.compact-dashboard.light .fusion-meta span,.compact-dashboard.light .gps-info span{color:#49637f}.compact-dashboard.light .header-meta button,.compact-dashboard.light .modal-head button,.compact-dashboard.light .period-tabs{color:#143653;background:rgba(235,243,255,.92);border-color:rgba(42,113,190,.24)}.compact-dashboard.light .period-tabs button{color:#24425f}.compact-dashboard.light .period-tabs button.active{color:#fff;background:#1769d8}.compact-dashboard.light th{background:rgba(229,240,255,.96);color:#4d6887}.compact-dashboard.light td{border-color:rgba(42,113,190,.10)}.compact-dashboard.light .queue-item{color:#102033;background:rgba(248,251,255,.78);border-color:rgba(42,113,190,.16)}.compact-dashboard.light .plate-placeholder,.compact-dashboard.light .gps-map{background-color:#dfeeff}.compact-dashboard.light .meter-core{background:#fff}.compact-dashboard.light .plate-result,.compact-dashboard.light .plate-final,.compact-dashboard.light .fusion-meta p,.compact-dashboard.light .gps-info p{background:rgba(248,251,255,.82);border-color:rgba(42,113,190,.16)}
.compact-dashboard.light .issue-action{color:#102033;background:rgba(248,251,255,.78);border-color:rgba(42,113,190,.16)}.compact-dashboard.light .issue-action small,.compact-dashboard.light .issue-action em{color:#49637f}
.compact-dashboard.light .stat-cards div,.compact-dashboard.light .resolution-summary div{background:rgba(239,247,255,.86);border-color:rgba(42,113,190,.18)}.compact-dashboard.light .stat-cards strong,.compact-dashboard.light .resolution-summary strong{color:#102033}.compact-dashboard.light .stat-cards b,.compact-dashboard.light .resolution-summary span{color:#49637f}.compact-dashboard.light .resolution-actions button{color:#102033;background:rgba(248,251,255,.86);border-color:rgba(42,113,190,.18)}.compact-dashboard.light .resolution-actions span{color:#49637f}.compact-dashboard.light .resolution-actions .approve{background:rgba(19,150,93,.10);border-color:rgba(19,150,93,.28)}.compact-dashboard.light .resolution-actions .exception{background:rgba(179,32,58,.10);border-color:rgba(179,32,58,.28)}.compact-dashboard.light .resolution-actions .recheck{background:rgba(154,103,0,.10);border-color:rgba(154,103,0,.28)}
.compact-dashboard.light{color:#26384b;background:linear-gradient(135deg,#e6edf5 0%,#dfe8f2 52%,#e9eef5 100%)}.compact-dashboard.light .compact-header{background:rgba(232,240,249,.92);border-color:rgba(91,124,158,.18);box-shadow:0 10px 24px rgba(68,91,120,.08)}.compact-dashboard.light .alert-card,.compact-dashboard.light .panel,.compact-dashboard.light .event-modal,.compact-dashboard.light .resolution-modal,.compact-dashboard.light .detail-card,.compact-dashboard.light .settlement-summary,.compact-dashboard.light .bar-chart{background:rgba(244,248,252,.86);border-color:rgba(91,124,158,.18);box-shadow:0 10px 26px rgba(68,91,120,.09),inset 0 1px 0 rgba(255,255,255,.72)}.compact-dashboard.light .alert-card i,.compact-dashboard.light .queue-item i,.compact-dashboard.light .issue-action i,.compact-dashboard.light .brand-mark{background:rgba(210,223,237,.82);border-color:rgba(91,124,158,.22);color:#31577a;box-shadow:none}.compact-dashboard.light .header-meta .icon-btn{background:#d7e2ee;color:#24415e;border-color:rgba(91,124,158,.28);box-shadow:none}.compact-dashboard.light .header-meta button,.compact-dashboard.light .modal-head button{background:#dce7f1;color:#24415e;border-color:rgba(91,124,158,.28);box-shadow:none}.compact-dashboard.light .period-tabs{background:#dce7f1;border-color:rgba(91,124,158,.24)}.compact-dashboard.light .period-tabs button{color:#486783}.compact-dashboard.light .period-tabs button.active{background:#6f8faf;color:#fff;box-shadow:none}.compact-dashboard.light th{background:#d6e2ee;color:#445f7a}.compact-dashboard.light tbody tr:hover{background:rgba(111,143,175,.12)}.compact-dashboard.light tbody tr.warning,.compact-dashboard.light tbody tr.caution{background:rgba(181,142,56,.08)}.compact-dashboard.light tbody tr.danger{background:rgba(172,78,86,.08)}.compact-dashboard.light .table-scroll,.compact-dashboard.light .queue-scroll,.compact-dashboard.light .log-scroll{scrollbar-color:#9db2c8 #d8e2ec}.compact-dashboard.light .queue-item,.compact-dashboard.light .issue-action{background:rgba(237,243,249,.88);border-color:rgba(91,124,158,.18);color:#26384b}.compact-dashboard.light .meter-core{background:#edf3f8;border-color:rgba(91,124,158,.18)}.compact-dashboard.light .meter-ring{filter:none;opacity:.9}.compact-dashboard.light .issue-visual-list i,.compact-dashboard.light .stacked-bar{background:#d7e2ec}.compact-dashboard.light .bar-chart i{background:linear-gradient(180deg,#6f9fc8,#5d7f9f);box-shadow:none}.compact-dashboard.light .bar-chart i::after{background:#f4f8fc;color:#26384b;border-color:rgba(91,124,158,.28);box-shadow:0 8px 18px rgba(68,91,120,.14)}.compact-dashboard.light .gps-map,.compact-dashboard.light .plate-placeholder{background-color:#d9e4ee;border-color:rgba(91,124,158,.2)}.compact-dashboard.light .plate-result,.compact-dashboard.light .plate-final,.compact-dashboard.light .fusion-meta p,.compact-dashboard.light .gps-info p{background:#e7eef6;border-color:rgba(91,124,158,.16)}
.compact-dashboard .alert-card,.compact-dashboard .panel,.compact-dashboard .event-modal,.compact-dashboard .resolution-modal{border-width:1.5px;box-shadow:0 14px 34px rgba(0,0,0,.32),0 0 0 1px rgba(95,170,255,.08),inset 0 1px 0 rgba(255,255,255,.06)}.compact-dashboard .panel{outline:1px solid rgba(95,170,255,.08)}.compact-dashboard .control-grid>.panel,.compact-dashboard .bottom-grid>.panel{border-color:rgba(91,169,245,.34)}.event-panel td span,.gps-log-panel td span{display:inline-flex;align-items:center;justify-content:center;min-width:68px;height:24px;padding:0 10px;border-radius:999px;border:1px solid currentColor;background:rgba(255,255,255,.06);font-size:11.5px;font-weight:900;line-height:1;box-shadow:inset 0 0 0 1px rgba(255,255,255,.04)}.event-panel td span.ok,.gps-log-panel td span.ok{color:#55e58c;background:rgba(85,229,140,.12);border-color:rgba(85,229,140,.42)}.event-panel td span.warn,.gps-log-panel td span.warn{color:#e8c75b;background:rgba(232,199,91,.13);border-color:rgba(232,199,91,.45)}.event-panel td span.caution,.gps-log-panel td span.caution{color:#75b7ff;background:rgba(117,183,255,.12);border-color:rgba(117,183,255,.42)}.event-panel td span.danger,.gps-log-panel td span.danger{color:#ff8792;background:rgba(255,135,146,.13);border-color:rgba(255,135,146,.45)}.issue-panel .danger{color:#ff9aa3}.issue-panel .warn{color:#e2c15a}.issue-panel .caution{color:#84baff}.meter-ring{background:conic-gradient(#d96672 0 58%,#caa442 58% 80%,#5f91bd 80% 91%,rgba(80,140,210,.22) 91% 100%)}.issue-visual-list i::after{background:linear-gradient(90deg,#c9636d,#d1aa4a)}.compact-dashboard.light .alert-card,.compact-dashboard.light .panel,.compact-dashboard.light .event-modal,.compact-dashboard.light .resolution-modal{border-width:1.5px;border-color:rgba(84,116,148,.34);box-shadow:0 12px 28px rgba(76,99,126,.12),0 0 0 1px rgba(84,116,148,.10),inset 0 1px 0 rgba(255,255,255,.72)}.compact-dashboard.light .control-grid>.panel,.compact-dashboard.light .bottom-grid>.panel{border-color:rgba(72,105,139,.42)}.compact-dashboard.light .event-panel td span,.compact-dashboard.light .gps-log-panel td span{background:#e1eaf3;box-shadow:none}.compact-dashboard.light .event-panel td span.ok,.compact-dashboard.light .gps-log-panel td span.ok{color:#166f50;background:#dceee7;border-color:#7eb49d}.compact-dashboard.light .event-panel td span.warn,.compact-dashboard.light .gps-log-panel td span.warn{color:#7b620e;background:#f0e6c9;border-color:#bba66b}.compact-dashboard.light .event-panel td span.caution,.compact-dashboard.light .gps-log-panel td span.caution{color:#315f91;background:#dce8f5;border-color:#8ca9c8}.compact-dashboard.light .event-panel td span.danger,.compact-dashboard.light .gps-log-panel td span.danger{color:#93333e;background:#ecdde0;border-color:#bc858c}.compact-dashboard.light .issue-panel .danger{color:#93333e}.compact-dashboard.light .issue-panel .warn{color:#7b620e}.compact-dashboard.light .issue-panel .caution{color:#315f91}.compact-dashboard.light .meter-ring{background:conic-gradient(#a75861 0 58%,#a98a3f 58% 80%,#6386aa 80% 91%,#c6d3df 91% 100%)}.compact-dashboard.light .issue-visual-list i::after{background:linear-gradient(90deg,#a75861,#a98a3f)}
.compact-dashboard.light .brand small,.compact-dashboard.light .header-meta span,.compact-dashboard.light .panel-title p,.compact-dashboard.light .panel-title span,.compact-dashboard.light .alert-card small,.compact-dashboard.light .alert-card span,.compact-dashboard.light .meter-core span,.compact-dashboard.light .issue-visual-list p,.compact-dashboard.light .settlement-summary>span,.compact-dashboard.light .settlement-summary>em,.compact-dashboard.light .settlement-summary p,.compact-dashboard.light .bar-chart span,.compact-dashboard.light .queue-item span,.compact-dashboard.light .queue-item em,.compact-dashboard.light .placeholder-meta,.compact-dashboard.light .eyebrow,.compact-dashboard.light .fusion-meta span,.compact-dashboard.light .gps-info span,.compact-dashboard.light .resolution-actions span{color:#314961}.compact-dashboard.light .issue-visual-list b,.compact-dashboard.light .settlement-summary b,.compact-dashboard.light .queue-item b,.compact-dashboard.light .meter-core strong,.compact-dashboard.light .stat-cards strong{color:#14283a}.compact-dashboard.light .ok{color:#126246}.compact-dashboard.light .warn{color:#6f570c}.compact-dashboard.light .caution{color:#285985}.compact-dashboard.light .danger{color:#87303a}.compact-dashboard.light .settlement-summary p span.ok{color:#126246}.compact-dashboard.light .settlement-summary p span.danger{color:#87303a}.compact-dashboard.light .settlement-summary p span.caution{color:#285985}.compact-dashboard.light .bar-chart i::after{min-width:260px;white-space:normal;text-align:left;line-height:1.45;color:#14283a}
.compact-dashboard.light .instant-card,.compact-dashboard.light .lane-preview,.compact-dashboard.light .plate-review-card{background:rgba(237,243,249,.88);border-color:rgba(91,124,158,.22);color:#26384b}.compact-dashboard.light .instant-card i{background:#d7e2ee;color:#24415e}.compact-dashboard.light .instant-main p,.compact-dashboard.light .instant-main strong,.compact-dashboard.light .lane-caption b,.compact-dashboard.light .plate-review-card strong{color:#14283a}.compact-dashboard.light .instant-main span,.compact-dashboard.light .instant-main small,.compact-dashboard.light .lane-caption small,.compact-dashboard.light .plate-review-card span,.compact-dashboard.light .plate-review-card small{color:#314961}.compact-dashboard.light .lane-frame,.compact-dashboard.light .plate-review-card::before{background:#d9e4ee;border-color:rgba(91,124,158,.22)}.compact-dashboard.light .vehicle-shape{background:linear-gradient(180deg,#b8c8d8,#7890a8);border-color:rgba(50,80,115,.24)}.compact-dashboard.light .plate-box{background:#f4f8fc;color:#14283a;border-color:#16895f}
.event-panel table{min-width:830px}.open-col,.row-open-cell{width:58px}.row-open-cell button{height:25px;padding:0 10px;border:1px solid rgba(74,159,255,.42);border-radius:999px;background:rgba(56,120,245,.22);color:#eaf6ff;font-size:11px;font-weight:900;opacity:0;transform:translateX(-4px);cursor:pointer;transition:opacity .14s ease,transform .14s ease,background .14s ease}tbody tr:hover .row-open-cell button{opacity:1;transform:translateX(0)}tbody tr.selected{background:rgba(56,190,245,.16)!important}.instant-card{grid-template-columns:62px minmax(0,1fr) 68px;overflow:hidden}.instant-card i,.instant-card em{max-width:100%;overflow:hidden;text-overflow:ellipsis}.instant-main>div{min-width:0}.instant-main>div span{flex:none;font-size:11px}.instant-main p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.instant-main small{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.35}.lane-caption span{color:#ffd84d}.lane-caption .danger{color:#ff9aa3}.lane-caption .warn{color:#e2c15a}.lane-caption .caution{color:#84baff}
.compact-dashboard.light .row-open-cell button{background:#dce7f1;color:#24415e;border-color:rgba(91,124,158,.34)}.compact-dashboard.light tbody tr.selected{background:rgba(92,130,170,.18)!important}.compact-dashboard.light .lane-caption span{color:#5c4508}.compact-dashboard.light .lane-caption .danger{color:#93333e}.compact-dashboard.light .lane-caption .warn{color:#7b620e}.compact-dashboard.light .lane-caption .caution{color:#315f91}
@media (max-width:1280px){.compact-dashboard{overflow:auto}.compact-main{height:auto;grid-template-rows:auto}.alert-row,.control-grid,.bottom-grid,.event-modal-grid,.settlement-visual,.resolution-grid,.lane-preview-grid{grid-template-columns:1fr}}
</style>
