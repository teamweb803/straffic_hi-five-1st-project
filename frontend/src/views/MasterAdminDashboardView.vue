<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { adminApi } from '@/api/admin'

const router = useRouter()
const auth = useAuthStore()

const THEME_STORAGE_KEY = 'hifive.dashboard.theme'
const nowText = ref('')
const themeMode = ref(localStorage.getItem(THEME_STORAGE_KEY) || 'dark')
const activeMenu = ref('대시보드')
const activeTab = ref('companies')
const selectedCenter = ref('서울 톨게이트')
const search = ref('')
const members = ref([])
const companies = ref([])
const memberMessage = ref('')
const showCompanyModal = ref(false)
const companyModalMessage = ref('')
const savingCompany = ref(false)
const companyForm = ref({
  name: '',
  owner: '',
  phone: '',
  email: '',
  centers: 0,
  status: '정상'
})

const kpiSection = ref(null)
const mapSection = ref(null)
const mapStage = ref(null)
const centerSection = ref(null)
const noticeSection = ref(null)
const companySection = ref(null)
const isMapEditMode = ref(false)
const draggingCenterName = ref('')
const draggingLabelName = ref('')
const isLightMode = computed(() => themeMode.value === 'light')

function toggleThemeMode() {
  themeMode.value = isLightMode.value ? 'dark' : 'light'
  localStorage.setItem(THEME_STORAGE_KEY, themeMode.value)
}

let timer = null
const MAP_MARKER_STORAGE_KEY = 'hifive.masterAdmin.mapMarkers.v1'

const menuGroups = [
  { label: '대시보드', icon: '⌂' },
  {
    label: '회원사 관리',
    icon: '▦',
    children: ['회원사 목록', '계정 관리', '권한 관리', '요금 정산 관리']
  },
  { label: '지점(관제센터) 관리', icon: '⌾' },
  { label: '단말기 관리', icon: '▣' },
  { label: '시스템 모니터링', icon: '▤' },
  { label: '공지사항', icon: '◇' },
  { label: '감사 로그', icon: '□' },
  { label: '설정', icon: '⚙' }
]

const centers = ref([
  { name: '서울 톨게이트', current: 1248, today: 12456, status: '정상', x: 38.6, y: 27.6, labelX: -116, labelY: -18, dashboardId: 'SEOUL-TOLL' },
  { name: '수원 톨게이트', current: 987, today: 9876, status: '정상', x: 37.8, y: 42.2, labelX: -116, labelY: -18, dashboardId: 'SUWON-TOLL' },
  { name: '대전 톨게이트', current: 765, today: 7654, status: '주의', x: 42.1, y: 56.4, labelX: -116, labelY: -18, dashboardId: 'DAEJEON-TOLL' },
  { name: '대구 톨게이트', current: 532, today: 5321, status: '점검중', x: 64.4, y: 61.0, labelX: 20, labelY: -18, dashboardId: 'DAEGU-TOLL' },
  { name: '부산 톨게이트', current: 1102, today: 11023, status: '정상', x: 65.2, y: 75.8, labelX: 20, labelY: -18, dashboardId: 'BUSAN-TOLL' },
  { name: '광주 톨게이트', current: 624, today: 6120, status: '정상', x: 37.8, y: 79.0, labelX: -116, labelY: -18, dashboardId: 'GWANGJU-TOLL' },
  { name: '강릉 톨게이트', current: 410, today: 4320, status: '정상', x: 64.0, y: 18.7, labelX: 20, labelY: -18, dashboardId: 'GANGNEUNG-TOLL' },
  { name: '제주 톨게이트', current: 302, today: 2210, status: '정상', x: 46.2, y: 96.0, labelX: 20, labelY: -18, dashboardId: 'JEJU-TOLL' }
])

const notices = [
  { title: '[공지] 시스템 점검 안내 (05/25 00:00 ~ 02:00)', date: '2025-05-20' },
  { title: '[안내] 요금 정산 시스템 업데이트 완료', date: '2025-05-19' },
  { title: '[안내] GPS 단말기 펌웨어 업데이트 안내', date: '2025-05-18' },
  { title: '[공지] 개인정보 처리방침 변경 안내', date: '2025-05-15' }
]

const topCenters = computed(() => centers.value.slice(0, 5))

const filteredCompanies = computed(() => {
  const keyword = search.value.trim()
  return companies.value.filter((company) => !keyword || company.name.includes(keyword))
})

const filteredMembers = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return members.value.filter((member) => {
    return !keyword ||
      member.email?.toLowerCase().includes(keyword) ||
      member.memberName?.toLowerCase().includes(keyword)
  })
})

const subpageTitle = computed(() => {
  if (activeMenu.value === '회원사 관리') return '회원사 목록'
  return activeMenu.value
})

const subpageDescription = computed(() => {
  const descriptions = {
    '회원사 목록': '등록된 회원사 정보를 조회하고 수정, 권한 설정을 관리합니다.',
    '계정 관리': '회원 계정의 로그인 정보, 상태, 허용 대시보드를 관리합니다.',
    '권한 관리': '회원별 접근 가능 지점과 정산/단말/공지 권한을 설정합니다.',
    '요금 정산 관리': '회원사별 정산 상태와 미정산 건을 확인합니다.',
    '지점(관제센터) 관리': '전국 톨게이트 지점의 운영 상태와 대시보드 진입을 관리합니다.',
    '단말기 관리': 'GPS/OCR 수집 단말 상태와 배치 지점을 관리합니다.',
    '시스템 모니터링': '서버, DB, GPS 수신 상태를 점검합니다.',
    '공지사항': '회원사와 지점에 노출할 공지사항을 관리합니다.',
    '감사 로그': '관리자 작업 이력과 권한 변경 이력을 확인합니다.',
    '설정': '마스터 관리자 콘솔의 기본 표시와 운영 정책을 설정합니다.'
  }
  return descriptions[subpageTitle.value] ?? '선택한 관리 항목의 상세 설정을 확인합니다.'
})

const deviceRows = [
  { id: 'PICO2W-NEO7M-RC-01', center: '서울 톨게이트', type: 'GPS', status: '정상', lastSeen: '10:32:45' },
  { id: 'EDGE-OCR-CAM-SEOUL-01', center: '서울 톨게이트', type: 'OCR', status: '정상', lastSeen: '10:32:41' },
  { id: 'PICO2W-NEO7M-DAEJEON-01', center: '대전 톨게이트', type: 'GPS', status: '주의', lastSeen: '10:28:10' },
  { id: 'EDGE-OCR-CAM-DAEGU-01', center: '대구 톨게이트', type: 'OCR', status: '점검중', lastSeen: '09:51:22' }
]

const auditRows = [
  { time: '2026-05-08 10:24:11', actor: 'master', action: '서울 톨게이트 마커 위치 수정', result: '성공' },
  { time: '2026-05-08 10:18:02', actor: 'master', action: '회원 대시보드 권한 변경', result: '성공' },
  { time: '2026-05-08 09:42:33', actor: 'admin@hifive.com', action: '회원사 목록 조회', result: '성공' }
]

function updateTime() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function statusClass(status) {
  if (status === '정상') return 'ok'
  if (status === '주의') return 'caution'
  if (status === '점검중') return 'danger'
  return 'muted'
}

function statusText(status) {
  return status === '점검중' ? '점검중' : status
}

function applyMapMarkerPositions(markerPositions) {
  if (!Array.isArray(markerPositions)) return

  markerPositions.forEach((position) => {
    const center = centers.value.find((item) => item.name === position.name)
    if (!center) return

    center.x = Number(position.x ?? center.x)
    center.y = Number(position.y ?? center.y)
    center.labelX = Number(position.labelX ?? center.labelX)
    center.labelY = Number(position.labelY ?? center.labelY)
  })
}

async function saveMapMarkerPositions() {
  const markerPositions = centers.value.map(({ name, x, y, labelX, labelY }) => ({
    name,
    x,
    y,
    labelX,
    labelY
  }))
  localStorage.setItem(MAP_MARKER_STORAGE_KEY, JSON.stringify(markerPositions))

  try {
    await adminApi.saveMapMarkers(markerPositions)
  } catch {
    memberMessage.value = '지도 위치를 백엔드에 저장하지 못했습니다. 로그인 상태와 백엔드 실행 상태를 확인해 주세요.'
  }
}

