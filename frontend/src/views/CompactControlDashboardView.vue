<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const nowText = ref('')
const selectedEventId = ref(2)

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

const kpis = [
  { label: '오늘 통행', value: '1,248', note: '+12.5%', tone: 'blue' },
  { label: '검수 대기', value: '12', note: 'OCR 확인', tone: 'yellow' },
  { label: 'GPS 단말', value: '3', note: '수신 정상', tone: 'green' },
  { label: '미정산', value: '36', note: '정산 대기', tone: 'orange' },
  { label: '탄소 저감', value: '482kg', note: 'ESG 추정', tone: 'cyan' }
]

const events = [
  { id: 1, time: '10:21:03', lane: '1차로', plate: '12가3456', conf: 97, status: '저장완료', speed: 42, gps: '통과' },
  { id: 2, time: '10:22:15', lane: '2차로', plate: '33나9029', conf: 62, status: '검수필요', speed: 35, gps: '통과' },
  { id: 3, time: '10:23:07', lane: '1차로', plate: '48다7720', conf: 91, status: '정산대기', speed: 38, gps: '통과' },
  { id: 4, time: '10:24:42', lane: '2차로', plate: '71라1208', conf: 89, status: '저장완료', speed: 44, gps: '통과' }
]

const selectedEvent = computed(() => events.find((event) => event.id === selectedEventId.value) ?? events[0])

const reviewQueue = [
  { plate: '33나9029', reason: 'OCR 신뢰도 낮음', conf: '62%', eta: '2분 전' },
  { plate: '18마4512', reason: '후면 번호판 재확인', conf: '58%', eta: '4분 전' },
  { plate: '62바7781', reason: 'GPS 영역 경계 근접', conf: '74%', eta: '7분 전' }
]

