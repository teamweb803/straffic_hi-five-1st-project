<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useBoardStore } from '@/stores/board'
import { gpsApi } from '@/api/gps'

const auth = useAuthStore()
const board = useBoardStore()

const clock = ref('')
let clockTimer = null
function tick() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  clock.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const kpi = reactive({
  total: 128430,
  accuracy: 97.3,
  speed: 42,
  uptime: 99.9
})
let kpiTimer = null
function bumpKpi() {
  kpi.total += Math.floor(Math.random() * 20)
  kpi.accuracy = Math.min(99.9, +(kpi.accuracy + (Math.random() - 0.5) * 0.05).toFixed(1))
  kpi.speed = Math.max(28, Math.min(80, kpi.speed + Math.floor((Math.random() - 0.5) * 6)))
}

const liveLogs = ref([
  mockLog('12가3456', 'A-17', 'PASSENGER', 0.94),
  mockLog('33나9029', 'A-18', 'TRUCK', 0.91),
  mockLog('48다7720', 'A-15', 'BUS', 0.88),
  mockLog('77가0033', 'A-17', 'PASSENGER', 0.62),
  mockLog('25마4499', 'A-19', 'VAN', 0.96)
])
let logTimer = null
function pushLog() {
  const types = ['PASSENGER', 'TRUCK', 'BUS', 'VAN', 'SPECIAL']
  const lanes = ['A-15', 'A-17', 'A-18', 'A-19']
  const conf = +(0.5 + Math.random() * 0.49).toFixed(2)
  liveLogs.value.unshift(mockLog(randomPlate(), lanes[Math.floor(Math.random() * lanes.length)], types[Math.floor(Math.random() * types.length)], conf))
  if (liveLogs.value.length > 20) liveLogs.value.pop()
}
function mockLog(plate, lane, vehicleType, confidence) {
  return { plate, lane, vehicleType, confidence, time: new Date().toISOString() }
}
function randomPlate() {
  const ko = ['가', '나', '다', '라', '마', '바', '사', '아', '자', '차']
  return `${Math.floor(10 + Math.random() * 90)}${ko[Math.floor(Math.random() * ko.length)]}${Math.floor(1000 + Math.random() * 9000)}`
}

const gpsTelemetry = ref([])
const gpsLoading = ref(false)
const gpsError = ref(null)
let gpsTimer = null

async function fetchGpsTelemetry() {
  gpsLoading.value = true
  gpsError.value = null
  try {
    const { data } = await gpsApi.latest()
    gpsTelemetry.value = data.map((telemetry) => ({
      ...telemetry,
      capturedAt: normalizeDate(telemetry.capturedAt),
      receivedAt: normalizeDate(telemetry.receivedAt)
    }))
  } catch (err) {
    gpsError.value = err?.response?.data?.message ?? 'GPS telemetry를 불러오지 못했습니다.'
  } finally {
    gpsLoading.value = false
  }
}

const latestGps = computed(() => gpsTelemetry.value[0] ?? null)
const activeGpsCount = computed(() => new Set(gpsTelemetry.value.map((telemetry) => telemetry.gpsDeviceId)).size)
const avgGpsSpeed = computed(() => {
  if (gpsTelemetry.value.length === 0) return 0
  const total = gpsTelemetry.value.reduce((sum, telemetry) => sum + Number(telemetry.speedKmh ?? 0), 0)
  return total / gpsTelemetry.value.length
})

const newPost = reactive({
  title: '',
  content: '',
  plateNumber: '',
  vehicleCount: 1,
  recognitionConfidence: 0.9
})
const postSubmitting = ref(false)

async function submitPost() {
  if (!newPost.title || !newPost.content) return
  postSubmitting.value = true
  await board.create({ ...newPost })
  postSubmitting.value = false
  newPost.title = ''
  newPost.content = ''
  newPost.plateNumber = ''
  newPost.vehicleCount = 1
  newPost.recognitionConfidence = 0.9
}

onMounted(() => {
  tick()
  clockTimer = setInterval(tick, 1000)
  kpiTimer = setInterval(bumpKpi, 2200)
  logTimer = setInterval(pushLog, 4000)
  gpsTimer = setInterval(fetchGpsTelemetry, 5000)
  board.fetchAll().catch(() => {})
  fetchGpsTelemetry()
})

onBeforeUnmount(() => {
  clearInterval(clockTimer)
  clearInterval(kpiTimer)
  clearInterval(logTimer)
  clearInterval(gpsTimer)
})

const lowConfCount = computed(() => liveLogs.value.filter((log) => log.confidence < 0.7).length)
const reviewQueueCount = computed(() => board.lowConfidencePosts.length + lowConfCount.value)