async function loadMapMarkerPositions() {
  try {
    const { data } = await adminApi.mapMarkers()
    if (Array.isArray(data) && data.length > 0) {
      applyMapMarkerPositions(data)
      localStorage.setItem(MAP_MARKER_STORAGE_KEY, JSON.stringify(data))
      return
    }
  } catch {
    memberMessage.value = '저장된 지도 위치를 백엔드에서 불러오지 못해 브라우저 캐시를 사용합니다.'
  }

  const saved = localStorage.getItem(MAP_MARKER_STORAGE_KEY)
  if (!saved) return

  try {
    const markerPositions = JSON.parse(saved)
    applyMapMarkerPositions(markerPositions)
  } catch {
    localStorage.removeItem(MAP_MARKER_STORAGE_KEY)
  }
}

async function fetchMembers() {
  const { data } = await adminApi.members()
  members.value = data
}

async function fetchCompanies() {
  const { data } = await adminApi.companies()
  companies.value = data
}

function openCompanyModal() {
  companyForm.value = {
    name: '',
    owner: '',
    phone: '',
    email: '',
    centers: 0,
    status: '정상'
  }
  companyModalMessage.value = ''
  showCompanyModal.value = true
}

async function createCompany() {
  if (savingCompany.value) return

  if (!companyForm.value.name || !companyForm.value.owner || !companyForm.value.phone || !companyForm.value.email) {
    companyModalMessage.value = '회원사명, 대표자, 연락처, 이메일을 모두 입력해 주세요.'
    return
  }

  if (Number(companyForm.value.centers) < 0) {
    companyModalMessage.value = '지점 수는 0 이상으로 입력해 주세요.'
    return
  }

  savingCompany.value = true
  companyModalMessage.value = ''

  try {
    const { data } = await adminApi.createCompany({
      ...companyForm.value,
      centers: Number(companyForm.value.centers)
    })
    companies.value = [...companies.value, data]
    showCompanyModal.value = false
    memberMessage.value = `${data.name} 회원사가 추가되었습니다.`
  } catch (error) {
    const status = error?.response?.status
    if (status === 403) {
      companyModalMessage.value = '관리자 세션이 만료되었거나 권한이 없습니다. admin 계정으로 다시 로그인해 주세요.'
    } else if (status === 400 || status === 500) {
      companyModalMessage.value = '회원사 추가에 실패했습니다. 이메일 중복 여부와 입력값을 확인해 주세요.'
    } else {
      companyModalMessage.value = '백엔드 연결 상태를 확인해 주세요.'
    }
  } finally {
    savingCompany.value = false
  }
}

async function assignDashboard(member, dashboardId) {
  const { data } = await adminApi.assignDashboard(member.email, dashboardId)
  members.value = members.value.map((item) => item.email === data.email ? data : item)
  memberMessage.value = `${data.memberName} 회원을 ${dashboardId || '미할당'} 대시보드에 연결했습니다.`
}

function activateMenu(menu) {
  activeMenu.value = menu

  if (menu === '대시보드') {
    kpiSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }

  if (['회원사 관리', '회원사 목록', '계정 관리', '권한 관리', '요금 정산 관리'].includes(menu)) {
    activeTab.value = menu === '계정 관리' ? 'accounts' : menu === '권한 관리' ? 'permissions' : 'companies'
    return
  }
}

function enterCenter(center) {
  selectedCenter.value = center.name
  router.push({ path: '/dashboard', query: { center: center.dashboardId } })
}

function enterCompactCenter(center) {
  selectedCenter.value = center.name
  router.push({ path: '/dashboard-compact', query: { center: center.dashboardId } })
}

function showActionMessage(message) {
  memberMessage.value = message
  window.alert(message)
}

function openQuickCompanyAdd() {
  activateMenu('회원사 목록')
  openCompanyModal()
}

function openCenterAdd() {
  activateMenu('지점(관제센터) 관리')
  showActionMessage('지점 추가 화면을 준비했습니다.')
}

function openNoticeCreate() {
  activateMenu('공지사항')
  showActionMessage('공지사항 등록 화면을 준비했습니다.')
}

function openSystemNotice() {
  activateMenu('시스템 모니터링')
  showActionMessage('시스템 공지 등록 화면을 준비했습니다.')
}

function showMoreNotices() {
  activateMenu('공지사항')
}

function zoomMap(action) {
  const actionText = action === 'reset' ? '초기화' : action === 'in' ? '확대' : '축소'
  showActionMessage(`지도 ${actionText} 기능을 적용했습니다.`)
}

function resetAccount(member) {
  showActionMessage(`${member.memberName} 계정의 비밀번호 초기화를 요청했습니다.`)
}

function editAccount(member) {
  showActionMessage(`${member.memberName} 계정 정보 수정 화면을 준비했습니다.`)
}

function toggleAccountLock(member) {
  showActionMessage(`${member.memberName} 계정 잠금 상태를 변경했습니다.`)
}

function exportSettlementReport() {
  showActionMessage('정산 리포트를 생성했습니다.')
}

function openDeviceRegister() {
  activateMenu('단말기 관리')
  showActionMessage('단말 등록 화면을 준비했습니다.')
}

function showDeviceDetail(device) {
  showActionMessage(`${device.id} 단말 상세 정보를 확인했습니다.`)
}

function exportAuditLog() {
  showActionMessage('감사 로그 내보내기를 시작했습니다.')
}

function saveMasterSettings() {
  showActionMessage('관리자 대시보드 설정이 저장되었습니다.')
}

function toggleMapEditMode() {
  if (isMapEditMode.value) {
    void saveMapMarkerPositions()
  }
  isMapEditMode.value = !isMapEditMode.value
  draggingCenterName.value = ''
  draggingLabelName.value = ''
}

function startMarkerDrag(event, center) {
  if (!isMapEditMode.value) return
  event.preventDefault()
  event.stopPropagation()
  draggingCenterName.value = center.name
  selectedCenter.value = center.name
  event.currentTarget.setPointerCapture?.(event.pointerId)
  updateMarkerPosition(event)
}

function updateMarkerPosition(event) {
  if (draggingLabelName.value) {
    updateLabelPosition(event)
    return
  }

  if (!draggingCenterName.value || !mapStage.value) return

  const rect = mapStage.value.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * 100
  const y = ((event.clientY - rect.top) / rect.height) * 100
  const center = centers.value.find((item) => item.name === draggingCenterName.value)

  if (!center) return
  center.x = Number(Math.min(96, Math.max(4, x)).toFixed(1))
  center.y = Number(Math.min(96, Math.max(4, y)).toFixed(1))
}

function startLabelDrag(event, center) {
  if (!isMapEditMode.value) return
  event.preventDefault()
  event.stopPropagation()
  draggingLabelName.value = center.name
  selectedCenter.value = center.name
  event.currentTarget.setPointerCapture?.(event.pointerId)
  updateLabelPosition(event)
}

function updateLabelPosition(event) {
  if (!draggingLabelName.value || !mapStage.value) return

  const rect = mapStage.value.getBoundingClientRect()
  const center = centers.value.find((item) => item.name === draggingLabelName.value)
  if (!center) return

  const markerX = (center.x / 100) * rect.width
  const markerY = (center.y / 100) * rect.height
  const pointerX = event.clientX - rect.left
  const pointerY = event.clientY - rect.top

  center.labelX = Number(Math.min(180, Math.max(-180, pointerX - markerX)).toFixed(0))
  center.labelY = Number(Math.min(90, Math.max(-90, pointerY - markerY)).toFixed(0))
}

function stopMarkerDrag() {
  if (draggingCenterName.value || draggingLabelName.value) {
    void saveMapMarkerPositions()
  }
  draggingCenterName.value = ''
  draggingLabelName.value = ''
}

function notifyCompanyEdited() {
  window.alert('회원사 정보가 수정되었습니다.')
}

function notifyPermissionSaved() {
  window.alert('권한 정보가 저장되었습니다.')
}

function logout() {
  window.alert('로그아웃 되었습니다.')
  auth.logout().finally(() => router.push('/'))
}

onMounted(() => {
  void loadMapMarkerPositions()
  updateTime()
  timer = setInterval(updateTime, 1000)
  fetchMembers().catch(() => {
    memberMessage.value = '회원 목록을 불러오지 못했습니다. 백엔드 실행 상태와 관리자 로그인을 확인해 주세요.'
  })
  fetchCompanies().catch(() => {
    memberMessage.value = '회원사 목록을 불러오지 못했습니다. 백엔드 실행 상태를 확인해 주세요.'
  })
})

onBeforeUnmount(() => {
  clearInterval(timer)
})
</script>