const gpsLogs = [
  { time: '26-05-11 13:11:30', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401236 / 127.104540', speed: '7.5', fix: '3D', sat: 9 },
  { time: '26-05-11 13:11:27', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401228 / 127.104531', speed: '6.8', fix: '3D', sat: 9 },
  { time: '26-05-11 13:11:24', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401219 / 127.104520', speed: '6.1', fix: '3D', sat: 8 },
  { time: '26-05-11 13:11:21', device: 'PICO2W-NEO7M-RC-01', latlng: '37.401210 / 127.104512', speed: '5.4', fix: '3D', sat: 8 }
]

let timer = null

function updateTime() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function statusClass(status) {
  if (['저장완료', '정상', '통과', '3D'].includes(status)) return 'ok'
  if (['검수필요', '주의'].includes(status)) return 'warn'
  if (['정산대기'].includes(status)) return 'info'
  return 'danger'
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
  <div class="compact-dashboard">
    <header class="compact-header">
      <div class="brand">
        <span class="brand-mark"></span>
        <div>
          <strong>HI-FIVE Control Dashboard</strong>
          <small>{{ centerName }} · Compact View</small>
        </div>
      </div>

      <div class="header-meta">
        <span>{{ nowText }}</span>
        <span><i class="live-dot"></i>서버 정상</span>
        <span>관리자 admin</span>
        <button type="button" @click="router.push('/master-admin')">회원 대시보드</button>
        <button type="button" @click="logout">로그아웃</button>
      </div>
    </header>

    <main class="compact-main">
      <section class="kpi-row">
        <article v-for="kpi in kpis" :key="kpi.label" class="kpi-card" :class="kpi.tone">
          <span>{{ kpi.label }}</span>
          <strong>{{ kpi.value }}</strong>
          <small>{{ kpi.note }}</small>
        </article>
      </section>

      <section class="overview-grid">
        <article class="panel event-panel">
          <div class="panel-title">
            <h2>실시간 통행 이벤트</h2>
            <span>LANE 1 · LANE 2</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>TIME</th>
                <th>LANE</th>
                <th>PLATE</th>
                <th>CONF</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="event in events"
                :key="event.id"
                :class="{ selected: selectedEventId === event.id }"
                @click="selectedEventId = event.id"
              >
                <td>{{ event.time }}</td>
                <td>{{ event.lane }}</td>
                <td>{{ event.plate }}</td>
                <td>{{ event.conf }}%</td>
                <td><span :class="statusClass(event.status)">{{ event.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="panel ocr-panel">
          <div class="panel-title">
            <h2>OCR · GPS 상세</h2>
            <span>{{ selectedEvent.plate }}</span>
          </div>

          <div class="detail-split">
            <div class="camera-frame">
              <div class="road-line"></div>
              <div class="car-body">
                <div class="plate-box">{{ selectedEvent.plate }}</div>
              </div>
              <b>{{ selectedEvent.conf }}%</b>
            </div>

            <div class="gps-map">
              <div class="zone"></div>
              <span class="point p1"></span>
              <span class="point p2"></span>
              <span class="point p3 active"></span>
              <div class="gps-info">
                <strong>GPS 영역 통과</strong>
                <small>중심 오차 1.8m · {{ selectedEvent.speed }}km/h</small>
              </div>
            </div>
          </div>

          <dl class="detail-list">
            <div><dt>차량 번호</dt><dd>{{ selectedEvent.plate }}</dd></div>
            <div><dt>차로</dt><dd>{{ selectedEvent.lane }}</dd></div>
            <div><dt>검출 시간</dt><dd>{{ selectedEvent.time }}</dd></div>
            <div><dt>GPS</dt><dd class="ok">{{ selectedEvent.gps }}</dd></div>
          </dl>
        </article>

        <article class="panel settlement-panel">
          <div class="panel-title">
            <h2>정산 · 시스템</h2>
            <span>Live</span>
          </div>
          <div class="settlement-total">
            <span>오늘 총 요금</span>
            <strong>₩2,450,800</strong>
          </div>
          <div class="bar-list">
            <p><span>1차로</span><i style="--w: 78%"></i><b>724</b></p>
            <p><span>2차로</span><i style="--w: 56%"></i><b>524</b></p>
            <p><span>미납</span><i style="--w: 18%"></i><b>36</b></p>
          </div>
          <div class="system-grid">
            <div><span>OCR Edge</span><strong class="ok">OK</strong></div>
            <div><span>GPS API</span><strong class="ok">OK</strong></div>
            <div><span>DB</span><strong class="ok">OK</strong></div>
            <div><span>WebTransport</span><strong class="ok">READY</strong></div>
          </div>
        </article>
      </section>

      <section class="bottom-grid">
        <article class="panel">
          <div class="panel-title">
            <h2>검수 큐</h2>
            <span>{{ reviewQueue.length }}건</span>
          </div>
          <div class="review-list">
            <button v-for="item in reviewQueue" :key="item.plate" type="button">
              <b>{{ item.plate }}</b>
              <span>{{ item.reason }}</span>
              <em>{{ item.conf }} · {{ item.eta }}</em>
            </button>
          </div>
        </article>

        <article class="panel gps-log-panel">
          <div class="panel-title">
            <h2>GPS Telemetry</h2>
            <span>PICO2W-NEO7M-RC-01</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>TIME</th>
                <th>DEVICE</th>
                <th>LAT/LNG</th>
                <th>SPD</th>
                <th>FIX</th>
                <th>SAT</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in gpsLogs" :key="log.time">
                <td>{{ log.time }}</td>
                <td>{{ log.device }}</td>
                <td>{{ log.latlng }}</td>
                <td>{{ log.speed }}</td>
                <td><span :class="statusClass(log.fix)">{{ log.fix }}</span></td>
                <td>{{ log.sat }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>
    </main>
  </div>
</template>

<style scoped>
.compact-dashboard {
  min-height: 100vh;
  overflow: hidden;
  color: #eaf6ff;
  background:
    radial-gradient(circle at 18% 0%, rgba(30, 144, 255, 0.2), transparent 34%),
    linear-gradient(135deg, #020814 0%, #061221 52%, #02050b 100%);
  font-family: Pretendard, Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.compact-header {
  height: 74px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  border-bottom: 1px solid rgba(62, 169, 255, 0.24);
  background: rgba(2, 9, 20, 0.82);
  backdrop-filter: blur(18px);
}

.brand,
.header-meta,
.panel-title,
.detail-list,
.system-grid,
.review-list button {
  display: flex;
  align-items: center;
}

.brand {
  gap: 14px;
}

.brand strong {
  display: block;
  font-size: 24px;
  letter-spacing: 0;
}

.brand small,
.header-meta span,
.panel-title span,
.kpi-card small {
  color: #a8bed6;
}

.brand-mark {
  width: 26px;
  height: 26px;
  border: 3px solid #2294ff;
  transform: rotate(45deg);
  box-shadow: 0 0 16px rgba(34, 148, 255, 0.6);
}

.header-meta {
  gap: 16px;
  font-size: 14px;
}

.header-meta button {
  height: 34px;
  padding: 0 14px;
  color: #f3fbff;
  border: 1px solid rgba(74, 159, 255, 0.45);
  border-radius: 7px;
  background: rgba(10, 42, 82, 0.72);
  cursor: pointer;
}

.live-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 7px;
  border-radius: 50%;
  background: #42e07c;
  box-shadow: 0 0 12px #42e07c;
}

.compact-main {
  height: calc(100vh - 74px);
  padding: 18px 28px 22px;
  display: grid;
  grid-template-rows: 108px minmax(0, 1fr) 190px;
  gap: 14px;
}

.kpi-row,
.overview-grid,
.bottom-grid {
  display: grid;
  gap: 14px;
}

.kpi-row {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.kpi-card,
.panel {
  border: 1px solid rgba(65, 163, 255, 0.24);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(12, 27, 48, 0.86), rgba(4, 13, 25, 0.78));
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.kpi-card {
  padding: 16px 18px;
}

.kpi-card span {
  display: block;
  color: #d9ecff;
  font-size: 14px;
}

.kpi-card strong {
  display: block;
  margin-top: 8px;
  font-size: 30px;
  line-height: 1;
}

.kpi-card.blue { border-color: rgba(45, 145, 255, 0.5); }
.kpi-card.yellow { border-color: rgba(255, 210, 69, 0.48); }
.kpi-card.green { border-color: rgba(68, 224, 134, 0.42); }
.kpi-card.orange { border-color: rgba(255, 135, 65, 0.44); }
.kpi-card.cyan { border-color: rgba(42, 224, 235, 0.42); }

.overview-grid {
  min-height: 0;
  grid-template-columns: 1.12fr 1.45fr 1fr;
}

.bottom-grid {
  grid-template-columns: 0.85fr 2.15fr;
  min-height: 0;
}

.panel {
  min-width: 0;
  min-height: 0;
  padding: 14px;
  overflow: hidden;
}

.panel-title {
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title h2 {
  margin: 0;
  font-size: 17px;
  letter-spacing: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}

th {
  height: 34px;
  color: #9eb9d6;
  font-weight: 700;
  background: rgba(40, 78, 121, 0.32);
}

td {
  height: 42px;
  color: #d8e6f5;
  border-bottom: 1px solid rgba(114, 165, 221, 0.12);
  text-align: center;
  white-space: nowrap;
}

tbody tr {
  cursor: pointer;
}

tbody tr.selected,
tbody tr:hover {
  background: rgba(30, 129, 255, 0.16);
}

.ok { color: #55e58c; }
.warn { color: #ffd84d; }
.info { color: #5ca8ff; }
.danger { color: #ff6f6f; }

.detail-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  height: calc(100% - 98px);
  min-height: 180px;
}

.camera-frame,
.gps-map {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(75, 166, 255, 0.25);
  border-radius: 8px;
  background: #071322;
}

.camera-frame {
  display: grid;
  place-items: center;
  background:
    linear-gradient(90deg, transparent 49%, rgba(255,255,255,0.14) 50%, transparent 51%),
    linear-gradient(180deg, #1b2636 0%, #08121f 100%);
}

.road-line {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(0deg, transparent 0 28px, rgba(255,255,255,0.16) 28px 34px);
  opacity: 0.35;
}

.car-body {
  position: relative;
  width: 62%;
  height: 42%;
  border-radius: 18px 18px 10px 10px;
  background: linear-gradient(180deg, #dce8f7, #7f93aa);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.5);
}

.plate-box {
  position: absolute;
  left: 50%;
  bottom: 18%;
  transform: translateX(-50%);
  min-width: 98px;
  padding: 5px 10px;
  color: #04130a;
  border: 2px solid #35ff7d;
  background: rgba(220, 255, 230, 0.92);
  font-weight: 900;
  text-align: center;
}

.camera-frame b {
  position: absolute;
  right: 12px;
  top: 12px;
  color: #35ff7d;
}

.gps-map {
  background:
    linear-gradient(rgba(54, 151, 255, 0.09) 1px, transparent 1px),
    linear-gradient(90deg, rgba(54, 151, 255, 0.09) 1px, transparent 1px),
    radial-gradient(circle at 55% 50%, rgba(38, 255, 127, 0.12), transparent 38%),
    #04111d;
  background-size: 28px 28px, 28px 28px, auto, auto;
}

.zone {
  position: absolute;
  left: 30%;
  top: 22%;
  width: 42%;
  height: 48%;
  border: 2px solid rgba(62, 255, 127, 0.8);
  transform: rotate(-11deg);
  background: rgba(62, 255, 127, 0.06);
}

.point {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #5ca8ff;
  box-shadow: 0 0 14px #5ca8ff;
}

.p1 { left: 31%; top: 68%; }
.p2 { left: 43%; top: 55%; }
.p3 { left: 55%; top: 45%; }
.point.active {
  width: 14px;
  height: 14px;
  background: #42e07c;
  box-shadow: 0 0 20px #42e07c;
}

.gps-info {
  position: absolute;
  left: 12px;
  bottom: 12px;
  padding: 9px 10px;
  border-radius: 7px;
  background: rgba(2, 11, 20, 0.78);
}

.gps-info strong,
.gps-info small {
  display: block;
}

.gps-info small {
  color: #b7cbe2;
}

.detail-list {
  justify-content: space-between;
  gap: 8px;
  margin: 12px 0 0;
}

.detail-list div {
  flex: 1;
  padding: 9px 10px;
  border-radius: 7px;
  background: rgba(58, 94, 135, 0.2);
}

.detail-list dt {
  color: #94adca;
  font-size: 12px;
}

.detail-list dd {
  margin: 4px 0 0;
  font-weight: 800;
}

.settlement-total {
  padding: 14px;
  border-radius: 8px;
  background: rgba(21, 79, 128, 0.24);
}

.settlement-total span,
.bar-list span,
.system-grid span {
  color: #a8bed6;
}

.settlement-total strong {
  display: block;
  margin-top: 6px;
  font-size: 30px;
}

.bar-list {
  display: grid;
  gap: 10px;
  margin: 14px 0;
}

.bar-list p {
  display: grid;
  grid-template-columns: 56px 1fr 38px;
  align-items: center;
  gap: 10px;
  margin: 0;
}

.bar-list i {
  height: 9px;
  border-radius: 999px;
  background: linear-gradient(90deg, #287dff, #43e3ff);
}

.bar-list i::after {
  content: '';
  display: block;
  width: var(--w);
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #47e38b, #ffd84d);
}

.system-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.system-grid div {
  padding: 10px;
  border-radius: 7px;
  background: rgba(65, 163, 255, 0.11);
}

.system-grid strong {
  display: block;
  margin-top: 4px;
}

.review-list {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.review-list button {
  width: 100%;
  justify-content: space-between;
  gap: 10px;
  min-height: 38px;
  color: #eaf6ff;
  border: 1px solid rgba(82, 159, 239, 0.2);
  border-radius: 7px;
  background: rgba(28, 58, 95, 0.34);
  cursor: pointer;
}

.review-list span {
  flex: 1;
  color: #bdd0e5;
  text-align: left;
}

.review-list em {
  color: #ffd84d;
  font-style: normal;
}

.gps-log-panel {
  overflow-x: auto;
}

.gps-log-panel table {
  min-width: 820px;
}

.gps-log-panel td:nth-child(2),
.gps-log-panel td:nth-child(3) {
  text-align: left;
}

@media (max-width: 1280px) {
  .compact-dashboard {
    overflow: auto;
  }

  .compact-main {
    height: auto;
    grid-template-rows: auto;
  }

  .kpi-row,
  .overview-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