function fmtPct(value) {
  return `${(Number(value ?? 0) * 100).toFixed(0)}%`
}

function fmtTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleTimeString('ko-KR', { hour12: false })
}

function fmtCoord(value) {
  return Number(value ?? 0).toFixed(6)
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
</script>

<template>
  <div class="bg-cloud min-h-screen">
    <header class="bg-white border-b border-line">
      <div class="max-w-7xl mx-auto px-6 py-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="font-mono text-xs tracking-[0.3em] text-brand">REALTIME OPS</p>
          <h1 class="font-headline text-3xl md:text-4xl text-deep mt-1">실시간 운영 관제</h1>
          <p class="text-sm text-navy/60 mt-1">
            <strong class="text-navy">{{ auth.member?.memberName ?? '관리자' }}</strong>님이 운영 중입니다.
          </p>
        </div>
        <div class="flex items-center gap-3 text-sm">
          <span class="font-mono text-navy/60">{{ clock }}</span>
          <span class="inline-flex items-center gap-2 px-3 py-1 bg-sky/10 rounded-full text-brand font-semibold">
            <span class="live-dot" />LIVE
          </span>
        </div>
      </div>
    </header>

    <div class="max-w-7xl mx-auto px-6 py-10 space-y-10">
      <section class="grid grid-cols-2 md:grid-cols-5 gap-4">
        <article class="kpi-card">
          <p class="font-mono text-[11px] text-brand">TOTAL</p>
          <p class="font-headline text-3xl text-deep mt-2">{{ kpi.total.toLocaleString() }}</p>
          <p class="text-xs text-navy/60 mt-1">총 처리 이벤트</p>
        </article>
        <article class="kpi-card">
          <p class="font-mono text-[11px] text-brand">ACCURACY</p>
          <p class="font-headline text-3xl text-deep mt-2">{{ kpi.accuracy }}%</p>
          <p class="text-xs text-navy/60 mt-1">번호판 인식 신뢰도</p>
        </article>
        <article class="kpi-card">
          <p class="font-mono text-[11px] text-brand">P95 LATENCY</p>
          <p class="font-headline text-3xl text-deep mt-2">{{ kpi.speed }}ms</p>
          <p class="text-xs text-navy/60 mt-1">엣지 처리 지연</p>
        </article>
        <article class="kpi-card">
          <p class="font-mono text-[11px] text-brand">REVIEW</p>
          <p class="font-headline text-3xl text-deep mt-2">{{ reviewQueueCount }}</p>
          <p class="text-xs text-navy/60 mt-1">검수 대기 차량</p>
        </article>
        <article class="kpi-card">
          <p class="font-mono text-[11px] text-brand">GPS</p>
          <p class="font-headline text-3xl text-deep mt-2">{{ activeGpsCount }}</p>
          <p class="text-xs text-navy/60 mt-1">연동 단말</p>
        </article>
      </section>

      <section class="grid lg:grid-cols-3 gap-5">
        <article class="card lg:col-span-2">
          <header class="flex items-center justify-between mb-4">
            <h2 class="font-bold text-navy">실시간 통과 로그</h2>
            <span class="font-mono text-xs text-navy/50">최근 {{ liveLogs.length }}</span>
          </header>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-navy/50 font-mono text-[11px] border-b border-line">
                  <th class="py-2">TIME</th>
                  <th>LANE</th>
                  <th>PLATE</th>
                  <th>VEHICLE</th>
                  <th>CONF</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in liveLogs" :key="log.time + log.plate" class="border-b border-line/60" :class="log.confidence < 0.7 ? 'bg-amber-50/60' : ''">
                  <td class="py-2 font-mono text-xs text-navy/70">{{ fmtTime(log.time) }}</td>
                  <td class="font-mono text-xs">{{ log.lane }}</td>
                  <td class="font-bold text-deep">{{ log.plate }}</td>
                  <td class="text-xs">{{ log.vehicleType }}</td>
                  <td>
                    <span class="px-2 py-0.5 rounded-full text-xs font-bold" :class="log.confidence < 0.7 ? 'bg-amber-200 text-amber-900' : 'bg-emerald-100 text-emerald-700'">
                      {{ fmtPct(log.confidence) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="card">
          <header class="flex items-center justify-between mb-4">
            <h2 class="font-bold text-navy">GPS/LTE 단말 현황</h2>
            <button class="btn-ghost text-xs py-1 px-3" @click="fetchGpsTelemetry">새로고침</button>
          </header>
          <div class="relative h-56 rounded-xl bg-gradient-to-br from-deep to-navy overflow-hidden">
            <svg viewBox="0 0 420 270" preserveAspectRatio="none" class="absolute inset-0 w-full h-full">
              <path d="M20,210 C100,180 160,140 220,120 S360,80 400,40" stroke="#38BEF5" stroke-width="3" fill="none" stroke-linecap="round" />
            </svg>
            <span class="live-dot absolute" style="left: 18%; top: 66%" />
            <span class="live-dot absolute" style="left: 50%; top: 44%; animation-delay: .35s" />
            <span class="live-dot absolute" style="left: 78%; top: 27%; animation-delay: .7s; background:#facc15" />
            <div class="absolute left-4 right-4 bottom-4 rounded-lg bg-white/90 p-3 text-xs text-navy">
              <p class="font-bold text-deep">{{ latestGps?.gpsDeviceId ?? 'PHONE-DEMO-01' }}</p>
              <p v-if="latestGps" class="mt-1 font-mono">{{ fmtCoord(latestGps.latitude) }}, {{ fmtCoord(latestGps.longitude) }}</p>
              <p v-else class="mt-1">아직 수신된 GPS telemetry가 없습니다.</p>
            </div>
          </div>
          <ul class="mt-4 space-y-2 text-xs text-navy/70">
            <li class="flex justify-between"><span>활성 단말</span><strong class="text-deep">{{ activeGpsCount }}</strong></li>
            <li class="flex justify-between"><span>평균 속도</span><strong class="text-deep">{{ avgGpsSpeed.toFixed(1) }} km/h</strong></li>
            <li class="flex justify-between"><span>최근 수신</span><strong class="text-deep">{{ fmtTime(latestGps?.capturedAt) }}</strong></li>
          </ul>
          <p v-if="gpsLoading" class="mt-3 text-xs text-navy/50">GPS telemetry를 불러오는 중...</p>
          <p v-else-if="gpsError" class="mt-3 text-xs text-red-500">{{ gpsError }}</p>
        </article>
      </section>

      <section class="grid lg:grid-cols-3 gap-5">
        <article class="card lg:col-span-2">
          <header class="flex items-center justify-between mb-4">
            <h2 class="font-bold text-navy">GPS telemetry 로그</h2>
            <span class="font-mono text-xs text-navy/50">PostgreSQL 저장 기준</span>
          </header>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-navy/50 font-mono text-[11px] border-b border-line">
                  <th class="py-2">TIME</th>
                  <th>DEVICE</th>
                  <th>LANE</th>
                  <th>PLATE</th>
                  <th>SPEED</th>
                  <th>COORD</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="telemetry in gpsTelemetry.slice(0, 8)" :key="telemetry.id" class="border-b border-line/60">
                  <td class="py-2 font-mono text-xs text-navy/70">{{ fmtTime(telemetry.capturedAt) }}</td>
                  <td class="font-mono text-xs">{{ telemetry.gpsDeviceId }}</td>
                  <td class="font-mono text-xs">{{ telemetry.laneId ?? '-' }}</td>
                  <td class="font-bold text-deep">{{ telemetry.plateNumber ?? '-' }}</td>
                  <td>{{ Number(telemetry.speedKmh ?? 0).toFixed(1) }} km/h</td>
                  <td class="font-mono text-xs">{{ fmtCoord(telemetry.latitude) }}, {{ fmtCoord(telemetry.longitude) }}</td>
                </tr>
                <tr v-if="gpsTelemetry.length === 0">
                  <td colspan="6" class="py-6 text-center text-sm text-navy/50">휴대폰 공기계 GPS/LTE telemetry가 들어오면 여기에 표시됩니다.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="card">
          <h2 class="font-bold text-navy mb-4">검수 게시글 등록</h2>
          <form class="space-y-3" @submit.prevent="submitPost">
            <input v-model="newPost.title" placeholder="제목" class="input-field" />
            <textarea v-model="newPost.content" placeholder="내용" class="input-field" rows="3" />
            <input v-model="newPost.plateNumber" placeholder="차량번호 (선택)" class="input-field" />
            <div class="grid grid-cols-2 gap-2">
              <input v-model.number="newPost.vehicleCount" type="number" min="1" placeholder="차량 수" class="input-field" />
              <input v-model.number="newPost.recognitionConfidence" type="number" min="0" max="1" step="0.01" placeholder="신뢰도" class="input-field" />
            </div>
            <button type="submit" class="btn-primary w-full" :disabled="postSubmitting">
              {{ postSubmitting ? '등록 중...' : '등록' }}
            </button>
          </form>
        </article>
      </section>
    </div>
  </div>
</template>