<template>
  <div class="master-shell" :class="{ light: isLightMode }">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-diamond"></span>
        <div>
          <strong>HI-FIVE</strong>
          <span>Master Admin Dashboard</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div v-for="menu in menuGroups" :key="menu.label" class="nav-group">
          <button
            class="nav-main"
            :class="{ active: activeMenu === menu.label || menu.children?.includes(activeMenu) }"
            type="button"
            @click="activateMenu(menu.label)"
          >
            <span class="nav-icon">{{ menu.icon }}</span>
            <span>{{ menu.label }}</span>
            <span v-if="menu.children" class="nav-caret">⌃</span>
          </button>

          <div v-if="menu.children" class="nav-children">
            <button
              v-for="child in menu.children"
              :key="child"
              :class="{ active: activeMenu === child }"
              type="button"
              @click="activateMenu(child)"
            >
              {{ child }}
            </button>
          </div>
        </div>
      </nav>

      <div class="quick-menu">
        <p>빠른 메뉴</p>
        <button type="button" @click="openQuickCompanyAdd">회원사 추가</button>
        <button type="button" @click="openCenterAdd">지점 추가</button>
        <button type="button" @click="openNoticeCreate">공지사항 등록</button>
        <button type="button" @click="openSystemNotice">시스템 공지</button>
      </div>

      <p class="copyright">© 2025 HI-FIVE All rights reserved.</p>
    </aside>

    <div class="content-shell">
      <header class="topbar">
        <div class="topbar-title">
          <span class="brand-diamond small"></span>
          <strong>HI-FIVE</strong>
          <span>Master Admin Dashboard</span>
        </div>

        <div class="header-tools">
          <span class="clock">◷ {{ nowText }}</span>
          <span class="system-state"><i></i>시스템 상태 : 정상</span>
          <span class="admin-chip"><b>{{ auth.member?.memberName ?? 'master' }}</b><small>최종 관리자</small></span>
          <button class="theme-btn" type="button" :title="isLightMode ? '다크 모드' : '라이트 모드'" :aria-label="isLightMode ? '다크 모드' : '라이트 모드'" @click="toggleThemeMode">
            <span>{{ isLightMode ? '☾' : '☀' }}</span>
          </button>
          <button class="home-btn" type="button" @click="router.push('/')">홈</button>
          <button class="logout-btn" type="button" @click="logout">로그아웃</button>
        </div>
      </header>

      <main>
        <template v-if="activeMenu === '대시보드'">
        <section ref="kpiSection" class="kpi-grid">
          <article class="kpi glass violet">
            <span class="kpi-icon">✓</span>
            <div>
              <p>전체 회원사</p>
              <strong>24</strong>
              <em>전일 대비 ▲ 2</em>
            </div>
          </article>
          <article class="kpi glass blue">
            <span class="kpi-icon">▣</span>
            <div>
              <p>전체 지점(관제센터)</p>
              <strong>38</strong>
              <em>전일 대비 ▲ 1</em>
            </div>
          </article>
          <article class="kpi glass green">
            <span class="kpi-icon">♟</span>
            <div>
              <p>오늘 전체 통행</p>
              <strong>128,456</strong>
              <em>전일 대비 ▲ 12.5%</em>
            </div>
          </article>
          <article class="kpi glass yellow">
            <span class="kpi-icon">▤</span>
            <div>
              <p>미정산 건수</p>
              <strong>1,248</strong>
              <em class="down">전일 대비 ▼ 5.3%</em>
            </div>
          </article>
          <article class="kpi glass cyan">
            <span class="kpi-icon">◆</span>
            <div>
              <p>시스템 상태</p>
              <strong>정상</strong>
              <em>모든 시스템 정상 운영 중</em>
            </div>
          </article>
        </section>

        <section class="dashboard-grid">
          <article ref="mapSection" class="map-panel glass">
            <div class="panel-title map-title">
              <h2>전국 지점 위치 현황</h2>
              <button
                class="map-edit-btn"
                :class="{ active: isMapEditMode }"
                type="button"
                @click="toggleMapEditMode"
              >
                {{ isMapEditMode ? '위치 편집 완료' : '위치 편집' }}
              </button>
            </div>

            <div
              ref="mapStage"
              class="map-stage"
              :class="{ editing: isMapEditMode }"
              @pointermove="updateMarkerPosition"
              @pointerup="stopMarkerDrag"
              @pointerleave="stopMarkerDrag"
            >
              <div class="state-summary">
                <div><i class="dot ok"></i><span>정상</span><strong>28</strong></div>
                <div><i class="dot caution"></i><span>주의</span><strong>7</strong></div>
                <div><i class="dot danger"></i><span>점검중</span><strong>3</strong></div>
              </div>

              <div class="map-zoom">
                <button type="button" @click="zoomMap('reset')">◎</button>
                <button type="button" @click="zoomMap('in')">＋</button>
                <button type="button" @click="zoomMap('out')">－</button>
              </div>

              <div
                v-for="center in centers"
                :key="center.name"
                class="map-marker"
                :class="[
                  statusClass(center.status),
                  {
                    selected: selectedCenter === center.name,
                    dragging: draggingCenterName === center.name,
                    labelDragging: draggingLabelName === center.name
                  }
                ]"
                :style="{ left: `${center.x}%`, top: `${center.y}%` }"
              >
                <button
                  class="pin"
                  type="button"
                  :title="isMapEditMode ? '포인터 위치 이동' : center.name"
                  @click="!isMapEditMode && (selectedCenter = center.name)"
                  @pointerdown="startMarkerDrag($event, center)"
                ></button>
                <button
                  class="marker-label"
                  type="button"
                  :style="{ transform: `translate(${center.labelX}px, ${center.labelY}px)` }"
                  :title="isMapEditMode ? '명칭 박스 위치 이동' : center.name"
                  @click="!isMapEditMode && (selectedCenter = center.name)"
                  @pointerdown="startLabelDrag($event, center)"
                >
                  <b>{{ center.name }}</b>
                  <small>{{ statusText(center.status) }}</small>
                </button>
              </div>
            </div>
          </article>

          <aside class="right-column">
            <article ref="centerSection" class="panel glass">
              <div class="panel-title">
                <h2>지점별 실시간 통행 현황 (상위 5)</h2>
              </div>

              <table class="control-table">
                <thead>
                  <tr>
                    <th>지점명</th>
                    <th>현재 통행</th>
                    <th>오늘 통행</th>
                    <th>상태</th>
                    <th>대시보드</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="center in topCenters"
                    :key="center.name"
                    :class="{ selected: selectedCenter === center.name }"
                  >
                    <td>{{ center.name }}</td>
                    <td>{{ center.current.toLocaleString() }}</td>
                    <td>{{ center.today.toLocaleString() }}</td>
                    <td><span class="status" :class="statusClass(center.status)">{{ center.status }}</span></td>
                    <td class="dashboard-entry-cell">
                      <button class="small-btn" type="button" @click="enterCenter(center)">진입1</button>
                      <button class="small-btn compact-entry-btn" type="button" @click="enterCompactCenter(center)">진입2</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </article>

            <article ref="noticeSection" class="panel glass notice-panel">
              <div class="panel-title with-button">
                <h2>시스템 공지사항</h2>
                <button class="text-btn" type="button" @click="showMoreNotices">더보기 ›</button>
              </div>
              <ul class="notice-list">
                <li v-for="notice in notices" :key="notice.title">
                  <span>{{ notice.title }}</span>
                  <time>{{ notice.date }}</time>
                </li>
              </ul>
            </article>
          </aside>
        </section>

        <section ref="companySection" class="bottom-grid">
          <article class="panel glass donut-panel">
            <div class="panel-title">
              <h2>회원사 통계</h2>
            </div>
            <div class="donut-content">
              <div class="donut"><span>24</span></div>
              <div class="legend">
                <p><i class="legend-dot ok"></i><span>정상</span><strong>18 (75%)</strong></p>
                <p><i class="legend-dot caution"></i><span>주의</span><strong>4 (16.7%)</strong></p>
                <p><i class="legend-dot inactive"></i><span>비활성</span><strong>2 (8.3%)</strong></p>
              </div>
            </div>
          </article>

          <article class="panel glass company-panel">
            <div class="company-toolbar">
              <div class="tab-row">
                <button :class="{ active: activeTab === 'companies' }" type="button" @click="activeTab = 'companies'">회원사 목록</button>
                <button :class="{ active: activeTab === 'accounts' }" type="button" @click="activeTab = 'accounts'">계정 관리</button>
                <button :class="{ active: activeTab === 'permissions' }" type="button" @click="activeTab = 'permissions'">권한 관리</button>
              </div>
              <label class="search-box">
                <input v-model.trim="search" type="search" placeholder="회원사명 검색..." />
                <span>⌕</span>
              </label>
              <button class="small-btn add-btn" type="button" @click="openCompanyModal">회원사 추가</button>
            </div>

            <p v-if="memberMessage" class="message">{{ memberMessage }}</p>

            <table v-if="activeTab === 'companies'" class="control-table member-table">
              <thead>
                <tr>
                  <th>회원사명</th>
                  <th>대표자</th>
                  <th>연락처</th>
                  <th>이메일</th>
                  <th>지점 수</th>
                  <th>상태</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="company in filteredCompanies" :key="company.email">
                  <td>{{ company.name }}</td>
                  <td>{{ company.owner }}</td>
                  <td>{{ company.phone }}</td>
                  <td>{{ company.email }}</td>
                  <td>{{ company.centers }}</td>
                  <td><span class="status" :class="statusClass(company.status)">{{ company.status }}</span></td>
                  <td>
                    <button class="small-btn" type="button" @click="notifyCompanyEdited">수정</button>
                    <button class="small-btn" type="button" @click="notifyPermissionSaved">권한</button>
                  </td>
                </tr>
              </tbody>
            </table>

            <table v-else-if="activeTab === 'accounts'" class="control-table member-table">
              <thead>
                <tr>
                  <th>계정 ID</th>
                  <th>담당자</th>
                  <th>권한</th>
                  <th>허용 대시보드</th>
                  <th>계정 상태</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in filteredMembers" :key="member.email">
                  <td>{{ member.email }}</td>
                  <td>{{ member.memberName }}</td>
                  <td>{{ member.role }}</td>
                  <td>{{ member.assignedDashboardId ?? '-' }}</td>
                  <td><span class="status ok">정상</span></td>
                  <td>
                    <button class="small-btn" type="button" @click="resetAccount(member)">초기화</button>
                    <button class="small-btn" type="button" @click="editAccount(member)">수정</button>
                    <button class="small-btn" type="button" @click="toggleAccountLock(member)">잠금</button>
                  </td>
                </tr>
              </tbody>
            </table>

            <table v-else class="control-table member-table">
              <thead>
                <tr>
                  <th>회원</th>
                  <th>계정 ID</th>
                  <th>권한 등급</th>
                  <th>접근 가능 지점</th>
                  <th>정산 권한</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in filteredMembers" :key="member.email">
                  <td>{{ member.memberName }}</td>
                  <td>{{ member.email }}</td>
                  <td>{{ member.role }}</td>
                  <td>
                    <select :value="member.assignedDashboardId" @change="assignDashboard(member, $event.target.value)">
                      <option value="">미할당</option>
                      <option v-for="center in centers" :key="center.dashboardId" :value="center.dashboardId">
                        {{ center.name }}
                      </option>
                    </select>
                  </td>
                  <td>{{ member.role === 'MASTER_ADMIN' ? '전체' : '허용' }}</td>
                  <td><button class="small-btn" type="button" @click="notifyPermissionSaved">권한 수정</button></td>
                </tr>
              </tbody>
            </table>
          </article>
        </section>
        </template>

        <section v-else class="subpage-shell">
          <article class="panel glass subpage-hero">
            <div>
              <p class="subpage-kicker">MASTER ADMIN</p>
              <h2>{{ subpageTitle }}</h2>
              <span>{{ subpageDescription }}</span>
            </div>
            <button class="home-btn" type="button" @click="activeMenu = '대시보드'">대시보드로 이동</button>
          </article>

          <article v-if="['회원사 관리', '회원사 목록'].includes(activeMenu)" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>회원사 목록</h3>
              <div class="toolbar-actions">
                <label class="search-box wide">
                  <input v-model.trim="search" type="search" placeholder="회원사명 검색..." />
                  <span>⌕</span>
                </label>
                <button class="small-btn add-btn" type="button" @click="openCompanyModal">회원사 추가</button>
              </div>
            </div>
            <table class="control-table member-table">
              <thead>
                <tr>
                  <th>회원사명</th>
                  <th>대표자</th>
                  <th>연락처</th>
                  <th>이메일</th>
                  <th>지점 수</th>
                  <th>상태</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="company in filteredCompanies" :key="company.email">
                  <td>{{ company.name }}</td>
                  <td>{{ company.owner }}</td>
                  <td>{{ company.phone }}</td>
                  <td>{{ company.email }}</td>
                  <td>{{ company.centers }}</td>
                  <td><span class="status" :class="statusClass(company.status)">{{ company.status }}</span></td>
                  <td>
                    <button class="small-btn" type="button" @click="notifyCompanyEdited">수정</button>
                    <button class="small-btn" type="button" @click="notifyPermissionSaved">권한</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </article>

          <article v-else-if="activeMenu === '계정 관리'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>계정 관리</h3>
              <label class="search-box wide">
                <input v-model.trim="search" type="search" placeholder="이메일 또는 담당자 검색..." />
                <span>⌕</span>
              </label>
            </div>
            <table class="control-table member-table">
              <thead>
                <tr>
                  <th>계정 ID</th>
                  <th>담당자</th>
                  <th>권한</th>
                  <th>허용 대시보드</th>
                  <th>계정 상태</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in filteredMembers" :key="member.email">
                  <td>{{ member.email }}</td>
                  <td>{{ member.memberName }}</td>
                  <td>{{ member.role }}</td>
                  <td>{{ member.assignedDashboardId ?? '-' }}</td>
                  <td><span class="status ok">정상</span></td>
                  <td>
                    <button class="small-btn" type="button" @click="resetAccount(member)">초기화</button>
                    <button class="small-btn" type="button" @click="editAccount(member)">수정</button>
                    <button class="small-btn" type="button" @click="toggleAccountLock(member)">잠금</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </article>

          <article v-else-if="activeMenu === '권한 관리'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>권한 관리</h3>
              <span class="subpage-note">회원별 접근 가능 관제 대시보드를 지정합니다.</span>
            </div>
            <table class="control-table member-table">
              <thead>
                <tr>
                  <th>회원</th>
                  <th>계정 ID</th>
                  <th>권한 등급</th>
                  <th>접근 가능 지점</th>
                  <th>정산 권한</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="member in filteredMembers" :key="member.email">
                  <td>{{ member.memberName }}</td>
                  <td>{{ member.email }}</td>
                  <td>{{ member.role }}</td>
                  <td>
                    <select :value="member.assignedDashboardId" @change="assignDashboard(member, $event.target.value)">
                      <option value="">미할당</option>
                      <option v-for="center in centers" :key="center.dashboardId" :value="center.dashboardId">
                        {{ center.name }}
                      </option>
                    </select>
                  </td>
                  <td>{{ member.role === 'MASTER_ADMIN' ? '전체' : '허용' }}</td>
                  <td><button class="small-btn" type="button" @click="notifyPermissionSaved">권한 수정</button></td>
                </tr>
              </tbody>
            </table>
          </article>

          <article v-else-if="activeMenu === '요금 정산 관리'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>요금 정산 관리</h3>
              <button class="small-btn" type="button" @click="exportSettlementReport">정산 리포트</button>
            </div>
            <div class="summary-grid">
              <div><span>오늘 총 정산</span><strong>₩2,450,800</strong></div>
              <div><span>미정산 건수</span><strong>1,248</strong></div>
              <div><span>보류 금액</span><strong>₩320,400</strong></div>
            </div>
          </article>

          <article v-else-if="activeMenu === '지점(관제센터) 관리'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>지점(관제센터) 관리</h3>
              <button class="small-btn" type="button" @click="openCenterAdd">지점 추가</button>
            </div>
            <table class="control-table member-table">
              <thead>
                <tr>
                  <th>지점명</th>
                  <th>현재 통행</th>
                  <th>오늘 통행</th>
                  <th>상태</th>
                  <th>대시보드</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="center in centers" :key="center.name">
                  <td>{{ center.name }}</td>
                  <td>{{ center.current.toLocaleString() }}</td>
                  <td>{{ center.today.toLocaleString() }}</td>
                  <td><span class="status" :class="statusClass(center.status)">{{ center.status }}</span></td>
                  <td class="dashboard-entry-cell">
                    <button class="small-btn" type="button" @click="enterCenter(center)">진입1</button>
                    <button class="small-btn compact-entry-btn" type="button" @click="enterCompactCenter(center)">진입2</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </article>

          <article v-else-if="activeMenu === '단말기 관리'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>단말기 관리</h3>
              <button class="small-btn" type="button" @click="openDeviceRegister">단말 등록</button>
            </div>
            <table class="control-table member-table">
              <thead>
                <tr>
                  <th>단말 ID</th>
                  <th>연결 지점</th>
                  <th>유형</th>
                  <th>상태</th>
                  <th>최근 수신</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="device in deviceRows" :key="device.id">
                  <td>{{ device.id }}</td>
                  <td>{{ device.center }}</td>
                  <td>{{ device.type }}</td>
                  <td><span class="status" :class="statusClass(device.status)">{{ device.status }}</span></td>
                  <td>{{ device.lastSeen }}</td>
                  <td><button class="small-btn" type="button" @click="showDeviceDetail(device)">상세</button></td>
                </tr>
              </tbody>
            </table>
          </article>

          <article v-else-if="activeMenu === '시스템 모니터링'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>시스템 모니터링</h3>
              <span class="subpage-note">실시간 운영 상태</span>
            </div>
            <div class="summary-grid">
              <div><span>Spring Boot</span><strong>정상</strong></div>
              <div><span>PostgreSQL</span><strong>정상</strong></div>
              <div><span>GPS 수신</span><strong>3대</strong></div>
              <div><span>OCR Edge</span><strong>2대</strong></div>
            </div>
          </article>

          <article v-else-if="activeMenu === '공지사항'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>공지사항</h3>
              <button class="small-btn" type="button" @click="openNoticeCreate">공지 등록</button>
            </div>
            <ul class="notice-list page-list">
              <li v-for="notice in notices" :key="notice.title">
                <span>{{ notice.title }}</span>
                <time>{{ notice.date }}</time>
              </li>
            </ul>
          </article>

          <article v-else-if="activeMenu === '감사 로그'" class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>감사 로그</h3>
              <button class="small-btn" type="button" @click="exportAuditLog">내보내기</button>
            </div>
            <table class="control-table member-table">
              <thead>
                <tr>
                  <th>시간</th>
                  <th>작업자</th>
                  <th>작업 내용</th>
                  <th>결과</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="audit in auditRows" :key="audit.time">
                  <td>{{ audit.time }}</td>
                  <td>{{ audit.actor }}</td>
                  <td>{{ audit.action }}</td>
                  <td><span class="status ok">{{ audit.result }}</span></td>
                </tr>
              </tbody>
            </table>
          </article>

          <article v-else class="panel glass subpage-panel">
            <div class="subpage-toolbar">
              <h3>설정</h3>
              <button class="small-btn" type="button" @click="saveMasterSettings">저장</button>
            </div>
            <div class="settings-grid">
              <label><span>기본 지도 편집</span><select><option>허용</option><option>차단</option></select></label>
              <label><span>대시보드 자동 새로고침</span><select><option>30초</option><option>1분</option><option>수동</option></select></label>
              <label><span>공지 노출 범위</span><select><option>전체 회원사</option><option>선택 회원사</option></select></label>
            </div>
          </article>
        </section>

        <div v-if="showCompanyModal" class="modal-backdrop" @click.self="showCompanyModal = false">
          <form class="company-modal glass" @submit.prevent="createCompany">
            <div class="modal-head">
              <div>
                <p class="subpage-kicker">COMPANY</p>
                <h3>회원사 추가</h3>
              </div>
              <button class="modal-close" type="button" @click="showCompanyModal = false">×</button>
            </div>

            <div class="modal-grid">
              <label>
                <span>회원사명</span>
                <input v-model.trim="companyForm.name" required type="text" placeholder="예: 인천 하이패스(주)" />
              </label>
              <label>
                <span>대표자</span>
                <input v-model.trim="companyForm.owner" required type="text" placeholder="대표자명" />
              </label>
              <label>
                <span>연락처</span>
                <input v-model.trim="companyForm.phone" required type="text" placeholder="032-123-4567" />
              </label>
              <label>
                <span>이메일</span>
                <input v-model.trim="companyForm.email" required type="email" placeholder="company@hipass.com" />
              </label>
              <label>
                <span>지점 수</span>
                <input v-model.number="companyForm.centers" min="0" required type="number" />
              </label>
              <label>
                <span>상태</span>
                <select v-model="companyForm.status">
                  <option>정상</option>
                  <option>주의</option>
                  <option>비활성</option>
                </select>
              </label>
            </div>

            <p v-if="companyModalMessage" class="modal-message">{{ companyModalMessage }}</p>

            <div class="modal-actions">
              <button class="small-btn" type="button" @click="showCompanyModal = false">취소</button>
              <button class="small-btn add-btn" type="button" :disabled="savingCompany" @click="createCompany">
                {{ savingCompany ? '저장 중...' : '저장' }}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
:global(body) {
  background: #030812;
}

* {
  box-sizing: border-box;
}

button,
input,
select {
  font: inherit;
}

button {
  cursor: pointer;
}

.master-shell {
  min-height: 100vh;
  min-width: 1440px;
  display: grid;
  grid-template-columns: 235px 1fr;
  color: #dce9f7;
  background:
    radial-gradient(circle at 76% 18%, rgba(0, 130, 255, 0.1), transparent 26%),
    radial-gradient(circle at 22% 10%, rgba(37, 198, 255, 0.09), transparent 25%),
    linear-gradient(135deg, #030812 0%, #06101f 48%, #030812 100%);
}

.glass {
  border: 1px solid rgba(42, 133, 227, 0.38);
  background:
    linear-gradient(145deg, rgba(11, 27, 51, 0.86), rgba(4, 13, 28, 0.72)),
    rgba(5, 16, 33, 0.72);
  box-shadow: 0 0 0 1px rgba(14, 111, 219, 0.08), 0 18px 42px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(16px);
}

.sidebar {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 16px 14px;
  border-right: 1px solid rgba(41, 129, 219, 0.34);
  background: linear-gradient(180deg, rgba(4, 13, 28, 0.98), rgba(4, 20, 40, 0.96));
}

.sidebar-brand,
.topbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar-brand {
  height: 54px;
  margin-bottom: 18px;
}

.sidebar-brand strong,
.topbar-title strong {
  color: #fff;
  font-size: 28px;
  line-height: 1;
  letter-spacing: 0.02em;
}

.sidebar-brand span:not(.brand-diamond),
.topbar-title span:not(.brand-diamond) {
  color: #d7e6ff;
  font-size: 14px;
}

.brand-diamond {
  width: 23px;
  height: 23px;
  display: inline-block;
  position: relative;
  border: 3px solid #1683ff;
  transform: rotate(45deg);
  box-shadow: 0 0 8px rgba(22, 131, 255, 0.32);
}

.brand-diamond::after {
  content: '';
  position: absolute;
  inset: 5px;
  border-radius: 50%;
  background: #1683ff;
}

.brand-diamond.small {
  width: 18px;
  height: 18px;
  border-width: 2px;
}

.sidebar-nav {
  display: grid;
  gap: 8px;
}

.nav-main,
.nav-children button,
.quick-menu button {
  width: 100%;
  border: 0;
  color: #c9d7eb;
  background: transparent;
}

.nav-main {
  height: 38px;
  display: grid;
  grid-template-columns: 22px 1fr 16px;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border-radius: 5px;
  text-align: left;
  font-size: 12.5px;
  white-space: nowrap;
}

.nav-main.active {
  color: #fff;
  border: 1px solid rgba(33, 130, 255, 0.7);
  background: linear-gradient(90deg, rgba(22, 103, 219, 0.45), rgba(17, 78, 153, 0.23));
  box-shadow: inset 0 0 24px rgba(22, 131, 255, 0.18);
}

.nav-icon {
  color: #d9e7ff;
  text-align: center;
}

.nav-caret {
  color: #94a9c4;
  font-size: 12px;
}

.nav-children {
  display: grid;
  gap: 2px;
  margin: 6px 0 12px 32px;
  padding-left: 13px;
  border-left: 1px solid rgba(117, 151, 194, 0.3);
}

.nav-children button {
  height: 29px;
  position: relative;
  padding-left: 8px;
  text-align: left;
  font-size: 12px;
  color: #9fb2cb;
  white-space: nowrap;
}

.nav-children button::before {
  content: '';
  width: 4px;
  height: 4px;
  position: absolute;
  left: -15px;
  top: 12px;
  border-radius: 50%;
  background: #5c7392;
}

.nav-children button.active,
.nav-children button:hover,
.nav-main:hover {
  color: #fff;
}

.quick-menu {
  margin-top: auto;
  padding: 14px;
  border: 1px solid rgba(42, 133, 227, 0.28);
  border-radius: 6px;
  background: rgba(5, 18, 37, 0.64);
}

.quick-menu p {
  margin: 0 0 12px;
  color: #9db1cb;
  font-size: 12px;
}

.quick-menu button {
  height: 37px;
  margin-top: 8px;
  border: 1px solid rgba(42, 133, 227, 0.46);
  border-radius: 5px;
  background: linear-gradient(180deg, rgba(18, 53, 100, 0.78), rgba(8, 30, 60, 0.74));
}

.copyright {
  margin: 26px 14px 0;
  color: #8192aa;
  font-size: 11px;
}

.content-shell {
  min-width: 0;
}

.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 26px 0 18px;
  border-bottom: 1px solid rgba(42, 133, 227, 0.28);
  background: rgba(2, 9, 20, 0.72);
}

.topbar-title strong {
  font-size: 25px;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 14px;
  color: #d8e6f8;
  font-size: 13px;
}

.clock {
  color: #e5efff;
}

.system-state {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding-left: 14px;
  border-left: 1px solid rgba(120, 157, 201, 0.35);
  color: #eaf4ff;
}

.system-state i {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #4cdf66;
  box-shadow: 0 0 15px rgba(76, 223, 102, 0.75);
}

.admin-chip {
  display: grid;
  grid-template-columns: 26px auto;
  column-gap: 8px;
  align-items: center;
  color: #eaf4ff;
}

.admin-chip::before {
  content: '';
  width: 26px;
  height: 26px;
  grid-row: span 2;
  border-radius: 50%;
  background: linear-gradient(180deg, #47617e, #1b2d45);
}

.admin-chip small {
  color: #b8c7da;
}

.home-btn,
.theme-btn,
.logout-btn,
.small-btn,
.text-btn,
.map-zoom button,
.tab-row button {
  border: 1px solid rgba(42, 133, 227, 0.45);
  color: #e5f0ff;
  background: linear-gradient(180deg, rgba(15, 49, 92, 0.78), rgba(6, 24, 50, 0.78));
}

.home-btn,
.theme-btn,
.logout-btn {
  height: 34px;
  padding: 0 16px;
  border-radius: 5px;
}

.theme-btn {
  width: 34px;
  min-width: 34px;
  padding: 0;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-weight: 700;
  color: #f8fbff;
  background: linear-gradient(135deg, rgba(22, 131, 255, 0.36), rgba(52, 211, 153, 0.18));
  box-shadow: 0 0 14px rgba(22, 131, 255, 0.18);
}

.theme-btn span {
  display: block;
  font-size: 16px;
  line-height: 1;
}

main {
  padding: 20px 16px 22px 18px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.kpi {
  min-height: 96px;
  display: grid;
  grid-template-columns: 70px 1fr;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 6px;
}

.kpi-icon {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06101f;
  font-weight: 900;
  font-size: 21px;
}

.kpi.violet .kpi-icon { background: linear-gradient(135deg, #aab0ff, #7a6cff); box-shadow: 0 0 12px rgba(122, 108, 255, 0.24); }
.kpi.blue .kpi-icon { background: linear-gradient(135deg, #35b7ff, #1378ef); box-shadow: 0 0 12px rgba(19, 120, 239, 0.24); }
.kpi.green .kpi-icon { background: linear-gradient(135deg, #5ff5be, #16a373); box-shadow: 0 0 12px rgba(22, 163, 115, 0.24); }
.kpi.yellow .kpi-icon { background: linear-gradient(135deg, #ffe16e, #ffb928); box-shadow: 0 0 12px rgba(255, 185, 40, 0.24); }
.kpi.cyan .kpi-icon { background: linear-gradient(135deg, #2be7e4, #15a7ba); box-shadow: 0 0 12px rgba(43, 231, 228, 0.24); }

.kpi p {
  margin: 0;
  color: #e6f1ff;
  font-size: 13px;
  font-weight: 700;
}

.kpi strong {
  display: block;
  margin-top: 4px;
  color: #fff;
  font-size: 28px;
  line-height: 1.1;
}

.kpi em {
  display: block;
  margin-top: 4px;
  color: #5fe080;
  font-size: 12px;
  font-style: normal;
}

.kpi em.down {
  color: #ff704f;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.map-panel {
  grid-column: span 3;
}

.right-column {
  grid-column: span 2;
}

.panel,
.map-panel {
  border-radius: 6px;
}

.map-panel {
  position: relative;
  overflow: hidden;
  padding: 12px;
  background: #04101e;
}

.map-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url('/korea_road_backmap.png') center / 100% 100% no-repeat;
}

.map-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(rgba(4, 13, 28, 0.08), rgba(4, 13, 28, 0.46));
  pointer-events: none;
}

.panel {
  padding: 13px;
}

.panel-title {
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 2;
  margin-bottom: 11px;
  padding-left: 10px;
  border-left: 2px solid #1683ff;
}

.panel-title h2 {
  margin: 0;
  color: #f1f7ff;
  font-size: 16px;
  font-weight: 800;
}

.map-title {
  padding-right: 2px;
}

.map-edit-btn {
  height: 30px;
  padding: 0 12px;
  border: 1px solid rgba(42, 133, 227, 0.46);
  border-radius: 5px;
  color: #d9eaff;
  background: rgba(5, 18, 37, 0.72);
}

.map-edit-btn.active {
  border-color: #4cdf66;
  color: #8ff7a5;
  background: rgba(35, 136, 68, 0.18);
}

.map-stage {
  height: 468px;
  position: relative;
  z-index: 2;
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.map-stage.editing {
  cursor: grab;
}

.map-stage::after {
  display: none;
}

.state-summary {
  width: 132px;
  position: absolute;
  left: 13px;
  top: 13px;
  z-index: 2;
  padding: 10px 12px;
  border: 1px solid rgba(86, 149, 219, 0.34);
  border-radius: 5px;
  background: rgba(5, 16, 32, 0.78);
}

.state-summary div {
  display: grid;
  grid-template-columns: 13px 1fr auto;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  color: #cfdcf0;
  font-size: 13px;
}

.dot,
.legend-dot {
  width: 9px;
  height: 9px;
  display: inline-block;
  border-radius: 50%;
}

.ok { background: #48d86a; color: #48d86a; }
.caution { background: #ffd326; color: #ffd326; }
.danger { background: #ff6d34; color: #ff6d34; }
.inactive { background: #778392; color: #778392; }

.map-zoom {
  position: absolute;
  left: 13px;
  bottom: 13px;
  z-index: 2;
  display: grid;
  gap: 7px;
}

.map-zoom button {
  width: 34px;
  height: 34px;
  border-radius: 5px;
  background: rgba(4, 15, 31, 0.84);
}

.map-marker {
  position: absolute;
  z-index: 3;
  width: 0;
  height: 0;
  transform: translate(-50%, -50%);
  touch-action: none;
}

.map-stage.editing .map-marker {
  cursor: grab;
}

.map-stage.editing .map-marker:active,
.map-marker.dragging {
  cursor: grabbing;
}

.pin {
  width: 13px;
  height: 13px;
  position: absolute;
  left: 0;
  top: 0;
  border-radius: 50%;
  border: 0;
  background: currentColor;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.08), 0 0 10px currentColor;
  transform: translate(-50%, -50%);
}

.marker-label {
  min-width: 96px;
  position: absolute;
  left: 0;
  top: 0;
  display: grid;
  gap: 3px;
  padding: 8px 10px;
  border: 1px solid rgba(119, 162, 214, 0.45);
  border-radius: 5px;
  color: #eaf4ff;
  text-align: left;
  background: rgba(5, 16, 32, 0.82);
}

.map-stage.editing .marker-label {
  cursor: move;
}

.marker-label b {
  font-size: 12px;
}

.marker-label small {
  font-size: 12px;
  font-weight: 800;
}

.map-marker.ok .marker-label small {
  color: #48d86a;
}

.map-marker.caution .marker-label small {
  color: #ffd326;
}

.map-marker.danger .marker-label small {
  color: #ff8a34;
}

.map-marker.selected .pin {
  box-shadow: 0 0 0 6px rgba(16, 131, 255, 0.15), 0 0 14px currentColor;
}

.map-marker.selected .marker-label {
  border-color: #1683ff;
  box-shadow: 0 0 10px rgba(22, 131, 255, 0.2);
}

.map-marker.dragging .marker-label {
  border-color: rgba(119, 162, 214, 0.45);
}

.map-marker.dragging .pin {
  box-shadow: 0 0 0 6px rgba(76, 223, 102, 0.16), 0 0 14px currentColor;
}

.map-marker.labelDragging .marker-label {
  border-color: #4cdf66;
  box-shadow: 0 0 12px rgba(76, 223, 102, 0.22);
}

.right-column {
  display: grid;
  gap: 12px;
  grid-template-rows: 1fr auto;
}

.control-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid rgba(63, 118, 180, 0.18);
  border-radius: 5px;
}

.control-table th,
.control-table td {
  height: 39px;
  padding: 0 13px;
  border-bottom: 1px solid rgba(102, 139, 184, 0.14);
  color: #d6e2f2;
  text-align: left;
  font-size: 13px;
  white-space: nowrap;
}

.control-table th {
  height: 36px;
  color: #a8bad0;
  font-weight: 600;
  background: rgba(26, 46, 73, 0.64);
}

.control-table tr:last-child td {
  border-bottom: 0;
}

.control-table tbody tr {
  background: rgba(2, 10, 22, 0.28);
}

.control-table tbody tr.selected,
.control-table tbody tr:hover {
  background: rgba(22, 131, 255, 0.13);
}

.status {
  display: inline-flex;
  align-items: center;
  min-width: 48px;
  height: 24px;
  justify-content: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.04);
}

.status.ok {
  color: #48d86a;
}

.status.caution {
  color: #ffd326;
}

.status.danger {
  color: #ff6d34;
}

.small-btn {
  min-width: 54px;
  height: 26px;
  margin-right: 6px;
  padding: 0 10px;
  border-radius: 5px;
  color: #dbeaff;
  font-size: 12px;
}

.small-btn:hover,
.home-btn:hover,
.logout-btn:hover,
.tab-row button.active {
  border-color: #1683ff;
  background: rgba(22, 131, 255, 0.24);
  box-shadow: 0 0 16px rgba(22, 131, 255, 0.22);
}

.dashboard-entry-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.dashboard-entry-cell .small-btn {
  min-width: 48px;
  margin-right: 0;
  padding: 0 8px;
}

.compact-entry-btn {
  border-color: rgba(47, 224, 235, 0.42);
  background: rgba(18, 92, 112, 0.24);
}

.notice-panel {
  min-height: 172px;
}

.with-button {
  padding-right: 4px;
}

.text-btn {
  height: 28px;
  border: 0;
  color: #c4d5eb;
  background: transparent;
}

.notice-list {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.notice-list li {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 3px;
  border-bottom: 1px solid rgba(102, 139, 184, 0.12);
  color: #d8e5f5;
  font-size: 13px;
}

.notice-list li:last-child {
  border-bottom: 0;
}

.notice-list time {
  color: #99a9bd;
  white-space: nowrap;
}

.bottom-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 12px;
  margin-top: 12px;
}

.donut-panel {
  min-height: 270px;
}

.donut-content {
  height: 210px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.donut {
  width: 134px;
  height: 134px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: conic-gradient(#48d86a 0 75%, #ffd326 75% 91.7%, #778392 91.7% 100%);
  box-shadow: 0 0 28px rgba(72, 216, 106, 0.12);
}

.donut::before {
  content: '';
  position: absolute;
  width: 82px;
  height: 82px;
  border-radius: 50%;
  background: #071322;
}

.donut span {
  position: relative;
  z-index: 1;
  color: #fff;
  font-size: 26px;
  font-weight: 900;
}

.legend {
  display: grid;
  gap: 12px;
}

.legend p {
  display: grid;
  grid-template-columns: 10px 44px minmax(72px, auto);
  gap: 8px;
  align-items: center;
  margin: 0;
  color: #c9d8ea;
  font-size: 12.5px;
  white-space: nowrap;
}

.legend strong {
  color: #dfeeff;
  font-weight: 500;
}

.company-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(86, 149, 219, 0.18);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.add-btn {
  border-color: rgba(76, 223, 102, 0.42);
  color: #9af7ae;
  background: rgba(35, 136, 68, 0.18);
}

.tab-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border: 1px solid rgba(42, 133, 227, 0.2);
  border-radius: 6px;
  background: rgba(3, 12, 26, 0.58);
}

.tab-row button {
  min-width: 96px;
  height: 32px;
  border: 0;
  border-radius: 4px;
  color: #b9c9df;
  background: transparent;
}

.search-box {
  width: 240px;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid rgba(42, 133, 227, 0.35);
  border-radius: 6px;
  background: rgba(3, 12, 26, 0.82);
}

.search-box input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  color: #eaf4ff;
  background: transparent;
  font-size: 12px;
}

.search-box input::placeholder {
  color: #6f8198;
}

.search-box span {
  color: #8ca0ba;
}

.member-table th,
.member-table td {
  height: 38px;
}

.member-table {
  border-color: rgba(70, 128, 194, 0.28);
  background: rgba(3, 12, 26, 0.4);
}

.member-table th {
  height: 34px;
  color: #9fb6d2;
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(180deg, rgba(25, 45, 72, 0.9), rgba(17, 33, 56, 0.82));
}

.member-table td {
  color: #cad8ea;
  background: rgba(5, 17, 34, 0.2);
}

.member-table tbody tr:nth-child(even) td {
  background: rgba(14, 29, 52, 0.16);
}

.member-table tbody tr:hover td {
  background: rgba(22, 131, 255, 0.09);
}

.member-table td:first-child {
  color: #ecf5ff;
  font-weight: 700;
}

.company-panel {
  overflow: hidden;
}

.company-panel .small-btn {
  min-width: 48px;
  height: 25px;
  margin-right: 4px;
  border-color: rgba(62, 125, 196, 0.38);
  color: #cfe0f6;
  background: rgba(10, 32, 61, 0.72);
}

.subpage-shell {
  display: grid;
  gap: 12px;
}

.subpage-hero {
  min-height: 112px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 22px;
  border-radius: 6px;
}

.subpage-kicker {
  margin: 0 0 8px;
  color: #1683ff;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.18em;
}

.subpage-hero h2 {
  margin: 0;
  color: #f4f8ff;
  font-size: 26px;
}

.subpage-hero span,
.subpage-note {
  color: #9fb2cb;
  font-size: 13px;
}

.subpage-panel {
  min-height: 520px;
  padding: 16px;
  border-radius: 6px;
}

.subpage-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(86, 149, 219, 0.18);
}

.subpage-toolbar h3 {
  margin: 0;
  color: #f1f7ff;
  font-size: 17px;
}

.search-box.wide {
  width: 300px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-grid div {
  min-height: 110px;
  display: grid;
  align-content: center;
  gap: 10px;
  padding: 18px;
  border: 1px solid rgba(42, 133, 227, 0.28);
  border-radius: 6px;
  background: rgba(3, 12, 26, 0.46);
}

.summary-grid span {
  color: #9fb2cb;
  font-size: 13px;
}

.summary-grid strong {
  color: #fff;
  font-size: 24px;
}

.page-list {
  padding: 0 4px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.settings-grid label {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid rgba(42, 133, 227, 0.28);
  border-radius: 6px;
  background: rgba(3, 12, 26, 0.46);
}

.settings-grid label span {
  color: #d6e2f2;
  font-size: 13px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 5, 14, 0.72);
}

.company-modal {
  width: min(720px, 100%);
  padding: 20px;
  border-radius: 8px;
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.modal-head h3 {
  margin: 0;
  color: #f4f8ff;
  font-size: 22px;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(42, 133, 227, 0.36);
  border-radius: 5px;
  color: #dce9f7;
  background: rgba(3, 12, 26, 0.72);
}

.modal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.modal-grid label {
  display: grid;
  gap: 8px;
}

.modal-grid span {
  color: #9fb2cb;
  font-size: 12px;
}

.modal-grid input,
.modal-grid select {
  width: 100%;
  height: 38px;
  padding: 0 11px;
  border: 1px solid rgba(42, 133, 227, 0.35);
  border-radius: 6px;
  color: #eaf4ff;
  background: rgba(3, 12, 26, 0.82);
}

.modal-message {
  margin: 14px 0 0;
  padding: 10px 12px;
  border: 1px solid rgba(255, 211, 38, 0.28);
  border-radius: 6px;
  color: #ffd326;
  background: rgba(255, 211, 38, 0.08);
  font-size: 13px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}

.modal-actions button:disabled {
  cursor: wait;
  opacity: 0.62;
}

.message {
  margin: 0 0 8px;
  color: #ffd326;
  font-size: 12px;
}

select {
  width: 170px;
  height: 28px;
  border: 1px solid rgba(42, 133, 227, 0.45);
  border-radius: 5px;
  color: #eaf4ff;
  background: #071322;
}

/* ===== Light mode ===== */
.master-shell.light {
  color: #203044;
  background:
    radial-gradient(circle at 14% 8%, rgba(22, 131, 255, 0.12), transparent 30%),
    radial-gradient(circle at 80% 86%, rgba(52, 211, 153, 0.10), transparent 30%),
    #eef5ff;
}

.master-shell.light .sidebar,
.master-shell.light .topbar {
  background: rgba(248, 251, 255, 0.88);
  border-color: rgba(38, 107, 186, 0.2);
  box-shadow: 0 14px 38px rgba(24, 57, 100, 0.08);
}

.master-shell.light .glass,
.master-shell.light .quick-menu,
.master-shell.light .company-modal {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.86), rgba(242, 248, 255, 0.72)),
    rgba(255, 255, 255, 0.72);
  border-color: rgba(38, 107, 186, 0.2);
  box-shadow: 0 16px 38px rgba(24, 57, 100, 0.09);
}

.master-shell.light .topbar-title strong,
.master-shell.light .sidebar-brand strong,
.master-shell.light .panel-title h2,
.master-shell.light .kpi strong,
.master-shell.light .total-number,
.master-shell.light .subpage-hero h2,
.master-shell.light .subpage-toolbar h3,
.master-shell.light .modal-head h3,
.master-shell.light .admin-chip,
.master-shell.light .clock,
.master-shell.light .system-state {
  color: #102033;
}

.master-shell.light .topbar-title span:not(.brand-diamond),
.master-shell.light .sidebar-brand span,
.master-shell.light .menu-group button,
.master-shell.light .submenu button,
.master-shell.light .kpi p,
.master-shell.light .panel-title span,
.master-shell.light .notice-list li,
.master-shell.light .legend-row,
.master-shell.light .subpage-note,
.master-shell.light .modal-grid span,
.master-shell.light .admin-chip small,
.master-shell.light .copyright {
  color: #526b88;
}

.master-shell.light .home-btn,
.master-shell.light .theme-btn,
.master-shell.light .logout-btn,
.master-shell.light .small-btn,
.master-shell.light .text-btn,
.master-shell.light .map-zoom button,
.master-shell.light .tab-row button,
.master-shell.light .quick-menu button,
.master-shell.light .action-btn {
  color: #24425f;
  background: linear-gradient(180deg, rgba(235, 243, 255, 0.95), rgba(220, 235, 255, 0.86));
  border-color: rgba(38, 107, 186, 0.24);
}

.master-shell.light .theme-btn {
  color: #05233d;
  background: linear-gradient(135deg, #ffffff, #dcecff);
  border-color: rgba(38, 107, 186, 0.42);
  box-shadow: 0 4px 14px rgba(24, 57, 100, 0.14);
}

.master-shell.light .control-table th {
  color: #55708d;
  background: rgba(227, 239, 255, 0.92);
}

.master-shell.light .control-table td,
.master-shell.light .control-table tbody tr {
  color: #223245;
  background: rgba(255, 255, 255, 0.52);
  border-color: rgba(38, 107, 186, 0.09);
}

.master-shell.light .control-table td:first-child,
.master-shell.light .member-table td:first-child,
.master-shell.light .notice-list li,
.master-shell.light .legend strong,
.master-shell.light .summary-grid strong,
.master-shell.light .settings-grid label span,
.master-shell.light .marker-label b {
  color: #102033;
}

.master-shell.light .status.ok,
.master-shell.light .ok,
.master-shell.light .map-marker.ok .marker-label small {
  color: #087a50;
}

.master-shell.light .status.caution,
.master-shell.light .caution,
.master-shell.light .map-marker.caution .marker-label small {
  color: #9a6700;
}

.master-shell.light .status.danger,
.master-shell.light .danger,
.master-shell.light .map-marker.danger .marker-label small {
  color: #b34b00;
}

.master-shell.light .member-table th {
  background: linear-gradient(180deg, rgba(229, 240, 255, 0.98), rgba(215, 232, 253, 0.92));
  color: #49637f;
}

.master-shell.light .member-table td,
.master-shell.light .member-table tbody tr:nth-child(even) td {
  color: #223245;
  background: rgba(255, 255, 255, 0.68);
}

.master-shell.light .member-table tbody tr:hover td,
.master-shell.light .control-table tbody tr:hover {
  background: rgba(22, 131, 255, 0.10);
}

.master-shell.light .state-summary,
.master-shell.light .summary-grid div,
.master-shell.light .settings-grid label,
.master-shell.light .tab-row {
  background: rgba(255, 255, 255, 0.76);
  border-color: rgba(38, 107, 186, 0.18);
}

.master-shell.light .donut::before {
  background: #f8fbff;
  box-shadow: inset 0 0 0 1px rgba(38, 107, 186, 0.10);
}

.master-shell.light .donut span {
  color: #102033;
}

.master-shell.light .state-summary div,
.master-shell.light .legend p,
.master-shell.light .notice-list time,
.master-shell.light .summary-grid span {
  color: #49637f;
}

.master-shell.light .search-box,
.master-shell.light .modal-grid input,
.master-shell.light .modal-grid select,
.master-shell.light select {
  color: #102033;
  background: #fff;
  border-color: rgba(38, 107, 186, 0.24);
}

.master-shell.light .map-panel::after {
  background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.18));
}

.master-shell.light .marker-label {
  background: rgba(255, 255, 255, 0.9);
  color: #102033;
  border-color: rgba(38, 107, 186, 0.28);
}

/* 라이트 모드 최종 대비 보정 */
.master-shell.light .sidebar *,
.master-shell.light .topbar *,
.master-shell.light .glass *,
.master-shell.light .company-modal * {
  text-shadow: none;
}

.master-shell.light .sidebar,
.master-shell.light .sidebar span,
.master-shell.light .sidebar button,
.master-shell.light .topbar,
.master-shell.light .topbar span,
.master-shell.light .topbar b,
.master-shell.light .glass,
.master-shell.light .glass p,
.master-shell.light .glass span,
.master-shell.light .glass strong,
.master-shell.light .glass em,
.master-shell.light .glass td,
.master-shell.light .glass th,
.master-shell.light .company-modal,
.master-shell.light .company-modal p,
.master-shell.light .company-modal span {
  color: #17283b;
}

.master-shell.light .sidebar-brand span,
.master-shell.light .menu-group button,
.master-shell.light .submenu button,
.master-shell.light .copyright,
.master-shell.light .kpi p,
.master-shell.light .panel-title span,
.master-shell.light .subpage-note,
.master-shell.light .notice-list time,
.master-shell.light .legend p,
.master-shell.light .summary-grid span,
.master-shell.light .modal-grid span {
  color: #425b78;
}

.master-shell.light button,
.master-shell.light .home-btn,
.master-shell.light .logout-btn,
.master-shell.light .small-btn,
.master-shell.light .text-btn,
.master-shell.light .map-edit-btn,
.master-shell.light .map-zoom button,
.master-shell.light .tab-row button,
.master-shell.light .quick-menu button {
  color: #12324f;
  background-color: rgba(239, 247, 255, 0.95);
}

.master-shell.light .small-btn:hover,
.master-shell.light .home-btn:hover,
.master-shell.light .logout-btn:hover,
.master-shell.light .tab-row button.active,
.master-shell.light .menu-group button.active,
.master-shell.light .submenu button.active {
  color: #063963;
  background: rgba(22, 131, 255, 0.14);
}

.master-shell.light .add-btn,
.master-shell.light .map-edit-btn.active {
  color: #066c47;
  background: rgba(31, 150, 93, 0.12);
}

.master-shell.light .kpi-icon,
.master-shell.light .brand-diamond,
.master-shell.light .theme-btn {
  color: #fff;
}

.master-shell.light .status,
.master-shell.light .marker-label,
.master-shell.light .state-summary {
  color: #17283b;
}

.master-shell.light .ok,
.master-shell.light .status.ok,
.master-shell.light .map-marker.ok .marker-label small,
.master-shell.light .system-state {
  color: #066c47;
}

.master-shell.light .caution,
.master-shell.light .status.caution,
.master-shell.light .map-marker.caution .marker-label small {
  color: #7a5200;
}

.master-shell.light .danger,
.master-shell.light .status.danger,
.master-shell.light .map-marker.danger .marker-label small {
  color: #a33b00;
}

@media (max-width: 1439px) {
  .master-shell {
    min-width: 1280px;
  }
}
</style>
