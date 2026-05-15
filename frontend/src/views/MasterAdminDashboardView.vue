<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { adminApi } from '@/api/admin'
import ChartJsPanel from '@/components/charts/ChartJsPanel.vue'

const router = useRouter()
const auth = useAuthStore()

const THEME_STORAGE_KEY = 'hifive.dashboard.theme'
const nowText = ref('')
const themeMode = ref(localStorage.getItem(THEME_STORAGE_KEY) || 'dark')
const activeMenu = ref('대시보드')
const activeTab = ref('companies')
const selectedCenter = ref('서울 톨게이트')
const expandedCenter = ref('')
const showCenterModal = ref(false)
const centerMetricPeriod = ref('daily')
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
const mapPositionDirty = ref(false)
const mapChangeCount = ref(0)
const mapEditSnapshot = ref([])
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
  { label: '시스템 관제', icon: '◉' },
  { label: 'Edge 장비', icon: '▣' },
  { label: 'Ingress', icon: '◎' },
  { label: '백엔드/DB', icon: '▤' },
  { label: '장애 알림', icon: '△' },
  { label: '지점 관리', icon: '▧' },
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

const dummyCompanies = [
  { name: '하이패스 서울(주)', owner: '김서울', phone: '02-1234-5678', email: 'seoul@hipass.com', centers: 5, status: '정상' },
  { name: '수원 하이패스(주)', owner: '이수원', phone: '031-234-5678', email: 'suwon@hipass.com', centers: 4, status: '정상' },
  { name: '대전 하이패스(주)', owner: '박대전', phone: '042-345-6789', email: 'daejeon@hipass.com', centers: 3, status: '주의' },
  { name: '대구 하이패스(주)', owner: '최대구', phone: '053-456-7890', email: 'daegu@hipass.com', centers: 4, status: '정상' },
  { name: '부산 하이패스(주)', owner: '정부산', phone: '051-567-8901', email: 'busan@hipass.com', centers: 6, status: '정상' },
  { name: '광주 스마트톨링(주)', owner: '윤광주', phone: '062-111-2200', email: 'gwangju@hipass.com', centers: 2, status: '정상' },
  { name: '강릉 톨링서비스(주)', owner: '한강릉', phone: '033-555-1900', email: 'gangneung@hipass.com', centers: 2, status: '정상' },
  { name: '제주 하이로드(주)', owner: '오제주', phone: '064-700-1200', email: 'jeju@hipass.com', centers: 1, status: '정상' },
  { name: '인천 스마트패스(주)', owner: '장인천', phone: '032-810-3300', email: 'incheon@hipass.com', centers: 3, status: '주의' },
  { name: '울산 하이패스(주)', owner: '문울산', phone: '052-420-7788', email: 'ulsan@hipass.com', centers: 2, status: '정상' },
  { name: '전주 톨링네트워크(주)', owner: '서전주', phone: '063-230-5588', email: 'jeonju@hipass.com', centers: 2, status: '비활성' },
  { name: '청주 교통관리(주)', owner: '남청주', phone: '043-610-4411', email: 'cheongju@hipass.com', centers: 2, status: '정상' }
]

const displayCompanies = computed(() => (companies.value.length >= 10 ? companies.value : dummyCompanies))

const filteredCompanies = computed(() => {
  const keyword = search.value.trim()
  return displayCompanies.value.filter((company) => !keyword || company.name.includes(keyword))
})

const filteredMembers = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return members.value.filter((member) => {
    return !keyword ||
      member.email?.toLowerCase().includes(keyword) ||
      member.memberName?.toLowerCase().includes(keyword)
  })
})

const chartGridColor = 'rgba(140, 176, 220, 0.14)'
const chartTextColor = '#aebfd4'

function lineData(values, color = '#38d778', fill = false) {
  return {
    labels: values.map((_, index) => index + 1),
    datasets: [{
      data: values,
      borderColor: color,
      backgroundColor: fill ? `${color}22` : 'transparent',
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 4,
      tension: 0.35,
      fill
    }]
  }
}

function multiLineData(series) {
  return {
    labels: ['16:35', '16:45', '16:55', '17:05', '17:15', '17:25', '17:35'],
    datasets: series.map((item) => ({
      label: item.label,
      data: item.values,
      borderColor: item.color,
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 4,
      tension: 0.35
    }))
  }
}

const sparklineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
  scales: { x: { display: false }, y: { display: false } }
}

const compactLineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: chartTextColor, font: { size: 10 } }, grid: { color: chartGridColor } },
    y: { ticks: { color: chartTextColor, font: { size: 10 } }, grid: { color: chartGridColor } }
  }
}

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '66%',
  plugins: { legend: { display: false } }
}

const dashboardSparklines = [
  lineData([16, 12, 14, 8, 10, 6, 9], '#38d778'),
  lineData([9, 11, 8, 12, 10, 13, 12], '#38d778'),
  lineData([15, 15, 11, 11, 8, 8, 6], '#38d778'),
  lineData([18, 15, 13, 10, 9, 7, 5], '#38d778'),
  lineData([17, 13, 14, 10, 8, 7, 6], '#38d778'),
  lineData([7, 9, 8, 12, 14, 13, 17], '#ffb928'),
  lineData([8, 9, 13, 11, 15, 14, 16], '#ffb928'),
  lineData([11, 12, 10, 9, 11, 8, 9], '#38d778'),
  lineData([13, 10, 12, 9, 8, 11, 7], '#38d778'),
  lineData([17, 13, 14, 11, 10, 8, 6], '#38d778'),
  lineData([14, 12, 13, 10, 12, 9, 10], '#38d778'),
  lineData([16, 14, 14, 11, 10, 8, 8], '#38d778'),
  lineData([15, 12, 13, 10, 9, 7, 8], '#38d778'),
  lineData([7, 8, 10, 13, 14, 16, 17], '#ffb928'),
  lineData([17, 15, 12, 14, 10, 8, 6], '#38d778')
]

const edgeFleetDoughnutData = {
  labels: ['Normal', 'Warning', 'Stale'],
  datasets: [{ data: [78, 7, 5], backgroundColor: ['#38d778', '#ffb928', '#ff635c'], borderWidth: 0 }]
}

const edgeMetricCharts = [
  { title: 'FPS', subtitle: '(frame/sec)', status: '정상', color: '#2f8cff', label: '평균 FPS', values: [28, 31, 27, 29, 31, 30, 33, 29] },
  { title: 'YOLO 처리 시간', subtitle: '(ms)', status: '정상', color: '#42d779', label: '평균 YOLO ms', values: [25, 27, 24, 29, 30, 32, 31, 28] },
  { title: 'OCR 처리 시간', subtitle: '(ms)', status: '주의', color: '#b28cff', label: '평균 OCR ms', values: [54, 64, 59, 62, 61, 60, 58, 63], warn: true },
  { title: 'Spool Count', subtitle: '(건)', status: '정상', color: '#ffb928', label: '현재 Spool', values: [72, 64, 70, 75, 73, 72, 69, 67] },
  { title: 'Sent Event Count', subtitle: '(건/분)', status: '정상', color: '#26c8e8', label: '전송 이벤트', values: [45, 43, 56, 62, 51, 44, 38, 42], total: '45,672 건' }
]

const ingressCharts = [
  { title: '수신 이벤트 (건)', data: lineData([6800, 7600, 8150, 7900, 8500, 9000, 9300], '#2f8cff') },
  { title: 'ACK / RETRY (건)', data: multiLineData([{ label: 'ACK', values: [6700, 7400, 7800, 8250, 8800, 9050, 9200], color: '#42d779' }, { label: 'RETRY', values: [210, 230, 260, 300, 350, 410, 480], color: '#ffb928' }]) },
  { title: 'REJECT / MALFORMED (건)', data: multiLineData([{ label: 'REJECT', values: [82, 96, 101, 112, 118, 130, 138], color: '#ff635c' }, { label: 'MALFORMED', values: [12, 13, 14, 15, 16, 17, 18], color: '#b28cff' }]) },
  { title: '현재 연결 수 (개)', data: lineData([190, 205, 210, 208, 206, 202, 200], '#26c8e8') }
]

const incidentTimelineData = {
  datasets: [
    { label: '치명', data: [{ x: 72, y: 5 }, { x: 66, y: 3 }], backgroundColor: '#ff635c', pointRadius: 6 },
    { label: '경고', data: [{ x: 28, y: 5 }, { x: 70, y: 4 }, { x: 52, y: 2 }, { x: 42, y: 1 }], backgroundColor: '#ffb928', pointRadius: 6 },
    { label: '정보', data: [{ x: 32, y: 4 }, { x: 23, y: 3 }, { x: 69, y: 1 }], backgroundColor: '#3d8cff', pointRadius: 6 },
    { label: '해제', data: [{ x: 92, y: 5 }, { x: 88, y: 4 }, { x: 92, y: 2 }, { x: 92, y: 1 }], backgroundColor: '#50d779', pointRadius: 6 }
  ]
}

const incidentTimelineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: { min: 0, max: 100, ticks: { display: false }, grid: { color: chartGridColor } },
    y: { min: 0.5, max: 5.5, ticks: { display: false }, grid: { color: chartGridColor } }
  }
}

const companyPermissionChartData = {
  labels: ['MASTER', 'ADMIN', 'OPERATOR', 'LOCKED'],
  datasets: [{ data: [1, 8, 26, 2], backgroundColor: ['#5ea8ff', '#38d778', '#ffb928', '#ff635c'], borderRadius: 6 }]
}

const companyPermissionChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: chartTextColor, font: { size: 10 } }, grid: { display: false } },
    y: { ticks: { display: false }, grid: { color: chartGridColor } }
  }
}

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

const recentAuditRows = [
  { time: '17:34:58', actor: 'admin', target: '서울도로공사 / 서울 톨게이트 A', reason: '장애 원인 확인', result: '성공' },
  { time: '17:29:33', actor: 'admin', target: '경기도로공사 / 수원 톨게이트 A', reason: '상태 점검', result: '성공' },
  { time: '17:24:11', actor: 'admin', target: '대전교통공사 / 대전 톨게이트 B', reason: '주의 상태 확인', result: '성공' },
  { time: '17:18:07', actor: 'operator02', target: '대구교통공사 / 대구 톨게이트 C', reason: '장애 처리 지원', result: '성공' },
  { time: '17:12:45', actor: 'admin', target: '부산운영공사 / 부산 톨게이트 D', reason: '장기 점검', result: '성공' }
]

const recentAlerts = [
  { level: '치명', tone: 'danger', title: '대구 톨게이트 C · 2번 레일 CCTV 수신 중단', time: '17:33:12' },
  { level: '경고', tone: 'caution', title: '대전 톨게이트 B · OCR Task Drop 증가', time: '17:31:05' },
  { level: '경고', tone: 'caution', title: '수원 톨게이트 A · Spool Count 85% 초과', time: '17:29:48' },
  { level: '정보', tone: 'info', title: '부산 톨게이트 D · LAN → LTE 경로 전환', time: '17:27:21' },
  { level: '정보', tone: 'info', title: 'Ingress · Retry 비율 일시 증가', time: '17:26:34' }
]

const companyByCenter = {
  '서울 톨게이트': '서울도로공사',
  '수원 톨게이트': '경기도로공사',
  '대전 톨게이트': '대전교통공사',
  '대구 톨게이트': '대구교통공사',
  '부산 톨게이트': '부산운영공사',
  '광주 톨게이트': '광주도로공사',
  '강릉 톨게이트': '강원도로공사',
  '제주 톨게이트': '제주교통공사'
}

const recentIssueByCenter = {
  '대전 톨게이트': '1건',
  '대구 톨게이트': '2건'
}

const centerDetailMeta = {
  '서울 톨게이트': {
    address: '서울특별시 서초구 양재대로 12',
    lat: '37.56668',
    lng: '126.97841',
    edgeCount: 3,
    metrics: {
      daily: { label: '일간', traffic: 12456, settlement: 2450800, bars: [42, 58, 74, 92, 86, 68, 54] },
      weekly: { label: '주간', traffic: 86420, settlement: 17155600, bars: [56, 68, 72, 88, 94, 80, 64] },
      monthly: { label: '월간', traffic: 358420, settlement: 71135800, bars: [48, 64, 79, 84, 91, 88, 76] }
    }
  },
  '수원 톨게이트': {
    address: '경기도 수원시 영통구 중부대로 88',
    lat: '37.26357',
    lng: '127.02860',
    edgeCount: 2,
    metrics: {
      daily: { label: '일간', traffic: 9876, settlement: 1896200, bars: [34, 44, 61, 78, 72, 62, 48] },
      weekly: { label: '주간', traffic: 68450, settlement: 13005500, bars: [45, 54, 66, 74, 82, 73, 58] },
      monthly: { label: '월간', traffic: 292380, settlement: 55552200, bars: [42, 58, 70, 76, 84, 79, 67] }
    }
  },
  '대전 톨게이트': {
    address: '대전광역시 유성구 북유성대로 154',
    lat: '36.35041',
    lng: '127.38455',
    edgeCount: 3,
    metrics: {
      daily: { label: '일간', traffic: 7654, settlement: 1454260, bars: [28, 38, 50, 68, 61, 47, 36] },
      weekly: { label: '주간', traffic: 52380, settlement: 9952200, bars: [38, 46, 59, 70, 66, 56, 44] },
      monthly: { label: '월간', traffic: 218700, settlement: 41553000, bars: [36, 49, 61, 73, 70, 63, 54] }
    }
  },
  '대구 톨게이트': {
    address: '대구광역시 동구 팔공로 221',
    lat: '35.87144',
    lng: '128.60144',
    edgeCount: 3,
    metrics: {
      daily: { label: '일간', traffic: 5321, settlement: 1010990, bars: [24, 32, 45, 54, 50, 41, 30] },
      weekly: { label: '주간', traffic: 38210, settlement: 7259900, bars: [31, 40, 52, 62, 58, 48, 37] },
      monthly: { label: '월간', traffic: 162400, settlement: 30856000, bars: [30, 43, 55, 66, 61, 53, 42] }
    }
  },
  '부산 톨게이트': {
    address: '부산광역시 금정구 중앙대로 2101',
    lat: '35.17955',
    lng: '129.07564',
    edgeCount: 2,
    metrics: {
      daily: { label: '일간', traffic: 11023, settlement: 2094370, bars: [38, 52, 67, 80, 88, 74, 59] },
      weekly: { label: '주간', traffic: 76230, settlement: 14483700, bars: [46, 58, 70, 84, 91, 79, 66] },
      monthly: { label: '월간', traffic: 321500, settlement: 61085000, bars: [43, 60, 76, 86, 92, 84, 72] }
    }
  },
  '광주 톨게이트': {
    address: '광주광역시 광산구 무진대로 303',
    lat: '35.15955',
    lng: '126.85260',
    edgeCount: 2,
    metrics: {
      daily: { label: '일간', traffic: 6120, settlement: 1162800, bars: [26, 36, 49, 61, 57, 44, 34] },
      weekly: { label: '주간', traffic: 42100, settlement: 7999000, bars: [34, 45, 56, 68, 63, 53, 41] },
      monthly: { label: '월간', traffic: 178300, settlement: 33877000, bars: [32, 47, 59, 70, 66, 58, 46] }
    }
  },
  '강릉 톨게이트': {
    address: '강원특별자치도 강릉시 경강로 2301',
    lat: '37.75185',
    lng: '128.87606',
    edgeCount: 2,
    metrics: {
      daily: { label: '일간', traffic: 4320, settlement: 820800, bars: [20, 30, 42, 53, 49, 38, 28] },
      weekly: { label: '주간', traffic: 30140, settlement: 5726600, bars: [28, 38, 49, 60, 56, 46, 35] },
      monthly: { label: '월간', traffic: 129900, settlement: 24681000, bars: [27, 41, 52, 64, 60, 50, 39] }
    }
  },
  '제주 톨게이트': {
    address: '제주특별자치도 제주시 공항로 2',
    lat: '33.49962',
    lng: '126.53119',
    edgeCount: 1,
    metrics: {
      daily: { label: '일간', traffic: 2210, settlement: 419900, bars: [16, 22, 31, 44, 40, 30, 23] },
      weekly: { label: '주간', traffic: 15980, settlement: 3036200, bars: [24, 31, 43, 54, 50, 39, 30] },
      monthly: { label: '월간', traffic: 68420, settlement: 12999800, bars: [22, 36, 48, 58, 54, 44, 34] }
    }
  }
}

const selectedCenterDetail = computed(() => {
  const center = centers.value.find((item) => item.name === selectedCenter.value) ?? centers.value[0]
  const meta = centerDetailMeta[center.name] ?? centerDetailMeta['서울 톨게이트']
  const metric = meta.metrics[centerMetricPeriod.value] ?? meta.metrics.daily
  return { ...center, ...meta, metric }
})

function centerOwner(centerName) {
  return companyByCenter[centerName] ?? '담당 회원사'
}

function centerIssueCount(centerName) {
  return recentIssueByCenter[centerName] ?? '0건'
}

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

function createMapMarkerSnapshot() {
  return centers.value.map(({ name, x, y, labelX, labelY }) => ({
    name,
    x,
    y,
    labelX,
    labelY
  }))
}

async function saveMapMarkerPositions() {
  if (!mapPositionDirty.value) return

  const markerPositions = createMapMarkerSnapshot()
  localStorage.setItem(MAP_MARKER_STORAGE_KEY, JSON.stringify(markerPositions))

  try {
    await adminApi.saveMapMarkers(markerPositions)
    mapPositionDirty.value = false
    mapChangeCount.value = 0
    mapEditSnapshot.value = createMapMarkerSnapshot()
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
  router.push({ path: '/dashboard', query: { center: center.dashboardId } })
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
  activateMenu('지점 관리')
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
  if (!isMapEditMode.value) {
    mapEditSnapshot.value = createMapMarkerSnapshot()
    mapPositionDirty.value = false
    mapChangeCount.value = 0
    isMapEditMode.value = true
  } else {
    isMapEditMode.value = false
  }
  draggingCenterName.value = ''
  draggingLabelName.value = ''
}

function resetMapEditPositions() {
  applyMapMarkerPositions(mapEditSnapshot.value)
  mapPositionDirty.value = false
  mapChangeCount.value = 0
  draggingCenterName.value = ''
  draggingLabelName.value = ''
}

function cancelMapEditMode() {
  resetMapEditPositions()
  isMapEditMode.value = false
}

function toggleCenterDetail(center) {
  if (isMapEditMode.value) return
  selectedCenter.value = center.name
  centerMetricPeriod.value = 'daily'
  showCenterModal.value = true
}

function markMapDirty() {
  if (!mapPositionDirty.value) {
    mapChangeCount.value += 1
  }
  mapPositionDirty.value = true
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
  const nextX = Number(Math.min(96, Math.max(4, x)).toFixed(1))
  const nextY = Number(Math.min(96, Math.max(4, y)).toFixed(1))
  if (center.x !== nextX || center.y !== nextY) {
    center.x = nextX
    center.y = nextY
    markMapDirty()
  }
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

  const nextLabelX = Number(Math.min(180, Math.max(-180, pointerX - markerX)).toFixed(0))
  const nextLabelY = Number(Math.min(90, Math.max(-90, pointerY - markerY)).toFixed(0))
  if (center.labelX !== nextLabelX || center.labelY !== nextLabelY) {
    center.labelX = nextLabelX
    center.labelY = nextLabelY
    markMapDirty()
  }
}

function stopMarkerDrag() {
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
          <span>MASTER<br />Master Admin Console</span>
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
        <button type="button" @click="openNoticeCreate">점검 공지</button>
        <button type="button" @click="activateMenu('장애 알림')">장애 등록</button>
      </div>

      <p class="copyright">© 2025 HI-FIVE All rights reserved.</p>
    </aside>

    <div class="content-shell">
      <header class="topbar">
        <div class="topbar-title">
          <span class="brand-diamond small"></span>
          <strong>{{ activeMenu === 'Ingress' ? 'Ingress 관제' : activeMenu === '시스템 관제' ? 'Master Admin · 시스템 관제' : activeMenu === 'Edge 장비' ? 'Edge 장비 관제' : activeMenu === '백엔드/DB' ? 'Backend / DB 관제' : activeMenu === '장애 알림' ? '장애 알림' : activeMenu === '지점 관리' ? '지점 관리' : activeMenu === '감사 로그' ? '감사 로그' : activeMenu === '설정' ? '설정' : ['회원사 관리', '회원사 목록'].includes(activeMenu) ? '회원사 관리' : 'HI-FIVE' }}</strong>
          <span>{{ activeMenu === 'Ingress' ? 'Python Ingress 서비스 상태 및 이벤트 흐름을 모니터링합니다.' : activeMenu === 'Edge 장비' ? 'Jetson Edge 장비 상태 및 성능 모니터링' : activeMenu === '장애 알림' ? '시스템 및 서비스 이상 상황을 모니터링하고 대응합니다.' : activeMenu === '지점 관리' ? '스마트 톨링 지점 및 제어센터 등록/수정/관리' : activeMenu === '감사 로그' ? '관리자 작업, 권한 변경, 대리조회 이력을 추적합니다.' : activeMenu === '설정' ? '관리자 콘솔 운영 정책과 시스템 기본값을 관리합니다.' : ['회원사 관리', '회원사 목록'].includes(activeMenu) ? '회원사 계정, 권한, 지점 연결 상태를 통합 관리합니다.' : activeMenu === '시스템 관제' || activeMenu === '백엔드/DB' ? '' : 'Master Admin Dashboard' }}</span>
        </div>

        <div class="header-tools">
          <span class="clock">{{ nowText }}</span>
          <span class="system-state global-ok"><i></i>전체 정상</span>
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
        <section ref="kpiSection" class="kpi-grid master-kpi-grid">
          <article class="kpi glass violet">
            <span class="kpi-icon">👥</span>
            <div>
              <p>전체 회원사</p>
              <strong>24</strong>
              <em>전일 대비 ▲ 2</em>
            </div>
          </article>
          <article class="kpi glass blue">
            <span class="kpi-icon">●</span>
            <div>
              <p>전체 지점</p>
              <strong>38</strong>
              <em>전일 대비 ▲ 1</em>
            </div>
          </article>
          <article class="kpi glass green">
            <span class="kpi-icon">✓</span>
            <div>
              <p>정상 지점</p>
              <strong>32</strong>
              <em>정상 비율 84.2%</em>
            </div>
          </article>
          <article class="kpi glass yellow">
            <span class="kpi-icon">!</span>
            <div>
              <p>주의/장애</p>
              <strong>6</strong>
              <em class="down">주의 4 / 장애 2</em>
            </div>
          </article>
          <article class="kpi glass cyan">
            <span class="kpi-icon">▣</span>
            <div>
              <p>시스템 상태</p>
              <strong>정상</strong>
              <em>모든 시스템 정상 운영 중</em>
            </div>
          </article>
        </section>

        <section class="dashboard-grid master-overview-grid">
          <article ref="mapSection" class="map-panel glass">
            <div class="panel-title map-title">
              <h2>전국 지점 위치 현황</h2>
              <div class="map-actions">
                <button
                  class="map-edit-btn"
                  :class="{ active: isMapEditMode }"
                  type="button"
                  @click="toggleMapEditMode"
                >
                  {{ isMapEditMode ? '편집 완료' : '위치 편집' }}
                </button>
                <button
                  v-if="isMapEditMode"
                  class="map-edit-btn ghost save"
                  type="button"
                  :disabled="!mapPositionDirty"
                  @click="saveMapMarkerPositions"
                >
                  변경사항 저장
                </button>
                <button
                  v-if="isMapEditMode"
                  class="map-edit-btn ghost"
                  type="button"
                  @click="resetMapEditPositions"
                >
                  위치 초기화
                </button>
                <button
                  v-if="isMapEditMode"
                  class="map-edit-btn ghost danger"
                  type="button"
                  @click="cancelMapEditMode"
                >
                  편집 취소
                </button>
                <span v-if="isMapEditMode" class="active">편집 모드</span>
              </div>
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
                  @click="toggleCenterDetail(center)"
                  @pointerdown="startMarkerDrag($event, center)"
                ></button>
                <button
                  class="marker-label"
                  type="button"
                  :style="{ transform: `translate(${center.labelX}px, ${center.labelY}px)` }"
                  :title="isMapEditMode ? '명칭 박스 위치 이동' : center.name"
                  @click="toggleCenterDetail(center)"
                  @pointerdown="startLabelDrag($event, center)"
                >
                  <b>{{ center.name }}</b>
                  <small>{{ statusText(center.status) }}</small>
                </button>
              </div>

            </div>
          </article>

          <aside class="right-column">
            <article class="panel glass dashboard-pipeline-panel">
              <div class="panel-title">
                <h2>시스템 파이프라인 상태</h2>
              </div>

              <table class="dashboard-pipeline-table">
                <tbody>
                  <tr>
                    <td rowspan="3" class="pipeline-table-icon">▣</td>
                    <td rowspan="3" class="pipeline-table-name">Edge</td>
                    <td>FPS</td>
                    <td>29.8</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[0]" :options="sparklineOptions" :height="22" /></td>
                    <td rowspan="3" class="pipeline-table-state"><b>정상 장비 : 78</b><span>State 5</span></td>
                  </tr>
                  <tr>
                    <td>Spool</td>
                    <td>12</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[1]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td>Active Path</td>
                    <td>LAN</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[2]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td rowspan="3" class="pipeline-table-icon">▤</td>
                    <td rowspan="3" class="pipeline-table-name">Ingress</td>
                    <td>수신 이벤트</td>
                    <td>128,456건</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[3]" :options="sparklineOptions" :height="22" /></td>
                    <td rowspan="3" class="pipeline-table-state"><b>연결 상태 정상</b><span>RETRY 1,208</span></td>
                  </tr>
                  <tr>
                    <td>ACK</td>
                    <td>126,842건</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[4]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td>RETRY</td>
                    <td>1,208건</td>
                    <td class="pipeline-spark warn"><ChartJsPanel type="line" :data="dashboardSparklines[5]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td rowspan="3" class="pipeline-table-icon">◒</td>
                    <td rowspan="3" class="pipeline-table-name">Backend</td>
                    <td>Validation 실패</td>
                    <td>0.18%</td>
                    <td class="pipeline-spark warn"><ChartJsPanel type="line" :data="dashboardSparklines[6]" :options="sparklineOptions" :height="22" /></td>
                    <td rowspan="3" class="pipeline-table-state"><b>API 상태 정상</b><span>p95 128ms</span></td>
                  </tr>
                  <tr>
                    <td>Duplicate 차단</td>
                    <td>1,284건</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[7]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td>API Latency</td>
                    <td>128 ms</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[8]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td rowspan="3" class="pipeline-table-icon">◉</td>
                    <td rowspan="3" class="pipeline-table-name">DB</td>
                    <td>Write TPS</td>
                    <td>412</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[9]" :options="sparklineOptions" :height="22" /></td>
                    <td rowspan="3" class="pipeline-table-state"><b>복제 지연 0.2초</b><span>Backup 정상</span></td>
                  </tr>
                  <tr>
                    <td>Read TPS</td>
                    <td>256</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[10]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td>Backup 상태</td>
                    <td>정상</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[11]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td rowspan="3" class="pipeline-table-icon">V</td>
                    <td rowspan="3" class="pipeline-table-name">API</td>
                    <td>응답 시간</td>
                    <td>145 ms</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[12]" :options="sparklineOptions" :height="22" /></td>
                    <td rowspan="3" class="pipeline-table-state"><b>API 상태 정상</b><span>1,284 rpm</span></td>
                  </tr>
                  <tr>
                    <td>오류율</td>
                    <td>0.02%</td>
                    <td class="pipeline-spark warn"><ChartJsPanel type="line" :data="dashboardSparklines[13]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                  <tr>
                    <td>요청 처리량</td>
                    <td>1,284 rpm</td>
                    <td class="pipeline-spark"><ChartJsPanel type="line" :data="dashboardSparklines[14]" :options="sparklineOptions" :height="22" /></td>
                  </tr>
                </tbody>
              </table>
            </article>
          </aside>

          <section ref="companySection" class="dashboard-lower-panels">
            <article ref="noticeSection" class="panel glass notice-panel">
              <div class="panel-title with-button">
                <h2>시스템 공지사항</h2>
                <button class="text-btn" type="button" @click="showMoreNotices">전체 보기 ›</button>
              </div>
              <ul class="notice-list">
                <li v-for="notice in notices" :key="notice.title">
                  <span>{{ notice.title }}</span>
                  <time>{{ notice.date }}</time>
                </li>
              </ul>
            </article>

            <article class="panel glass alert-panel">
              <div class="panel-title with-button">
                <h2>최근 장애 알림</h2>
                <button class="text-btn" type="button" @click="activateMenu('장애 알림')">전체 보기 ›</button>
              </div>
              <ul class="alert-list">
                <li v-for="alert in recentAlerts" :key="`${alert.time}-${alert.title}`">
                  <b :class="alert.tone">{{ alert.level }}</b>
                  <span>{{ alert.title }}</span>
                  <time>{{ alert.time }}</time>
                </li>
              </ul>
            </article>
          </section>
        </section>
        </template>

        <section v-else class="subpage-shell">
          <article v-if="!['Ingress', '시스템 관제', 'Edge 장비', '백엔드/DB', '장애 알림', '지점 관리', '감사 로그', '설정', '회원사 관리', '회원사 목록'].includes(activeMenu)" class="panel glass subpage-hero">
            <div>
              <p class="subpage-kicker">MASTER ADMIN</p>
              <h2>{{ subpageTitle }}</h2>
              <span>{{ subpageDescription }}</span>
            </div>
            <button class="home-btn" type="button" @click="activeMenu = '대시보드'">대시보드로 이동</button>
          </article>

          <article v-if="['회원사 관리', '회원사 목록'].includes(activeMenu)" class="company-admin-page">
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
                      <td><b>{{ company.name }}</b><small>{{ index === 0 ? '서울/수도권 운영사' : '스마트 톨링 회원사' }}</small></td>
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
                <div>
                  <span><b>MASTER</b><strong>1</strong></span>
                  <span><b>ADMIN</b><strong>8</strong></span>
                  <span><b>OPERATOR</b><strong>26</strong></span>
                  <span><b>LOCKED</b><strong>2</strong></span>
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

          <article v-else-if="['지점(관제센터) 관리', '지점 관리'].includes(activeMenu)" class="branch-page">
            <section class="branch-filter-row">
              <label><span>회원사</span><button class="filter-toggle" type="button">전체 회원사</button></label>
              <label><span>지역</span><button class="filter-toggle" type="button">전체 지역</button></label>
              <label><span>상태</span><button class="filter-toggle" type="button">전체 상태</button></label>
              <label class="branch-search"><input type="search" placeholder="지점명 또는 주소 검색" /><span>⌕</span></label>
              <button class="branch-reset" type="button">필터 초기화</button>
            </section>

            <section class="branch-main-grid">
              <article class="branch-panel branch-map-panel">
                <div class="branch-panel-head">
                  <h3>전국 지점 위치</h3>
                  <div class="branch-map-actions">
                    <button class="primary" type="button">위치 편집</button>
                    <button class="success" type="button">GPS 영역 설정</button>
                    <button type="button">초기화</button>
                  </div>
                </div>
                <div class="branch-map-stage">
                  <div class="branch-map-legend top"><span class="ok">정상 28</span><span class="warn">점검중 3</span><span class="info">장애 2</span></div>
                  <div class="branch-zoom"><button>◎</button><button>＋</button><button>－</button></div>
                  <span class="branch-map-marker ok" style="left:38%;top:32%"><i></i><b>서울 톨게이트</b></span>
                  <span class="branch-map-marker ok" style="left:37%;top:43%"><i></i><b>수원 톨게이트</b></span>
                  <span class="branch-map-marker warn" style="left:47%;top:63%"><i></i><b>대전 톨게이트</b></span>
                  <span class="branch-map-marker danger" style="left:66%;top:59%"><i></i><b>대구 톨게이트</b></span>
                  <span class="branch-map-marker ok" style="left:73%;top:73%"><i></i><b>부산 톨게이트</b></span>
                  <span class="branch-map-marker ok" style="left:34%;top:75%"><i></i><b>광주 톨게이트</b></span>
                  <span class="branch-map-marker ok" style="left:59%;top:24%"><i></i><b>강릉 톨게이트</b></span>
                  <span class="branch-map-marker ok" style="left:47%;top:91%"><i></i><b>제주 톨게이트</b></span>
                  <div class="branch-map-legend bottom"><span class="ok">정상</span><span class="warn">주의</span><span class="caution">점검중</span><span class="danger">장애</span></div>
                </div>
              </article>

              <aside class="branch-side-stack">
                <article class="branch-panel branch-detail">
                  <div class="branch-panel-head"><h3>선택 지점 상세 정보</h3><span class="branch-badge ok">정상</span></div>
                  <dl>
                    <dt>지점명</dt><dd>서울 톨링 A · 제어센터</dd>
                    <dt>담당 회원사</dt><dd>서울고속도로(주)</dd>
                    <dt>주소</dt><dd>경기도 성남시 분당구 판교로 255번길 9</dd>
                    <dt>지점 유형</dt><dd>제어센터 / 톨링 게이트</dd>
                    <dt>Edge 장비</dt><dd>3대 <code>wss://seoul-a-ingress.hi-five.kr</code></dd>
                    <dt>운영 상태</dt><dd><span class="branch-badge ok">정상 운영</span></dd>
                    <dt>마지막 변경자</dt><dd><b>admin</b> <small>(2025-05-11 17:33:12)</small></dd>
                  </dl>
                </article>

                <article class="branch-panel gps-zone-card">
                  <div class="branch-panel-head"><h3>GPS 결제 영역 설정 <small>(직사각형 영역)</small></h3><button class="primary">편집</button></div>
                  <div class="gps-zone-body">
                    <div class="gps-zone-map"><span>N</span><span>W</span><span>E</span><span>S</span><i></i><b></b></div>
                    <dl>
                      <dt>중심 좌표 (LAT, LNG)</dt><dd>37.4910401, 126.7251320</dd>
                      <dt>영역 폭</dt><dd>120.0 m</dd>
                      <dt>영역 높이</dt><dd>80.0 m</dd>
                      <dt>방향 기준</dt><dd>도로 진행 방향 기준</dd>
                      <dt>IN/OUT 기준</dt><dd>IN: 진입, OUT: 출구</dd>
                    </dl>
                  </div>
                </article>

                <article class="branch-panel branch-devices">
                  <h3>연결 장비 목록 (3)</h3>
                  <table class="branch-table">
                    <thead><tr><th>Jetson ID</th><th>카메라 레일</th><th>Active Path</th><th>상태</th><th>Stale</th></tr></thead>
                    <tbody>
                      <tr><td>JETSON-27</td><td>1번 레일 (IN)</td><td>LAN</td><td><span class="branch-badge ok">정상</span></td><td>5초 전</td></tr>
                      <tr><td>JETSON-28</td><td>2번 레일 (OUT)</td><td>LAN</td><td><span class="branch-badge ok">정상</span></td><td>8초 전</td></tr>
                      <tr><td>JETSON-29</td><td>후면 레일 (OUT)</td><td>LTE (백업)</td><td><span class="branch-badge warn">주의</span></td><td>28초 전</td></tr>
                    </tbody>
                  </table>
                </article>
              </aside>
            </section>

            <article class="branch-panel branch-history">
              <h3>지점/설정 변경 이력 <small>(최근 6건)</small></h3>
              <table class="branch-table">
                <thead><tr><th>변경시각</th><th>관리자</th><th>변경 항목</th><th>이전 값</th><th>변경 값</th><th>사유</th></tr></thead>
                <tbody>
                  <tr><td>2025-05-11 17:33:12</td><td>admin</td><td>지점 위치 (LAT, LNG)</td><td>37.4910322, 126.7251241</td><td>37.4910401, 126.7251320</td><td>정밀 위치 보정</td></tr>
                  <tr><td>2025-05-11 16:15:47</td><td>admin</td><td>GPS 영역 폭</td><td>110.0 m</td><td>120.0 m</td><td>진입 차로 확인 반영</td></tr>
                  <tr><td>2025-05-10 14:22:05</td><td>operator02</td><td>Edge 장비 추가</td><td>2대</td><td>3대 (JETSON-29 추가)</td><td>후면 레일 장비 설치</td></tr>
                  <tr><td>2025-05-09 11:08:33</td><td>admin</td><td>Ingress Endpoint</td><td>wss://old-ingress.hi-five.kr</td><td>wss://seoul-a-ingress.hi-five.kr</td><td>Ingress 주소 변경</td></tr>
                  <tr><td>2025-05-08 15:44:12</td><td>admin</td><td>GPS 영역 높이</td><td>70.0 m</td><td>80.0 m</td><td>출구 차로 포지션 조정</td></tr>
                  <tr><td>2025-05-07 09:17:28</td><td>operator01</td><td>지점 상태 변경</td><td>주의</td><td>정상</td><td>장애 조치 완료</td></tr>
                </tbody>
              </table>
              <button type="button">전체 변경 이력 보기 →</button>
            </article>
          </article>

          <article v-else-if="activeMenu === 'Edge 장비'" class="edge-page">
            <section class="edge-main-grid">
              <article class="edge-panel edge-list-panel">
                <h3>Edge 장비 목록 <small>(42대)</small></h3>
                <div class="edge-filter-row">
                  <button class="filter-toggle" type="button">지점 전체</button><button class="filter-toggle" type="button">Alive 전체</button><button class="filter-toggle" type="button">Source 전체</button><button class="filter-toggle" type="button">Path 전체</button><button class="filter-toggle" type="button">Stale 전체</button>
                  <label><input type="search" placeholder="장비 ID 검색..." /><span>⌕</span></label>
                  <button type="button">필터 초기화</button>
                </div>
                <table class="edge-table">
                  <thead><tr><th></th><th>장비 ID</th><th>지점</th><th>Alive</th><th>Source</th><th>입력 Source</th><th>FPS</th><th>YOLO ms</th><th>OCR ms</th><th>Spool</th><th>Path</th><th>Stale</th><th>최근 오류</th></tr></thead>
                  <tbody>
                    <tr class="selected"><td><span class="radio on"></span></td><td>JETSON-27</td><td>서울 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge ok">Running</b></td><td>CAM-01 (L1)</td><td>29.8</td><td>18.6</td><td>42.3</td><td>12</td><td><b class="edge-badge path">LAN</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-12</td><td>수원 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge ok">Running</b></td><td>CAM-02 (L2)</td><td>29.6</td><td>18.9</td><td>41.0</td><td>8</td><td><b class="edge-badge path">LAN</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-08</td><td>대전 톨링 B</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge ok">Running</b></td><td>CAM-01 (L1)</td><td>29.7</td><td>19.2</td><td>43.1</td><td>5</td><td><b class="edge-badge warn">LTE</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-34</td><td>부산 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge idle">Idle</b></td><td>-</td><td>0.0</td><td>0.0</td><td>0.0</td><td>0</td><td><b class="edge-badge path">LAN</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-15</td><td>광주 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge ok">Running</b></td><td>CAM-01 (L1)</td><td>29.4</td><td>20.1</td><td>44.5</td><td>14</td><td><b class="edge-badge path">LAN</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-05</td><td>대구 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge ok">Running</b></td><td>CAM-02 (L2)</td><td>29.5</td><td>18.5</td><td>40.7</td><td>6</td><td><b class="edge-badge warn">LTE</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-19</td><td>인천 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge ok">Running</b></td><td>CAM-01 (L1)</td><td>29.3</td><td>19.0</td><td>41.8</td><td>9</td><td><b class="edge-badge path">LAN</b></td><td><b class="edge-badge warn">10분</b></td><td>-</td></tr>
                    <tr><td><span class="radio"></span></td><td>JETSON-21</td><td>울산 톨링 A</td><td><b class="edge-badge ok">Alive</b></td><td><b class="edge-badge idle">Idle</b></td><td>-</td><td>0.0</td><td>0.0</td><td>0.0</td><td>0</td><td><b class="edge-badge path">LAN</b></td><td><b class="edge-badge ok">정상</b></td><td>-</td></tr>
                  </tbody>
                </table>
                <footer class="edge-pagination"><span>1-8 / 42대</span><div><button>‹</button><button class="active">1</button><button>2</button><button>3</button><button>4</button><button>5</button><button>…</button><button>6</button><button>›</button></div><button class="filter-toggle">8개씩 보기</button></footer>
              </article>

              <article class="edge-panel edge-detail-panel">
                <div class="edge-detail-head"><h3>JETSON-27 상세</h3><span>● Alive</span></div>
                <dl class="edge-detail-list">
                  <dt>지점</dt><dd>서울 톨링 A</dd><dt>차선</dt><dd>1번 레일 (L1)</dd><dt>현재 입력 Source</dt><dd>CAM-01 (L1)</dd><dt>마지막 상태 갱신</dt><dd>2025-05-11 17:36:47 (2초 전)</dd><dt>Jetson 상태 State</dt><dd class="ok">정상 (2분 미만)</dd>
                </dl>
                <h4>실시간 상태 요약</h4>
                <div class="edge-live-grid">
                  <div><i>▧</i><span>Processed Frames</span><strong>12,842,321 프레임</strong></div><div><i>◉</i><span>Spool Count</span><strong>12 건</strong></div><div><i>⌘</i><span>OCR Task Count</span><strong>582,411 건</strong></div><div><i>⌁</i><span>Active Path</span><strong>LAN</strong></div><div><i>×</i><span>Dropped OCR Task</span><strong class="danger">1,274 건</strong></div><div><i>◷</i><span>Uptime</span><strong>12일 04:32:11</strong></div><div><i>＋</i><span>Sent Event Count</span><strong>45,672 건</strong></div><div><i>!</i><span>최근 오류</span><strong>-</strong></div>
                </div>
                <section class="edge-recent-error"><h4>최근 오류 <small>(최근 1건)</small></h4><p>- 오류 없음 -</p></section>
                <footer class="edge-actions"><button>원격 재시작</button><button>로그 보기</button><button>상태 이력</button></footer>
              </article>
            </section>

            <section class="edge-chart-row">
              <article v-for="chart in edgeMetricCharts" :key="chart.title" class="edge-panel metric-chart">
                <h3>{{ chart.title }} <small>{{ chart.subtitle }}</small></h3>
                <b :class="{ warn: chart.warn }">{{ chart.status }}</b>
                <strong v-if="chart.total">{{ chart.total }}</strong>
                <ChartJsPanel type="line" :data="lineData(chart.values, chart.color)" :options="compactLineOptions" :height="128" />
                <span>{{ chart.label }}</span>
              </article>
            </section>
          </article>

          <article v-else-if="['단말기 관리'].includes(activeMenu)" class="panel glass subpage-panel">
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

          <article v-else-if="activeMenu === '시스템 관제'" class="system-control-page">
            <section class="system-kpi-grid">
              <article class="system-kpi"><i>▣</i><div><span>전체 Edge</span><strong>86 <em>대</em></strong><small>전체 등록</small></div></article>
              <article class="system-kpi ok"><i>✓</i><div><span>정상 Edge</span><strong>78 <em>대</em></strong><small>정상 비율 90.7%</small></div></article>
              <article class="system-kpi ok"><i>▤</i><div><span>Ingress 상태</span><strong>정상</strong><small>Uptime 12일 04:32</small></div></article>
              <article class="system-kpi ok"><i>◒</i><div><span>Backend 상태</span><strong>정상</strong><small>Uptime 8일 11:18</small></div></article>
              <article class="system-kpi ok"><i>◉</i><div><span>DB 상태</span><strong>정상</strong><small>복제 지연 0.2초</small></div></article>
              <article class="system-kpi danger"><i>!</i><div><span>최근 장애</span><strong>2 <em>건</em></strong><small>최근 24시간</small></div></article>
            </section>

            <article class="system-panel pipeline-panel">
              <h3>시스템 파이프라인 상태 <small>ⓘ</small></h3>
              <div class="pipeline-flow">
                <section class="pipeline-node">
                  <i>▣</i><h4>Jetson Edge</h4><b>정상 운영</b>
                  <dl><dt>FPS</dt><dd>29.8</dd><dt>Spool</dt><dd>12</dd><dt>Active Path</dt><dd>LAN</dd></dl>
                  <p><span></span>정상 장비 78 / Stale 5</p>
                </section>
                <section class="pipeline-node">
                  <i>▤</i><h4>Python Ingress</h4><b>정상 운영</b>
                  <dl><dt>수신 이벤트</dt><dd>128,456건</dd><dt>ACK</dt><dd>126,842건</dd><dt>RETRY</dt><dd>1,208건</dd></dl>
                  <p><span></span>연결 상태 정상</p>
                </section>
                <section class="pipeline-node">
                  <i>◒</i><h4>Spring Boot Backend</h4><b>정상 운영</b>
                  <dl><dt>Validation 실패</dt><dd>0.18%</dd><dt>Duplicate 차단</dt><dd>1,284건</dd><dt>API Latency (p95)</dt><dd>128 ms</dd></dl>
                  <p><span></span>API 상태 정상</p>
                </section>
                <section class="pipeline-node">
                  <i>◉</i><h4>PostgreSQL / DB</h4><b>정상 운영</b>
                  <dl><dt>Write TPS</dt><dd>412</dd><dt>Read TPS</dt><dd>256</dd><dt>Backup 상태</dt><dd>정상</dd></dl>
                  <p><span></span>복제 지연 0.2초</p>
                </section>
                <section class="pipeline-node">
                  <i>V</i><h4>Dashboard API</h4><b>정상 운영</b>
                  <dl><dt>응답 시간 (p95)</dt><dd>145 ms</dd><dt>오류율</dt><dd>0.02%</dd><dt>요청 처리량</dt><dd>1,284 rpm</dd></dl>
                  <p><span></span>API 상태 정상</p>
                </section>
              </div>
            </article>

            <section class="system-summary-grid">
              <article class="system-panel edge-summary">
                <div class="system-panel-title"><h3>Edge Fleet 요약</h3><button type="button">전체 Edge 보기 ›</button></div>
                <div class="edge-metrics">
                  <div><i>⌛</i><span>Stale 장비</span><strong>5 <em>대</em></strong><small>5.8%</small></div>
                  <div><i>▰</i><span>Source Running</span><strong>73 <em>대</em></strong><small>84.9%</small></div>
                  <div><i>Ⅱ</i><span>Source Idle</span><strong>10 <em>대</em></strong><small>11.6%</small></div>
                  <div><i>▤</i><span>OCR Drop 비</span><strong>0.12%</strong><small>정상 범위</small></div>
                  <div><i>⌘</i><span>Active Path - LAN</span><strong>72 <em>대</em></strong><small>83.7%</small></div>
                  <div><i>⌁</i><span>Active Path - LTE</span><strong>14 <em>대</em></strong><small>16.3%</small></div>
                </div>
                <div class="donut-wrap">
                  <h4>Edge 상태 분포</h4>
                  <div class="system-donut system-donut-chart"><ChartJsPanel type="doughnut" :data="edgeFleetDoughnutData" :options="doughnutOptions" :height="138" /><div class="system-donut-center"><strong>86</strong><span>?</span></div></div>
                  <ul>
                    <li><b class="ok"></b>정상 78 (90.7%)</li>
                    <li><b class="warn"></b>주의 7 (8.1%)</li>
                    <li><b class="danger"></b>Stale 5 (5.8%)</li>
                  </ul>
                </div>
              </article>

              <article class="system-panel ingress-summary">
                <div class="system-panel-title"><h3>Ingress 요약</h3><button type="button">상세 보기 ›</button></div>
                <div class="ingress-mini-grid">
                  <div><i>▥</i><span>수신 이벤트</span><strong>128,456건</strong><small>최근 1시간</small></div>
                  <div><i>✓</i><span>ACK</span><strong>128,842건</strong><small>성공률 98.7%</small></div>
                  <div><i>↻</i><span>RETRY</span><strong>1,208건</strong><small>0.94%</small></div>
                  <div><i>×</i><span>REJECT</span><strong>184건</strong><small>0.14%</small></div>
                  <div><i>{}</i><span>Malformed</span><strong>222건</strong><small>0.17%</small></div>
                  <div><i>♟</i><span>현재 연결 수</span><strong>156개</strong><small>총 1,024개</small></div>
                </div>
                <p class="forward-result">Spring Forward 결과 <b>정상</b><span>최근 10분</span></p>
              </article>

              <article class="system-panel backend-summary">
                <div class="system-panel-title"><h3>Backend / DB 요약</h3><button type="button">상세 보기 ›</button></div>
                <div class="backend-mini-grid">
                  <div><i>▱</i><span>Validation 실패율</span><strong>0.18%</strong><small>정상</small></div>
                  <div><i>▣</i><span>Duplicate 차단</span><strong>1,284건</strong><small>최근 1시간</small></div>
                  <div><i>▤</i><span>저장 성공률</span><strong>99.98%</strong><small>정상</small></div>
                  <div><i>⌁</i><span>DB 연결 상태</span><strong>정상</strong><small>활성</small></div>
                  <div><i>⌒</i><span>Query Latency (p95)</span><strong>18 ms</strong><small>정상</small></div>
                  <div><i>☁</i><span>백업 상태</span><strong>정상</strong><small>최근 1시간 전</small></div>
                </div>
              </article>
            </section>

            <article class="system-panel system-alert-table">
              <div class="system-panel-title"><h3>최근 시스템 알림</h3><button type="button">전체 알림 보기 ›</button></div>
              <table>
                <thead><tr><th>발생시각</th><th>구성요소</th><th>심각도</th><th>내용</th><th>상태</th></tr></thead>
                <tbody>
                  <tr><td>2025-05-11 17:32:41</td><td>Jetson (JETSON-27)</td><td><span class="sys-badge danger">치명</span></td><td>Jetson 상태 Stale (서울 톨링 A) - 10분 이상 상태 미수신</td><td><span class="sys-badge hold">조치중</span></td></tr>
                  <tr><td>2025-05-11 17:22:17</td><td>Ingress</td><td><span class="sys-badge warn">경고</span></td><td>Malformed Payload 증가 - 최근 10분간 45건</td><td><span class="sys-badge hold">조치중</span></td></tr>
                  <tr><td>2025-05-11 16:58:11</td><td>Network</td><td><span class="sys-badge warn">경고</span></td><td>LAN → LTE 경로 전환 - 부산 톨링 D</td><td><span class="sys-badge ok">완료</span></td></tr>
                  <tr><td>2025-05-11 16:44:10</td><td>Backend (Spring)</td><td><span class="sys-badge info">정보</span></td><td>API Latency (p95) 상승 - 210ms (임계치 300ms)</td><td><span class="sys-badge ok">완료</span></td></tr>
                  <tr><td>2025-05-11 15:31:05</td><td>PostgreSQL</td><td><span class="sys-badge info">정보</span></td><td>자동 백업 완료 - 스냅샷 생성 성공</td><td><span class="sys-badge ok">완료</span></td></tr>
                </tbody>
              </table>
            </article>
          </article>

          <article v-else-if="activeMenu === 'Ingress'" class="ingress-page">
            <section class="ingress-kpi-grid">
              <article class="ingress-kpi alive"><i>⌁</i><div><span>Ingress Alive</span><strong>정상</strong><small>Uptime 12일 04:32:11</small></div></article>
              <article class="ingress-kpi"><i>▣</i><div><span>수신 이벤트</span><strong>8,742,318 <em>건</em></strong><small>오늘 128,456건 ▲ +10.4%</small></div></article>
              <article class="ingress-kpi"><i>✓</i><div><span>ACK</span><strong>8,698,214 <em>건</em></strong><small>성공률 99.50%</small></div></article>
              <article class="ingress-kpi caution"><i>↻</i><div><span>RETRY</span><strong>31,245 <em>건</em></strong><small>비율 0.36%</small></div></article>
              <article class="ingress-kpi danger"><i>×</i><div><span>REJECT</span><strong>8,214 <em>건</em></strong><small>비율 0.09%</small></div></article>
              <article class="ingress-kpi malformed"><i>{ }</i><div><span>Malformed</span><strong>4,645 <em>건</em></strong><small>비율 0.05%</small></div></article>
            </section>

            <section class="ingress-main-grid">
              <article class="ingress-panel ingress-info-panel">
                <h3>연결 상태 및 주요 정보</h3>
                <ul class="ingress-info-list">
                  <li><span>현재 연결 수</span><strong>156 개</strong></li>
                  <li><span>총 연결 수 (누적)</span><strong>12,568 개</strong></li>
                  <li><span>마지막 event_id</span><b>evt_20250511_173504_f31a9c2b</b></li>
                  <li><span>마지막 payload 크기</span><strong>1,284 bytes</strong></li>
                  <li><span>Spring forward 결과</span><em class="ok">성공</em></li>
                  <li><span>Jetson 상태 수신 여부</span><em class="ok">수신 중</em></li>
                  <li><span>Jetson 상태 Stale 여부</span><em class="ok">정상</em></li>
                </ul>
                <footer><p><span>버전</span><b>ingress 1.3.7</b></p><p><span>시작 시간</span><b>2025-05-01 13:02:56</b></p><p><span>메모리 사용률</span><b>342 MB (28%)</b></p></footer>
              </article>

              <article class="ingress-panel ingress-chart-panel">
                <div class="ingress-panel-title"><h3>Ingress ?? ?? <small>(?? 1??)</small></h3><button type="button">?? 1??</button></div>
                <div class="ingress-chart-grid">
                  <section v-for="chart in ingressCharts" :key="chart.title"><h4>{{ chart.title }}</h4><ChartJsPanel type="line" :data="chart.data" :options="compactLineOptions" :height="128" /></section>
                </div>
              </article>

              <section class="ingress-side-stack">
                <article class="ingress-panel">
                  <div class="ingress-panel-title"><h3>LAN / LTE 전환 로그 <small>(최근 10건)</small></h3><button type="button">전체 보기 ›</button></div>
                  <table class="ingress-table"><thead><tr><th>시간</th><th>이전 경로</th><th>변경 경로</th><th>사유</th></tr></thead><tbody>
                    <tr><td>17:32:41</td><td class="route-lan">LAN</td><td class="route-lan">LAN</td><td>수동 복구</td></tr>
                    <tr><td>17:21:18</td><td class="route-lan">LAN</td><td class="route-lte">LTE</td><td>신호 회복</td></tr>
                    <tr><td>17:12:05</td><td class="route-lte">LTE</td><td class="route-lan">LAN</td><td>LAN 끊김</td></tr>
                    <tr><td>16:58:33</td><td class="route-lan">LAN</td><td class="route-lte">LTE</td><td>신호 회복</td></tr>
                    <tr><td>16:44:10</td><td class="route-lte">LTE</td><td class="route-lan">LAN</td><td>신호 약화</td></tr>
                  </tbody></table>
                </article>
                <article class="ingress-panel">
                  <div class="ingress-panel-title"><h3>Spring Forward 상태 <small>(최근 5건)</small></h3><button type="button">전체 보기 ›</button></div>
                  <table class="ingress-table"><thead><tr><th>시간</th><th>event_id</th><th>전송 결과</th><th>응답 시간</th><th>비고</th></tr></thead><tbody>
                    <tr><td>17:35:04</td><td>evt_20250511_173504_f31a9c2b</td><td class="route-lan">성공</td><td>145 ms</td><td>200 OK</td></tr>
                    <tr><td>17:34:57</td><td>evt_20250511_173457_d9b21a8c</td><td class="route-lan">성공</td><td>153 ms</td><td>200 OK</td></tr>
                    <tr><td>17:34:49</td><td>evt_20250511_173449_bc2f7e11</td><td class="route-lan">성공</td><td>149 ms</td><td>200 OK</td></tr>
                    <tr><td>17:34:39</td><td>evt_20250511_173439_9a6d3b7e</td><td class="route-lan">성공</td><td>161 ms</td><td>200 OK</td></tr>
                  </tbody></table>
                </article>
              </section>
            </section>

            <article class="ingress-panel ingress-error-panel">
              <div class="ingress-panel-title"><h3>최근 Ingress 오류 <small>(최근 10건)</small></h3><button type="button">전체 보기 ›</button></div>
              <table class="ingress-table error-table"><thead><tr><th>발생시각</th><th>event_id</th><th>source</th><th>오류 유형</th><th>payload 크기</th><th>처리 결과</th><th>상태</th></tr></thead><tbody>
                <tr><td>2025-05-11 17:31:45</td><td>evt_20250511_173145_7b2a12fc</td><td>Edge-DAE-02</td><td>Malformed JSON</td><td>512 bytes</td><td><span class="ingress-badge reject">REJECT</span></td><td><span class="ingress-badge hold">확인 필요</span></td></tr>
                <tr><td>2025-05-11 17:30:12</td><td>evt_20250511_173012_4c9d8f11</td><td>Edge-DGU-01</td><td>Schema Validation Error</td><td>768 bytes</td><td><span class="ingress-badge reject">REJECT</span></td><td><span class="ingress-badge hold">확인 필요</span></td></tr>
                <tr><td>2025-05-11 17:28:55</td><td>evt_20250511_172855_f12e3d9a</td><td>Edge-DBS-03</td><td>Spring Forward 실패 (5xx)</td><td>1,102 bytes</td><td><span class="ingress-badge retry">RETRY</span></td><td><span class="ingress-badge retry">재시도 중</span></td></tr>
                <tr><td>2025-05-11 17:27:21</td><td>evt_20250511_172721_9b4f88cd</td><td>Edge-DGW-02</td><td>Healthz Check Down</td><td>-</td><td>-</td><td><span class="ingress-badge info">조치 중</span></td></tr>
                <tr><td>2025-05-11 17:25:47</td><td>evt_20250511_172547_0c3d5f89</td><td>Edge-DJE-01</td><td>Payload 필드 누락</td><td>634 bytes</td><td><span class="ingress-badge reject">REJECT</span></td><td><span class="ingress-badge hold">확인 필요</span></td></tr>
              </tbody></table>
              <p class="ingress-footnote">※ 시간은 서버 시간 기준(KST) 입니다.</p>
            </article>
          </article>

          <article v-else-if="activeMenu === '백엔드/DB'" class="backend-db-page">
            <section class="backend-db-kpi-grid">
              <article class="backend-db-kpi ok"><i>✓</i><div><span>Backend 상태</span><strong>정상</strong><small>Uptime 12일 04:32:11</small></div></article>
              <article class="backend-db-kpi"><i>◷</i><div><span>API 응답 p95</span><strong>128 <em>ms</em></strong><small>p50 42 ms / p99 312 ms</small></div></article>
              <article class="backend-db-kpi purple"><i>⌾</i><div><span>Validation 실패율</span><strong>0.18 <em>%</em></strong><small>실패 482 / 전체 267,842</small></div></article>
              <article class="backend-db-kpi warn"><i>⇄</i><div><span>Duplicate 차단</span><strong>3,248 <em>건</em></strong><small>차단 비율 2.18%</small></div></article>
              <article class="backend-db-kpi ok"><i>▤</i><div><span>DB 연결 상태</span><strong>정상</strong><small>Active 28 / Max 100</small></div></article>
              <article class="backend-db-kpi"><i>↗</i><div><span>저장 성공률</span><strong>99.92 <em>%</em></strong><small>성공 267,432 / 실패 210</small></div></article>
            </section>

            <section class="backend-db-main-grid">
              <article class="backend-db-panel spring-service">
                <h3>Spring Boot 서비스 상태</h3>
                <table class="backend-db-table">
                  <thead><tr><th>서비스</th><th>상태</th><th>처리 건수(1분)</th><th>에러율</th><th>평균 응답시간</th></tr></thead>
                  <tbody>
                    <tr><td><span class="ok-dot">●</span> Protobuf Decode</td><td><b>정상</b></td><td>8,742</td><td>0.02%</td><td>14 ms</td></tr>
                    <tr><td><span class="ok-dot">●</span> DTO Validation</td><td><b>정상</b></td><td>8,742</td><td>0.18%</td><td>21 ms</td></tr>
                    <tr><td><span class="ok-dot">●</span> Duplicate Check</td><td><b>정상</b></td><td>8,742</td><td>0.02%</td><td>11 ms</td></tr>
                    <tr><td><span class="ok-dot">●</span> GPS 판정 처리</td><td><b>정상</b></td><td>8,742</td><td>0.05%</td><td>19 ms</td></tr>
                    <tr><td><span class="ok-dot">●</span> 결제 판정 처리</td><td><b>정상</b></td><td>8,742</td><td>0.04%</td><td>23 ms</td></tr>
                    <tr><td><span class="ok-dot">●</span> REST API</td><td><b>정상</b></td><td>2,156</td><td>0.08%</td><td>128 ms</td></tr>
                  </tbody>
                </table>
                <footer class="backend-db-panel-footer"><span>ⓘ 기준 구간 : 최근 1분</span><button type="button">상세 모니터링 ↗</button></footer>
              </article>

              <article class="backend-db-panel request-flow">
                <h3>요청/처리 흐름 <small>(실시간)</small></h3>
                <div class="flow-chain">
                  <div><i>▦</i><strong>Ingress<br />Forward</strong><b>●</b><span>수신 정상<br />8,742 /min</span></div>
                  <div><i>{ }</i><strong>Protobuf<br />Decode</strong><b>●</b><span>정상<br />8,742 /min</span></div>
                  <div><i>◈</i><strong>Validation</strong><b>●</b><span>정상<br />실패율 0.18%</span></div>
                  <div><i>⌕</i><strong>Duplicate<br />Check</strong><b>●</b><span>정상<br />차단율 2.18%</span></div>
                  <div><i>◎</i><strong>GPS<br />Payment Decision</strong><b>●</b><span>정상<br />정상율 97.82%</span></div>
                  <div><i>▤</i><strong>PostgreSQL<br />Save</strong><b>●</b><span>정상<br />성공률 99.92%</span></div>
                </div>
                <footer class="flow-legend"><span class="ok">정상</span><span class="warn">지연/주의</span><span class="error">오류</span><span class="idle">대기</span><em>자동 갱신 : 5초 ↻</em></footer>
              </article>

              <article class="backend-db-panel postgres-status">
                <h3>PostgreSQL (DB) 상태</h3>
                <ul>
                  <li><span>Active Connections</span><strong>28 / 100</strong><b>정상</b></li>
                  <li><span>Write TPS</span><strong>256 tps</strong><b>정상</b></li>
                  <li><span>Read TPS</span><strong>712 tps</strong><b>정상</b></li>
                  <li><span>Slow Query (1s 이상)</span><strong>3건</strong><b>정상</b></li>
                  <li><span>Storage Usage</span><strong>42.6%</strong><b>정상</b></li>
                  <li><span>Backup Status</span><strong></strong><b>정상</b></li>
                  <li class="wide-value"><span>Last Backup</span><strong>2025-05-11 02:00:00</strong></li>
                  <li><span>Replication Status</span><strong>정상 (Primary)</strong><b>정상</b></li>
                </ul>
                <button type="button">DB 상세 모니터링 ↗</button>
              </article>
            </section>

            <section class="backend-db-bottom-grid">
              <article class="backend-db-panel backend-errors">
                <h3>백엔드 오류 <small>(최근 5건)</small></h3>
                <table class="backend-db-table">
                  <thead><tr><th>발생시각</th><th>단계</th><th>event_id</th><th>오류 유형</th><th>처리 결과</th></tr></thead>
                  <tbody>
                    <tr><td>2025-05-11 17:35:12</td><td>DTO Validation</td><td>evt_20250511_173512_a1b2c3d4</td><td>잘못된 plate 형식</td><td><b class="db-badge reject">REJECT</b></td></tr>
                    <tr><td>2025-05-11 17:34:58</td><td>GPS 판정 처리</td><td>evt_20250511_173458_b2c3d4e5</td><td>GPS 좌표 누락</td><td><b class="db-badge reject">REJECT</b></td></tr>
                    <tr><td>2025-05-11 17:33:21</td><td>Duplicate Check</td><td>evt_20250511_173321_c3d4e5f6</td><td>중복 이벤트 (event_id)</td><td><b class="db-badge duplicate">DUPLICATE</b></td></tr>
                    <tr><td>2025-05-11 17:31:07</td><td>Protobuf Decode</td><td>evt_20250511_173107_d4e5f6a7</td><td>프로토콜 스키마 오류</td><td><b class="db-badge reject">REJECT</b></td></tr>
                    <tr><td>2025-05-11 17:29:44</td><td>REST API</td><td>-</td><td>/api/v1/events 타임아웃</td><td><b class="db-badge timeout">TIMEOUT</b></td></tr>
                  </tbody>
                </table>
                <footer class="backend-db-panel-footer right"><button type="button">전체 오류 로그 보기 ↗</button></footer>
              </article>

              <article class="backend-db-panel db-table-summary">
                <h3>DB 테이블 요약 <small>(주요 테이블)</small></h3>
                <table class="backend-db-table">
                  <thead><tr><th>테이블명</th><th>행 수</th><th>최근 쓰기 시간</th><th>상태</th></tr></thead>
                  <tbody>
                    <tr><td>passage_events</td><td>5,482,193</td><td>2025-05-11 17:36:45</td><td><b class="db-badge ok">정상</b></td></tr>
                    <tr><td>gps_telemetry</td><td>18,742,331</td><td>2025-05-11 17:36:44</td><td><b class="db-badge ok">정상</b></td></tr>
                    <tr><td>settlement_results</td><td>2,156,782</td><td>2025-05-11 17:36:42</td><td><b class="db-badge ok">정상</b></td></tr>
                    <tr><td>review_tasks</td><td>86,451</td><td>2025-05-11 17:35:11</td><td><b class="db-badge ok">정상</b></td></tr>
                    <tr><td>system_audit_logs</td><td>1,283,905</td><td>2025-05-11 17:36:40</td><td><b class="db-badge ok">정상</b></td></tr>
                  </tbody>
                </table>
                <footer class="backend-db-panel-footer right"><button type="button">DB 테이블 상세 보기 ↗</button></footer>
              </article>
            </section>
          </article>

          <article v-else-if="['시스템 모니터링', '시스템 관제'].includes(activeMenu)" class="panel glass subpage-panel">
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

          <article v-else-if="activeMenu === '장애 알림'" class="incident-page">
            <section class="incident-kpi-grid">
              <article class="incident-kpi critical"><i>!</i><div><span>치명</span><strong>7 <em>건</em></strong><small>전일 대비 ▲ 2</small></div></article>
              <article class="incident-kpi warn"><i>!</i><div><span>경고</span><strong>18 <em>건</em></strong><small>전일 대비 ▼ 4</small></div></article>
              <article class="incident-kpi info"><i>i</i><div><span>정보</span><strong>34 <em>건</em></strong><small>전일 대비 ▲ 6</small></div></article>
              <article class="incident-kpi action"><i>✕</i><div><span>조치중</span><strong>9 <em>건</em></strong><small>전일 대비 ▲ 1</small></div></article>
              <article class="incident-kpi done"><i>✓</i><div><span>완료 (금일)</span><strong>52 <em>건</em></strong><small>전일 대비 ▲ 8</small></div></article>
              <article class="incident-kpi time"><i>◷</i><div><span>평균 처리시간</span><strong>1시간 32분</strong><small>전일 1시간 26분 ▲ 6분</small></div></article>
            </section>

            <section class="incident-main-grid">
              <article class="incident-panel incident-list-panel">
                <div class="incident-filter-row">
                  <label><span>심각도</span><button class="filter-toggle" type="button">전체</button></label>
                  <label><span>구성요소</span><button class="filter-toggle" type="button">전체</button></label>
                  <label><span>지점</span><button class="filter-toggle" type="button">전체</button></label>
                  <label><span>상태</span><button class="filter-toggle" type="button">전체</button></label>
                  <div class="incident-search"><input type="search" placeholder="알림명 검색" /><span>⌕</span></div>
                  <button class="incident-icon-btn" type="button">▤</button>
                </div>
                <table class="incident-table">
                  <thead><tr><th></th><th>발생시각</th><th>구성요소</th><th>지점/서비스</th><th>심각도</th><th>알림명</th><th>영향</th><th>상태</th></tr></thead>
                  <tbody>
                    <tr class="selected"><td><span class="radio on"></span></td><td>17:35:21</td><td>Backend</td><td>서울 통합센터</td><td><b class="incident-badge critical">치명</b></td><td>Backend Validation 실패율 증가</td><td>결제 지연 발생</td><td><b class="incident-badge action">조치중</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:34:48</td><td>Edge (Jetson)</td><td>대전 톨링 B</td><td><b class="incident-badge critical">치명</b></td><td>Jetson 상태 Stale</td><td>통행 이벤트 지연</td><td><b class="incident-badge wait">대기</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:32:15</td><td>Ingress</td><td>수원 통합 A</td><td><b class="incident-badge warn">경고</b></td><td>Malformed Payload 증가</td><td>일부 이벤트 폐기</td><td><b class="incident-badge wait">대기</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:30:02</td><td>Ingress</td><td>광주 통합 E</td><td><b class="incident-badge warn">경고</b></td><td>Retry/Reject 비율 상승</td><td>전달 실패 증가</td><td><b class="incident-badge wait">대기</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:28:37</td><td>Edge (Jetson)</td><td>부산 톨링 D</td><td><b class="incident-badge warn">경고</b></td><td>Spool Count High (85%)</td><td>전송 지연 가능성</td><td><b class="incident-badge wait">대기</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:26:41</td><td>Network</td><td>경강선 구간</td><td><b class="incident-badge warn">경고</b></td><td>LAN → LTE 경로 전환</td><td>대역폭 감소</td><td><b class="incident-badge info">정보</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:24:10</td><td>DB (PostgreSQL)</td><td>통합 DB</td><td><b class="incident-badge warn">경고</b></td><td>Slow Query 감지</td><td>쿼리 처리 지연</td><td><b class="incident-badge wait">대기</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>17:21:05</td><td>Backend</td><td>서울 통합센터</td><td><b class="incident-badge info">정보</b></td><td>API Latency (p95) 1.2s</td><td>응답 지연 증가</td><td><b class="incident-badge info">정보</b></td></tr>
                  </tbody>
                </table>
                <footer class="incident-pagination"><span>전체 342건</span><div><button>‹</button><button class="active">1</button><button>2</button><button>3</button><button>4</button><button>5</button><button>…</button><button>35</button><button>›</button></div><button class="filter-toggle">10개씩 보기</button></footer>
              </article>

              <article class="incident-panel incident-detail-panel">
                <div class="incident-detail-head"><h3>선택 알림 상세</h3><b class="incident-badge critical">치명</b></div>
                <h2><i>!</i> Backend Validation 실패율 증가</h2>
                <dl class="incident-detail-grid">
                  <dt>구성요소</dt><dd>Backend (Spring Boot)</dd><dt>발생시각</dt><dd>2025-05-11 17:35:21</dd><dt>지점/서비스</dt><dd>서울 통합센터</dd><dt>상태 지속시간</dt><dd>12분 26초</dd>
                </dl>
                <h4>관련 지표 <small>(최근 10분)</small></h4>
                <div class="incident-related-grid">
                  <div><span>Validation 실패율</span><strong>5.6%</strong><small>임계값: 3%</small></div>
                  <div><span>Validation 오류 수</span><strong>1,248건</strong><small>임계값: 500</small></div>
                  <div><span>Duplicate 이벤트</span><strong>328건</strong><small>임계값: 200</small></div>
                  <div><span>API p95 Latency</span><strong>1.23 s</strong><small>임계값: 1.0 s</small></div>
                </div>
                <section class="incident-impact"><h4>운영 영향</h4><p><i>!</i> 검증 실패로 인한 결제 판정 지연 및 검수 대기 증가가 발생하고 있습니다.</p></section>
                <section class="incident-actions-text"><h4>권장 조치</h4><ol><li>Validation 규칙 및 판단 로직 확인</li><li>최근 배포 내역 및 설정 변경 사항 점검</li><li>관련 로그 분석 및 이상 데이터 샘플 확인</li></ol></section>
                <footer class="incident-actions"><button>확인</button><button>담당자 배정</button><button>유지보수 요청</button><button>완료 처리</button></footer>
              </article>
            </section>

            <section class="incident-bottom-grid">
              <article class="incident-panel incident-timeline">
                <h3>구성요소별 알림 타임라인</h3>
                <div class="timeline-legend"><span class="critical">치명</span><span class="warn">경고</span><span class="info">정보</span><span class="done">해제</span></div>
                <div class="timeline-chart">
                  <div class="timeline-labels"><span>Jetson Edge</span><span>Python Ingress</span><span>Backend (Spring)</span><span>PostgreSQL DB</span><span>Network</span></div>
                  <div class="timeline-board chart-timeline"><ChartJsPanel type="scatter" :data="incidentTimelineData" :options="incidentTimelineOptions" :height="150" /></div>
                </div>
                <button class="timeline-btn" type="button">타임라인 범례 보기</button>
              </article>

              <article class="incident-panel incident-history">
                <div class="incident-detail-head"><h3>최근 조치 내역</h3><button class="filter-toggle" type="button">전체 내역 보기</button></div>
                <table class="incident-history-table">
                  <thead><tr><th>시간</th><th>처리자</th><th>조치</th><th>메모</th></tr></thead>
                  <tbody>
                    <tr><td>17:35:32</td><td>admin</td><td>알림 확인</td><td><b class="incident-badge info">확인</b></td></tr>
                    <tr><td>17:35:48</td><td>admin</td><td>담당자 배정</td><td><b class="incident-badge action">조치중</b></td></tr>
                    <tr><td>17:32:01</td><td>system</td><td>알림 발생</td><td><b class="incident-badge critical">발생</b></td></tr>
                    <tr><td>17:30:12</td><td>admin</td><td>알림 확인</td><td><b class="incident-badge info">확인</b></td></tr>
                    <tr><td>17:29:45</td><td>admin</td><td>유지보수 요청</td><td><b class="incident-badge wait">요청중</b></td></tr>
                  </tbody>
                </table>
              </article>
            </section>
          </article>

          <article v-else-if="['공지사항'].includes(activeMenu)" class="panel glass subpage-panel">
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

          <article v-else-if="activeMenu === '감사 로그'" class="audit-log-page">
            <section class="audit-kpi-grid">
              <article class="audit-kpi"><i>▣</i><div><span>금일 로그</span><strong>1,284</strong><small>전일 대비 ▲ 8.4%</small></div></article>
              <article class="audit-kpi ok"><i>✓</i><div><span>성공 작업</span><strong>1,271</strong><small>성공률 98.9%</small></div></article>
              <article class="audit-kpi warn"><i>!</i><div><span>권한 변경</span><strong>34</strong><small>최근 24시간</small></div></article>
              <article class="audit-kpi info"><i>⌕</i><div><span>대리조회</span><strong>18</strong><small>감사 대상 3건</small></div></article>
              <article class="audit-kpi danger"><i>×</i><div><span>실패/거부</span><strong>13</strong><small>접근 거부 5건</small></div></article>
              <article class="audit-kpi"><i>↗</i><div><span>내보내기</span><strong>7</strong><small>CSV/PDF 생성</small></div></article>
            </section>

            <section class="audit-filter-row">
              <button class="filter-toggle" type="button">기간: 오늘</button>
              <button class="filter-toggle" type="button">작업 유형 전체</button>
              <button class="filter-toggle" type="button">작업자 전체</button>
              <button class="filter-toggle" type="button">결과 전체</button>
              <label><input type="search" placeholder="작업 내용, 대상, IP 검색" /><span>⌕</span></label>
              <button class="primary" type="button" @click="exportAuditLog">내보내기</button>
            </section>

            <section class="audit-main-grid">
              <article class="audit-panel audit-list-panel">
                <div class="audit-panel-head"><h3>감사 로그 목록 <small>최근 작업 이력</small></h3><button type="button">보존 정책 보기</button></div>
                <table class="audit-log-table">
                  <thead><tr><th></th><th>발생시각</th><th>작업자</th><th>대상</th><th>작업 유형</th><th>작업 내용</th><th>IP</th><th>결과</th></tr></thead>
                  <tbody>
                    <tr class="selected"><td><span class="radio on"></span></td><td>2026-05-12 10:24:11</td><td>admin</td><td>하이패스 서울(주)</td><td><b class="audit-badge info">권한</b></td><td>회원사 관제 대시보드 접근 권한 수정</td><td>192.168.0.89</td><td><b class="audit-badge ok">성공</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>2026-05-12 10:18:02</td><td>admin</td><td>수원 톨게이트</td><td><b class="audit-badge info">지점</b></td><td>대시보드 연결 지점 변경</td><td>192.168.0.89</td><td><b class="audit-badge ok">성공</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>2026-05-12 09:42:33</td><td>operator02</td><td>대전 톨게이트 B</td><td><b class="audit-badge warn">대리조회</b></td><td>장애 원인 확인 목적 대리조회</td><td>192.168.0.121</td><td><b class="audit-badge ok">성공</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>2026-05-12 09:21:08</td><td>admin</td><td>GPS 영역</td><td><b class="audit-badge info">설정</b></td><td>서울 톨링 A GPS 결제 영역 수정</td><td>192.168.0.89</td><td><b class="audit-badge ok">성공</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>2026-05-12 08:55:41</td><td>operator01</td><td>Backend / DB</td><td><b class="audit-badge danger">접근</b></td><td>권한 없는 DB 상세 모니터링 접근</td><td>192.168.0.144</td><td><b class="audit-badge danger">거부</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>2026-05-12 08:31:19</td><td>system</td><td>시스템 공지</td><td><b class="audit-badge info">공지</b></td><td>점검 공지 자동 게시</td><td>internal</td><td><b class="audit-badge ok">성공</b></td></tr>
                    <tr><td><span class="radio"></span></td><td>2026-05-12 08:12:04</td><td>admin</td><td>JETSON-27</td><td><b class="audit-badge warn">장비</b></td><td>원격 재시작 요청</td><td>192.168.0.89</td><td><b class="audit-badge ok">성공</b></td></tr>
                  </tbody>
                </table>
                <footer class="audit-pagination"><span>전체 12,568건</span><div><button>‹</button><button class="active">1</button><button>2</button><button>3</button><button>…</button><button>126</button><button>›</button></div><button>10개씩 보기</button></footer>
              </article>

              <aside class="audit-side-stack">
                <article class="audit-panel audit-detail-card">
                  <div class="audit-panel-head"><h3>선택 로그 상세</h3><span class="audit-badge ok">성공</span></div>
                  <dl>
                    <dt>로그 ID</dt><dd>AUD-20260512-102411-001</dd>
                    <dt>작업자</dt><dd>admin <small>최종 관리자</small></dd>
                    <dt>작업 대상</dt><dd>하이패스 서울(주)</dd>
                    <dt>작업 유형</dt><dd>권한 변경</dd>
                    <dt>요청 IP</dt><dd>192.168.0.89</dd>
                    <dt>User Agent</dt><dd>Chrome / Windows</dd>
                    <dt>처리 결과</dt><dd><span class="audit-badge ok">성공</span></dd>
                  </dl>
                </article>

                <article class="audit-panel audit-risk-card">
                  <h3>감사 위험도 분석</h3>
                  <div class="audit-risk-score"><strong>LOW</strong><span>정상 범위 작업</span></div>
                  <ul>
                    <li><span>비정상 시간대 접근</span><b>없음</b></li>
                    <li><span>권한 상승 시도</span><b>없음</b></li>
                    <li><span>반복 실패</span><b>없음</b></li>
                    <li><span>대리조회 사유</span><b class="warn">검토 3건</b></li>
                  </ul>
                </article>
              </aside>
            </section>

            <section class="audit-bottom-grid">
              <article class="audit-panel audit-type-card">
                <h3>작업 유형 분포</h3>
                <div class="audit-bars">
                  <span><b style="width:82%"></b><em>권한/계정 524</em></span>
                  <span><b style="width:64%"></b><em>지점/장비 408</em></span>
                  <span><b style="width:38%"></b><em>대리조회 218</em></span>
                  <span><b style="width:24%"></b><em>접근 거부 13</em></span>
                </div>
              </article>
              <article class="audit-panel audit-recent-card">
                <div class="audit-panel-head"><h3>최근 대리조회 감사</h3><button type="button">전체 감사 로그 보기</button></div>
                <table class="audit-log-table compact">
                  <thead><tr><th>시간</th><th>관리자</th><th>회원사 / 지점</th><th>사유</th><th>결과</th></tr></thead>
                  <tbody>
                    <tr v-for="audit in recentAuditRows" :key="`${audit.time}-${audit.target}`"><td>{{ audit.time }}</td><td>{{ audit.actor }}</td><td>{{ audit.target }}</td><td>{{ audit.reason }}</td><td><span class="audit-badge ok">{{ audit.result }}</span></td></tr>
                  </tbody>
                </table>
              </article>
            </section>
          </article>

          <article v-else class="settings-page">
            <section class="settings-kpi-grid">
              <article class="settings-kpi ok"><i>✓</i><div><span>콘솔 상태</span><strong>정상</strong><small>최근 저장 10:24</small></div></article>
              <article class="settings-kpi"><i>↻</i><div><span>자동 새로고침</span><strong>30초</strong><small>전체 대시보드 적용</small></div></article>
              <article class="settings-kpi warn"><i>!</i><div><span>보안 정책</span><strong>강화</strong><small>2FA 권장 3건</small></div></article>
              <article class="settings-kpi"><i>▤</i><div><span>로그 보존</span><strong>365일</strong><small>감사 로그 기준</small></div></article>
              <article class="settings-kpi ok"><i>☁</i><div><span>백업 정책</span><strong>활성</strong><small>매일 02:00</small></div></article>
              <article class="settings-kpi"><i>◐</i><div><span>기본 테마</span><strong>{{ isLightMode ? 'Light' : 'Dark' }}</strong><small>사용자별 저장</small></div></article>
            </section>

            <section class="settings-main-grid">
              <article class="settings-panel settings-form-panel">
                <div class="settings-panel-head">
                  <h3>관리자 콘솔 기본 설정</h3>
                  <button type="button" @click="saveMasterSettings">변경사항 저장</button>
                </div>
                <div class="settings-form-grid">
                  <label><span>기본 지도 편집</span><select><option>허용</option><option>승인 후 허용</option><option>차단</option></select><small>지점 마커 위치와 라벨 편집 권한</small></label>
                  <label><span>대시보드 자동 새로고침</span><select><option>30초</option><option>1분</option><option>5분</option><option>수동</option></select><small>관리자/관제 대시보드 데이터 갱신 주기</small></label>
                  <label><span>공지 노출 범위</span><select><option>전체 회원사</option><option>선택 회원사</option><option>내부 관리자만</option></select><small>시스템 공지와 점검 공지 기본 대상</small></label>
                  <label><span>기본 진입 대시보드</span><select><option>관리자 대시보드</option><option>시스템 관제</option><option>장애 알림</option></select><small>로그인 후 최초 진입 화면</small></label>
                  <label><span>위험 알림 기준</span><select><option>치명 즉시 알림</option><option>경고 이상 알림</option><option>전체 알림</option></select><small>상단 알림 버튼과 장애 알림 집계 기준</small></label>
                  <label><span>라이트/다크 모드</span><select :value="themeMode" @change="themeMode = $event.target.value"><option value="dark">Dark</option><option value="light">Light</option></select><small>현재 브라우저에 저장되는 UI 테마</small></label>
                </div>
              </article>

              <aside class="settings-side-stack">
                <article class="settings-panel settings-security">
                  <h3>보안 및 접근 정책</h3>
                  <ul>
                    <li><span>관리자 세션 만료</span><b>60분</b><em>활성</em></li>
                    <li><span>비밀번호 정책</span><b>12자 이상</b><em>강화</em></li>
                    <li><span>IP 접근 제한</span><b>사내망 우선</b><em class="warn">검토</em></li>
                    <li><span>권한 변경 승인</span><b>MASTER 승인</b><em>활성</em></li>
                  </ul>
                </article>

                <article class="settings-panel settings-backup">
                  <h3>백업 / 보존 정책</h3>
                  <dl>
                    <dt>DB 백업</dt><dd>매일 02:00</dd>
                    <dt>감사 로그 보존</dt><dd>365일</dd>
                    <dt>장애 알림 보존</dt><dd>180일</dd>
                    <dt>최근 백업</dt><dd>2026-05-12 02:00</dd>
                  </dl>
                </article>
              </aside>
            </section>

            <section class="settings-bottom-grid">
              <article class="settings-panel settings-notification">
                <h3>알림 채널 설정</h3>
                <div>
                  <span><b>시스템 상태</b><em>콘솔 배너 / 이메일</em><strong>ON</strong></span>
                  <span><b>장애 알림</b><em>브라우저 / Slack / 이메일</em><strong>ON</strong></span>
                  <span><b>권한 변경</b><em>감사 로그 / 이메일</em><strong>ON</strong></span>
                  <span><b>백업 실패</b><em>콘솔 배너 / SMS</em><strong>ON</strong></span>
                </div>
              </article>

              <article class="settings-panel settings-history">
                <div class="settings-panel-head"><h3>최근 설정 변경 이력</h3><button type="button">전체 보기</button></div>
                <table class="settings-table">
                  <thead><tr><th>시간</th><th>관리자</th><th>항목</th><th>이전 값</th><th>변경 값</th><th>결과</th></tr></thead>
                  <tbody>
                    <tr><td>10:24:11</td><td>admin</td><td>자동 새로고침</td><td>1분</td><td>30초</td><td><span class="settings-badge ok">성공</span></td></tr>
                    <tr><td>09:52:44</td><td>admin</td><td>공지 노출 범위</td><td>선택 회원사</td><td>전체 회원사</td><td><span class="settings-badge ok">성공</span></td></tr>
                    <tr><td>09:20:31</td><td>operator02</td><td>지도 편집</td><td>허용</td><td>승인 후 허용</td><td><span class="settings-badge warn">검토</span></td></tr>
                    <tr><td>08:48:10</td><td>system</td><td>백업 정책</td><td>대기</td><td>활성</td><td><span class="settings-badge ok">성공</span></td></tr>
                  </tbody>
                </table>
              </article>
            </section>
          </article>
        </section>

        <div v-if="showCenterModal" class="modal-backdrop" @click.self="showCenterModal = false">
          <article class="center-detail-modal glass">
            <div class="modal-head">
              <div>
                <p class="subpage-kicker">TOLLING CENTER</p>
                <h3>{{ selectedCenterDetail.name }}</h3>
              </div>
              <span class="center-modal-status" :class="statusClass(selectedCenterDetail.status)">
                {{ statusText(selectedCenterDetail.status) }}
              </span>
              <button class="modal-close" type="button" @click="showCenterModal = false">×</button>
            </div>

            <section class="center-modal-summary">
              <dl>
                <div>
                  <dt>지점명</dt>
                  <dd>{{ selectedCenterDetail.name }}</dd>
                </div>
                <div>
                  <dt>담당 회원사</dt>
                  <dd>{{ centerOwner(selectedCenterDetail.name) }}</dd>
                </div>
                <div>
                  <dt>Edge 대수</dt>
                  <dd>{{ selectedCenterDetail.edgeCount }}대</dd>
                </div>
                <div>
                  <dt>최근 장애</dt>
                  <dd>{{ centerIssueCount(selectedCenterDetail.name) }}</dd>
                </div>
                <div class="wide">
                  <dt>위치 주소</dt>
                  <dd>{{ selectedCenterDetail.address }}</dd>
                </div>
                <div>
                  <dt>위도</dt>
                  <dd>{{ selectedCenterDetail.lat }}</dd>
                </div>
                <div>
                  <dt>경도</dt>
                  <dd>{{ selectedCenterDetail.lng }}</dd>
                </div>
              </dl>
              <button class="center-dashboard-btn" type="button" @click="enterCenter(selectedCenterDetail)">
                관제 대시보드 진입
              </button>
            </section>

            <section class="center-modal-metrics">
              <div class="center-period-tabs">
                <button
                  v-for="period in ['daily', 'weekly', 'monthly']"
                  :key="period"
                  type="button"
                  :class="{ active: centerMetricPeriod === period }"
                  @click="centerMetricPeriod = period"
                >
                  {{ selectedCenterDetail.metrics[period].label }}
                </button>
              </div>

              <div class="center-metric-cards">
                <article>
                  <span>통행량</span>
                  <strong>{{ selectedCenterDetail.metric.traffic.toLocaleString() }}</strong>
                  <small>{{ selectedCenterDetail.metric.label }} 기준</small>
                </article>
                <article>
                  <span>정산 금액</span>
                  <strong>₩{{ selectedCenterDetail.metric.settlement.toLocaleString() }}</strong>
                  <small>정산 후보 포함</small>
                </article>
              </div>

              <div class="center-bar-chart">
                <span
                  v-for="(height, index) in selectedCenterDetail.metric.bars"
                  :key="`${selectedCenterDetail.name}-${centerMetricPeriod}-${index}`"
                  :style="{ height: `${height}%` }"
                >
                  <i></i>
                </span>
              </div>
            </section>
          </article>
        </div>

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

.map-edit-btn.ghost {
  border-color: rgba(117, 151, 194, 0.36);
  color: #c9d9ee;
  background: rgba(5, 18, 37, 0.48);
}

.map-edit-btn.ghost.danger {
  border-color: rgba(255, 109, 52, 0.38);
  color: #ffb191;
  background: rgba(255, 109, 52, 0.1);
}

.map-edit-btn.ghost.save {
  border-color: rgba(76, 223, 102, 0.42);
  color: #8ff7a5;
  background: rgba(35, 136, 68, 0.16);
}

.map-edit-btn:disabled {
  opacity: 0.42;
  cursor: not-allowed;
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

.center-detail-modal {
  width: min(860px, 100%);
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

.center-modal-status {
  min-width: 68px;
  height: 30px;
  display: grid;
  place-items: center;
  margin-left: auto;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.center-modal-status.ok {
  color: #78f39b;
  background: rgba(37, 204, 113, 0.15);
  border: 1px solid rgba(37, 204, 113, 0.32);
}

.center-modal-status.caution {
  color: #ffd05f;
  background: rgba(255, 185, 40, 0.13);
  border: 1px solid rgba(255, 185, 40, 0.34);
}

.center-modal-status.danger {
  color: #ff817a;
  background: rgba(255, 100, 93, 0.13);
  border: 1px solid rgba(255, 100, 93, 0.34);
}

.center-modal-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px;
  gap: 14px;
  align-items: stretch;
}

.center-modal-summary dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.center-modal-summary dl div {
  min-height: 58px;
  display: grid;
  align-content: center;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid rgba(117, 151, 194, 0.15);
  border-radius: 6px;
  background: rgba(5, 18, 37, 0.52);
}

.center-modal-summary dl .wide {
  grid-column: span 2;
}

.center-modal-summary dt,
.center-modal-summary dd {
  margin: 0;
}

.center-modal-summary dt {
  color: #9fb2cb;
  font-size: 12px;
}

.center-modal-summary dd {
  color: #f4f8ff;
  font-size: 15px;
  font-weight: 700;
}

.center-dashboard-btn {
  min-height: 100%;
  border: 1px solid rgba(42, 133, 227, 0.52);
  border-radius: 6px;
  color: #eef7ff;
  background: linear-gradient(135deg, rgba(22, 131, 255, 0.78), rgba(10, 67, 143, 0.9));
  font-size: 15px;
  font-weight: 800;
}

.center-modal-metrics {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid rgba(117, 151, 194, 0.15);
  border-radius: 6px;
  background: rgba(5, 18, 37, 0.42);
}

.center-period-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.center-period-tabs button {
  width: 82px;
  height: 32px;
  border: 1px solid rgba(42, 133, 227, 0.32);
  border-radius: 5px;
  color: #c9d7eb;
  background: rgba(3, 12, 26, 0.64);
}

.center-period-tabs button.active {
  color: #fff;
  border-color: rgba(42, 133, 227, 0.68);
  background: rgba(22, 103, 219, 0.52);
}

.center-metric-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.center-metric-cards article {
  min-height: 92px;
  padding: 14px;
  border: 1px solid rgba(42, 133, 227, 0.22);
  border-radius: 6px;
  background: linear-gradient(180deg, rgba(16, 42, 76, 0.78), rgba(7, 24, 47, 0.72));
}

.center-metric-cards span,
.center-metric-cards small {
  display: block;
  color: #9fb2cb;
  font-size: 12px;
}

.center-metric-cards strong {
  display: block;
  margin: 7px 0 5px;
  color: #fff;
  font-size: 26px;
}

.center-bar-chart {
  height: 150px;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  align-items: end;
  gap: 12px;
  padding: 18px 18px 12px;
  border: 1px solid rgba(117, 151, 194, 0.13);
  border-radius: 6px;
  background:
    linear-gradient(rgba(117, 151, 194, 0.1) 1px, transparent 1px),
    rgba(2, 10, 22, 0.34);
  background-size: 100% 30px;
}

.center-bar-chart span {
  min-height: 18px;
  display: block;
  border-radius: 5px 5px 2px 2px;
  background: linear-gradient(180deg, #53d98a, #1778ef);
  box-shadow: 0 0 12px rgba(22, 131, 255, 0.22);
}

.center-bar-chart i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255,255,255,0.22), transparent);
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
.master-shell.light .company-modal,
.master-shell.light .center-detail-modal {
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
.master-shell.light .modal-head h3,
.master-shell.light .center-modal-summary dd,
.master-shell.light .center-metric-cards strong,
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

.master-shell.light .center-modal-summary dl div,
.master-shell.light .center-modal-metrics,
.master-shell.light .center-metric-cards article {
  background: rgba(246, 250, 255, 0.88);
  border-color: rgba(58, 126, 204, 0.24);
}

.master-shell.light .center-modal-summary dt,
.master-shell.light .center-metric-cards span,
.master-shell.light .center-metric-cards small {
  color: #53677f;
}

.master-shell.light .center-period-tabs button {
  color: #34536f;
  background: rgba(255, 255, 255, 0.88);
  border-color: rgba(58, 126, 204, 0.24);
}

.master-shell.light .center-period-tabs button.active {
  color: #063963;
  background: rgba(22, 131, 255, 0.15);
  border-color: rgba(22, 131, 255, 0.45);
}

.master-shell.light .center-bar-chart {
  background:
    linear-gradient(rgba(82, 112, 145, 0.12) 1px, transparent 1px),
    rgba(255, 255, 255, 0.82);
  border-color: rgba(58, 126, 204, 0.22);
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
.master-shell.light .company-modal *,
.master-shell.light .center-detail-modal * {
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
.master-shell.light .center-detail-modal,
.master-shell.light .company-modal p,
.master-shell.light .company-modal span,
.master-shell.light .center-detail-modal p,
.master-shell.light .center-detail-modal span {
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

/* Master dashboard 2026 control-console layout */
.master-shell {
  grid-template-columns: 220px 1fr;
}

.sidebar {
  padding: 18px 12px 12px;
}

.sidebar-brand {
  height: 68px;
  align-items: flex-start;
}

.sidebar-brand strong {
  font-size: 25px;
  letter-spacing: 0;
}

.sidebar-brand span:not(.brand-diamond) {
  line-height: 1.25;
}

.brand-diamond {
  margin-top: 3px;
  width: 28px;
  height: 28px;
}

.nav-main {
  height: 44px;
  grid-template-columns: 26px 1fr 10px;
  font-size: 15px;
  border-radius: 6px;
}

.nav-icon {
  font-size: 17px;
}

.nav-children {
  display: none;
}

.quick-menu {
  padding: 12px;
}

.quick-menu button {
  height: 41px;
  text-align: left;
  padding: 0 14px;
  font-size: 14px;
}

.content-shell main {
  padding: 14px 16px 12px;
}

.topbar {
  height: 66px;
  padding: 0 20px;
}

.topbar-title .brand-diamond {
  display: none;
}

.topbar-title strong {
  font-size: 25px;
}

.topbar-title span:not(.brand-diamond) {
  font-size: 25px;
  font-weight: 800;
  color: #fff;
}

.global-ok {
  min-width: 136px;
  justify-content: center;
  padding: 8px 18px;
  border: 1px solid rgba(37, 204, 113, 0.38);
  border-radius: 5px;
  background: rgba(37, 204, 113, 0.12);
  color: #62f18d;
}

.admin-chip b {
  font-size: 16px;
}

.master-kpi-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.master-kpi-grid .kpi {
  min-height: 100px;
  border-radius: 8px;
}

.master-kpi-grid .kpi-icon {
  width: 58px;
  height: 58px;
  font-size: 25px;
  box-shadow: 0 0 18px rgba(42, 133, 227, 0.2);
}

.master-kpi-grid .kpi p {
  font-size: 13px;
}

.master-kpi-grid .kpi strong {
  font-size: 30px;
}

.master-overview-grid {
  grid-template-columns: minmax(720px, 1.08fr) minmax(560px, 0.92fr);
  gap: 14px;
  align-items: stretch;
}

.master-overview-grid .map-panel,
.master-overview-grid .right-column {
  min-height: 548px;
}

.master-overview-grid .right-column {
  display: grid;
  grid-template-rows: 1fr;
  gap: 14px;
}

.panel-title h2 {
  font-size: 19px;
}

.map-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.map-actions span {
  padding: 7px 14px;
  border: 1px solid rgba(37, 204, 113, 0.28);
  border-radius: 999px;
  color: #7ef3a0;
  background: rgba(37, 204, 113, 0.1);
  font-size: 12px;
  font-weight: 800;
}

.map-actions span:not(.active) {
  opacity: 0.58;
}

.map-stage {
  min-height: 486px;
  border-radius: 7px;
}

.state-summary {
  top: 12px;
  left: 18px;
  width: 158px;
}

.marker-label {
  min-width: 154px;
  padding: 10px 12px;
}

.marker-detail {
  display: none;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(145, 185, 231, 0.22);
  color: #d9e9fb;
  font-size: 12px;
  line-height: 1.6;
  white-space: normal;
}

.map-marker.selected .marker-label {
  min-width: 235px;
}

.map-marker.selected .marker-detail {
  display: block;
}

.map-marker.selected:not(.expanded) .marker-label {
  min-width: 154px;
}

.map-marker.expanded .marker-label {
  min-width: 235px;
}

.map-marker.expanded .marker-detail {
  display: block;
}

.center-more-btn {
  height: 28px;
  border: 1px solid rgba(42, 133, 227, 0.54);
  border-radius: 5px;
  color: #eaf4ff;
  background: rgba(17, 78, 153, 0.46);
}

.live-center-table th,
.audit-mini-table th {
  height: 36px;
}

.live-center-table td,
.audit-mini-table td {
  height: 40px;
}

.center-more-btn {
  display: block;
  margin: 8px auto 0;
  padding: 0 16px;
  color: #4da3ff;
  background: transparent;
  border-color: transparent;
}

.audit-panel {
  min-height: 0;
}

.audit-panel small {
  color: #9fb2cb;
  font-size: 13px;
}

.audit-mini-table {
  font-size: 12.5px;
}

.dashboard-pipeline-panel {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.dashboard-pipeline-table {
  width: 100%;
  flex: 1;
  border-collapse: collapse;
  table-layout: auto;
  overflow: hidden;
  border: 1px solid rgba(117, 151, 194, 0.14);
  border-radius: 6px;
}

.dashboard-pipeline-table tr {
  border-bottom: 1px solid rgba(117, 151, 194, 0.1);
}

.dashboard-pipeline-table tr:nth-child(3n) {
  border-bottom-color: rgba(42, 133, 227, 0.32);
}

.dashboard-pipeline-table td {
  height: 38px;
  padding: 0 12px;
  color: #dce9f8;
  font-size: 13.5px;
  white-space: nowrap;
  border-right: 1px solid rgba(117, 151, 194, 0.1);
}

.dashboard-pipeline-table td:last-child {
  border-right: 0;
}

.pipeline-table-icon {
  width: 58px;
  text-align: center;
  color: #7ec1ff !important;
  font-size: 28px !important;
  background: rgba(47, 140, 255, 0.1);
}

.pipeline-table-name {
  width: 92px;
  color: #f2f7ff !important;
  font-size: 16px !important;
  font-weight: 700;
}

.dashboard-pipeline-table td:nth-child(3),
.dashboard-pipeline-table tr:not(:first-child) td:first-child:not(.pipeline-table-icon) {
  color: #9fb2cb;
}

.dashboard-pipeline-table td:nth-child(4),
.dashboard-pipeline-table tr:not(:first-child) td:nth-child(2):not(.pipeline-table-name) {
  color: #f2f7ff;
  text-align: right;
  font-size: 14px;
  font-weight: 700;
}

.pipeline-spark {
  width: 96px;
  min-width: 96px;
  text-align: center !important;
}

.pipeline-spark svg {
  width: 86px;
  height: 24px;
  overflow: visible;
}

.pipeline-spark polyline {
  fill: none;
  stroke: #35dc72;
  stroke-width: 2.8;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 0 5px rgba(53, 220, 114, 0.34));
}

.pipeline-spark.warn polyline {
  stroke: #ffb928;
  filter: drop-shadow(0 0 5px rgba(255, 185, 40, 0.28));
}

.pipeline-table-state {
  width: 144px;
  text-align: center;
  background: rgba(37, 204, 113, 0.08);
}

.pipeline-table-state b,
.pipeline-table-state span {
  display: block;
  color: #65eb8a;
  font-size: 13px;
  font-weight: 600;
}

.pipeline-table-state span {
  margin-top: 4px;
  color: #dce9f8;
  font-weight: 400;
}

.master-bottom-grid {
  display: grid;
  grid-template-columns: 330px 1fr 1fr;
  gap: 14px;
  margin-top: 14px;
}

.master-bottom-grid .panel {
  min-height: 246px;
}

.donut-content {
  height: calc(100% - 42px);
}

.alert-list,
.notice-list {
  display: grid;
  gap: 0;
}

.alert-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.alert-list li,
.notice-list li {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr) 72px;
  align-items: center;
  min-height: 38px;
  border-bottom: 1px solid rgba(125, 164, 210, 0.12);
}

.notice-list li {
  grid-template-columns: minmax(0, 1fr) 94px;
}

.alert-list b {
  width: 58px;
  padding: 5px 8px;
  border-radius: 5px;
  text-align: center;
  font-size: 12px;
}

.alert-list b.danger {
  background: rgba(255, 91, 103, 0.16);
  border: 1px solid rgba(255, 91, 103, 0.38);
}

.alert-list b.caution {
  background: rgba(255, 190, 65, 0.16);
  border: 1px solid rgba(255, 190, 65, 0.38);
}

.alert-list b.info {
  background: rgba(39, 135, 255, 0.16);
  border: 1px solid rgba(39, 135, 255, 0.38);
}

.alert-list span,
.notice-list span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-list time,
.notice-list time {
  color: #93a8c3;
  text-align: right;
  font-size: 12px;
}

.master-shell.light .global-ok,
.master-shell.light .map-actions span {
  color: #087a50;
  background: rgba(22, 154, 96, 0.1);
}

.master-shell.light .marker-detail,
.master-shell.light .audit-panel small,
.master-shell.light .alert-list time,
.master-shell.light .notice-list time {
  color: #425b78;
}

.master-shell.light .alert-list span,
.master-shell.light .notice-list span {
  color: #17283b;
}

.master-shell.light .dashboard-pipeline-table {
  border-color: rgba(58, 126, 204, 0.22);
}

.master-shell.light .dashboard-pipeline-table td,
.master-shell.light .pipeline-table-name {
  color: #102033 !important;
}

.master-shell.light .dashboard-pipeline-table td:nth-child(3),
.master-shell.light .dashboard-pipeline-table tr:not(:first-child) td:first-child:not(.pipeline-table-icon) {
  color: #53677f !important;
}

.master-shell.light .pipeline-table-icon {
  color: #0f67b4 !important;
  background: rgba(36, 126, 219, 0.1);
}

.master-shell.light .pipeline-table-state {
  background: rgba(24, 142, 84, 0.08);
}

.master-shell.light .pipeline-table-state b {
  color: #087a50;
}

.master-shell.light .pipeline-table-state span {
  color: #425b78;
}

.master-shell.light .pipeline-spark polyline {
  stroke: #178f52;
  filter: none;
}

.master-shell.light .pipeline-spark.warn polyline {
  stroke: #b46b00;
}

.master-shell.light .alert-list b.danger {
  color: #a33b00;
  background: rgba(179, 75, 0, 0.1);
}

.master-shell.light .alert-list b.caution {
  color: #7a5200;
  background: rgba(154, 103, 0, 0.1);
}

.master-shell.light .alert-list b.info {
  color: #0f5f9a;
  background: rgba(15, 95, 154, 0.1);
}

/* Final layout lock: map left, live/audit right, status/notice/alert bottom */
.master-overview-grid.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(700px, 1.08fr) minmax(560px, 0.92fr);
  grid-template-rows: minmax(548px, 1fr) minmax(218px, 0.4fr);
  grid-template-areas:
    "map side"
    "lower side";
  align-items: stretch;
  gap: 14px;
  margin-top: 12px;
}

.master-overview-grid > .map-panel {
  grid-area: map;
  grid-column: auto;
  min-height: 548px;
}

.master-overview-grid > .right-column {
  grid-area: side;
  grid-column: auto;
  min-height: 780px;
  display: grid;
  grid-template-rows: minmax(0, 1fr);
  gap: 14px;
}

.master-overview-grid > .right-column > .panel {
  min-height: 0;
  overflow: hidden;
}

.dashboard-lower-panels {
  grid-area: lower;
  display: grid;
  grid-template-columns: minmax(260px, 0.72fr) minmax(420px, 1.28fr);
  gap: 14px;
  min-height: 218px;
}

.dashboard-lower-panels > .panel {
  min-height: 218px;
}

.master-bottom-grid.bottom-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.82fr) minmax(380px, 1fr) minmax(380px, 1fr);
  grid-template-areas: "audit notice alert";
  gap: 14px;
  margin-top: 14px;
}

.master-bottom-grid > .dashboard-audit-panel {
  grid-area: audit;
}

.master-bottom-grid > .notice-panel {
  grid-area: notice;
}

.master-bottom-grid > .alert-panel {
  grid-area: alert;
}

.master-bottom-grid > .panel {
  min-height: 246px;
}

.ingress-page {
  display: grid;
  gap: 14px;
}

.ingress-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.ingress-kpi,
.ingress-panel {
  border: 1px solid rgba(42, 133, 227, 0.28);
  border-radius: 6px;
  background: rgba(5, 16, 33, 0.72);
  box-shadow: 0 0 0 1px rgba(14, 111, 219, 0.08), 0 18px 42px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(16px);
}

.ingress-kpi {
  min-height: 96px;
  display: grid;
  grid-template-columns: 62px 1fr;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.ingress-kpi i {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06101f;
  font-style: normal;
  font-weight: 900;
  background: linear-gradient(135deg, #35b7ff, #1378ef);
  box-shadow: 0 0 12px rgba(19, 120, 239, 0.24);
}

.ingress-kpi.alive i,
.ingress-kpi:not(.danger):not(.caution):not(.malformed):nth-child(3) i {
  background: linear-gradient(135deg, #5ff5be, #16a373);
}

.ingress-kpi.caution i {
  background: linear-gradient(135deg, #ffe16e, #ffb928);
}

.ingress-kpi.danger i {
  background: linear-gradient(135deg, #ff7b70, #d64640);
  color: #fff;
}

.ingress-kpi.malformed i {
  background: linear-gradient(135deg, #aab0ff, #7a6cff);
  color: #fff;
}

.ingress-kpi span {
  display: block;
  color: #e6f1ff;
  font-size: 13px;
  font-weight: 700;
}

.ingress-kpi strong {
  display: block;
  margin-top: 4px;
  color: #fff;
  font-size: 25px;
  line-height: 1.1;
}

.ingress-kpi strong em {
  color: #dce9f8;
  font-size: 14px;
  font-style: normal;
}

.ingress-kpi small {
  display: block;
  margin-top: 5px;
  color: #8ff7a5;
  font-size: 12px;
}

.ingress-kpi.danger small { color: #ff806e; }
.ingress-kpi.caution small { color: #7ee6a0; }

.ingress-main-grid {
  display: grid;
  grid-template-columns: minmax(290px, 0.72fr) minmax(420px, 0.92fr) minmax(510px, 1.18fr);
  gap: 12px;
}

.ingress-panel {
  min-width: 0;
  padding: 13px;
}

.ingress-panel h3,
.ingress-panel-title h3 {
  margin: 0;
  color: #f1f7ff;
  font-size: 16px;
  font-weight: 800;
}

.ingress-panel-title {
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
  padding-left: 10px;
  border-left: 2px solid #1683ff;
}

.ingress-panel-title small {
  color: #9fb2cb;
  font-weight: 500;
}

.ingress-panel-title button {
  height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(42, 133, 227, 0.46);
  border-radius: 5px;
  color: #d9eaff;
  background: rgba(5, 18, 37, 0.72);
}

.ingress-info-list {
  display: grid;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  border: 1px solid rgba(117, 151, 194, 0.15);
  border-radius: 6px;
  overflow: hidden;
}

.ingress-info-list li {
  min-height: 46px;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(117, 151, 194, 0.12);
}

.ingress-info-list li:last-child { border-bottom: 0; }
.ingress-info-list span { color: #c9d7eb; font-size: 13px; }
.ingress-info-list strong { color: #f5fbff; font-size: 16px; }
.ingress-info-list b { color: #cfe0f4; font-size: 11px; font-weight: 500; }
.ingress-info-list em { min-width: 72px; height: 28px; display: grid; place-items: center; border: 1px solid rgba(76, 223, 102, 0.35); border-radius: 6px; color: #67e887; background: rgba(35, 136, 68, 0.16); font-style: normal; font-weight: 800; }

.ingress-info-panel footer {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 12px;
  border-top: 1px solid rgba(117, 151, 194, 0.16);
}

.ingress-info-panel footer p {
  margin: 0;
  padding: 12px 8px 0;
  border-right: 1px solid rgba(117, 151, 194, 0.16);
}

.ingress-info-panel footer p:last-child { border-right: 0; }
.ingress-info-panel footer span { display: block; color: #9fb2cb; font-size: 11px; }
.ingress-info-panel footer b { display: block; margin-top: 5px; color: #f4f8ff; font-size: 11px; }

.ingress-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 18px;
}

.ingress-chart-grid section {
  min-height: 174px;
}

.ingress-chart-grid h4 {
  margin: 0 0 8px;
  color: #e6f1ff;
  font-size: 13px;
}

.line-chart {
  height: 142px;
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background:
    linear-gradient(rgba(117, 151, 194, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(117, 151, 194, 0.1) 1px, transparent 1px);
  background-size: 100% 35px, 48px 100%;
}

.line-chart::before {
  content: '16:35   16:50   17:05   17:20   17:35';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 4px;
  color: #90a5c0;
  font-size: 11px;
  word-spacing: 14px;
}

.line-chart svg {
  position: absolute;
  inset: 8px 8px 18px;
  width: calc(100% - 16px);
  height: calc(100% - 26px);
  overflow: visible;
}

.line-chart polyline {
  fill: none;
  stroke: #2f8cff;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 0 5px rgba(47, 140, 255, 0.42));
}

.line-chart circle {
  r: 3.5;
  fill: #2f8cff;
  stroke: #06101f;
  stroke-width: 1.5;
}

.line-chart.dual .ack { stroke: #42d779; filter: drop-shadow(0 0 5px rgba(66, 215, 121, 0.34)); }
.line-chart.dual .retry { stroke: #ffb928; filter: drop-shadow(0 0 5px rgba(255, 185, 40, 0.28)); }
.line-chart.dual .ack-points circle { fill: #42d779; }
.line-chart.dual .retry-points circle { fill: #ffb928; }
.line-chart.reject .reject-line { stroke: #ff665f; filter: drop-shadow(0 0 5px rgba(255, 102, 95, 0.3)); }
.line-chart.reject .malformed-line { stroke: #b28cff; filter: drop-shadow(0 0 5px rgba(178, 140, 255, 0.24)); }
.line-chart.reject .reject-points circle { fill: #ff665f; }
.line-chart.reject .malformed-points circle { fill: #b28cff; }
.line-chart.cyan polyline { stroke: #26c8e8; filter: drop-shadow(0 0 5px rgba(38, 200, 232, 0.32)); }
.line-chart.cyan circle { fill: #26c8e8; }

.ingress-side-stack {
  display: grid;
  gap: 12px;
}

.ingress-table {
  width: 100%;
  border-collapse: collapse;
}

.ingress-table th,
.ingress-table td {
  height: 30px;
  padding: 0 10px;
  border-bottom: 1px solid rgba(117, 151, 194, 0.12);
  color: #d7e6ff;
  text-align: left;
  white-space: nowrap;
}

.ingress-table td {
  font-weight: 400;
}

.ingress-table th {
  color: #9fb2cb;
  background: rgba(26, 46, 73, 0.54);
  font-weight: 600;
}

.route-lan { color: #57e77e !important; font-weight: 400; }
.route-lte { color: #ffb928 !important; font-weight: 400; }

.ingress-side-stack .ingress-table {
  table-layout: fixed;
  font-size: 11px;
}

.ingress-side-stack .ingress-table td,
.ingress-side-stack .ingress-table th {
  overflow: hidden;
  text-overflow: ellipsis;
}

.ingress-error-panel {
  padding-bottom: 8px;
}

.ingress-badge {
  min-width: 70px;
  height: 24px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
}

.ingress-badge.reject { border: 1px solid rgba(255, 91, 85, 0.45); color: #ff786f; background: rgba(255, 91, 85, 0.12); }
.ingress-badge.retry,
.ingress-badge.hold { border: 1px solid rgba(255, 185, 40, 0.45); color: #ffd05f; background: rgba(255, 185, 40, 0.12); }
.ingress-badge.info { border: 1px solid rgba(47, 140, 255, 0.45); color: #9fc9ff; background: rgba(47, 140, 255, 0.12); }

.ingress-footnote {
  margin: 12px 0 0;
  color: #9fb2cb;
  font-size: 12px;
  text-align: center;
}

.master-shell.light .ingress-kpi,
.master-shell.light .ingress-panel {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(58, 126, 204, 0.3);
  box-shadow: 0 12px 30px rgba(49, 91, 137, 0.12);
}

.master-shell.light .ingress-panel h3,
.master-shell.light .ingress-panel-title h3,
.master-shell.light .ingress-kpi strong,
.master-shell.light .ingress-chart-grid h4,
.master-shell.light .ingress-info-list strong,
.master-shell.light .ingress-info-panel footer b,
.master-shell.light .ingress-table td {
  color: #102033;
}

.master-shell.light .ingress-kpi span,
.master-shell.light .ingress-panel-title small,
.master-shell.light .ingress-info-list span,
.master-shell.light .ingress-info-panel footer span,
.master-shell.light .ingress-footnote,
.master-shell.light .ingress-table th {
  color: #53677f;
}

.master-shell.light .line-chart {
  background:
    linear-gradient(rgba(82, 112, 145, 0.14) 1px, transparent 1px),
    linear-gradient(90deg, rgba(82, 112, 145, 0.12) 1px, transparent 1px);
  background-size: 100% 35px, 48px 100%;
}

.topbar-title span:not(.brand-diamond) {
  font-size: 12px;
}

.ingress-info-list em {
  min-width: 60px;
  height: 24px;
  font-size: 12px;
  font-weight: 600;
}

.system-control-page {
  display: grid;
  gap: 12px;
}

.system-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.system-kpi,
.system-panel {
  border: 1px solid rgba(42, 133, 227, 0.28);
  border-radius: 6px;
  background: rgba(5, 16, 33, 0.72);
  box-shadow: 0 0 0 1px rgba(14, 111, 219, 0.08), 0 18px 42px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(16px);
}

.system-kpi {
  min-height: 96px;
  display: grid;
  grid-template-columns: 62px 1fr;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.system-kpi i {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06101f;
  font-style: normal;
  font-weight: 900;
  font-size: 22px;
  background: linear-gradient(135deg, #35b7ff, #1378ef);
  box-shadow: 0 0 12px rgba(19, 120, 239, 0.24);
}

.system-kpi.ok i { background: linear-gradient(135deg, #5ff5be, #16a373); }
.system-kpi.danger i { color: #fff; background: linear-gradient(135deg, #ff7b70, #d64640); }
.system-kpi span { color: #e6f1ff; font-size: 13px; font-weight: 700; }
.system-kpi strong { display: block; margin-top: 5px; color: #fff; font-size: 26px; line-height: 1.1; }
.system-kpi strong em { color: #dce9f8; font-size: 14px; font-style: normal; }
.system-kpi small { display: block; margin-top: 5px; color: #c9d7eb; font-size: 12px; }

.system-panel {
  padding: 13px;
}

.system-panel h3,
.system-panel-title h3 {
  margin: 0;
  color: #f1f7ff;
  font-size: 16px;
  font-weight: 800;
}

.pipeline-panel h3 {
  margin-bottom: 14px;
}

.pipeline-flow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 40px;
}

.pipeline-node {
  min-height: 186px;
  position: relative;
  padding: 14px 16px 0;
  border: 1px solid rgba(42, 133, 227, 0.36);
  border-radius: 6px;
  background: linear-gradient(180deg, rgba(12, 38, 70, 0.86), rgba(6, 22, 43, 0.84));
}

.pipeline-node:not(:last-child)::after {
  content: '✓';
  position: absolute;
  right: -30px;
  top: 42px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06101f;
  background: #35dc72;
  font-size: 13px;
  font-weight: 900;
}

.pipeline-node:not(:last-child)::before {
  content: '';
  position: absolute;
  right: -42px;
  top: 52px;
  width: 42px;
  height: 2px;
  background: linear-gradient(90deg, rgba(53, 220, 114, 0.45), rgba(53, 220, 114, 0.9));
  box-shadow: 0 0 10px rgba(53, 220, 114, 0.26);
}

.pipeline-node i {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06101f;
  background: linear-gradient(135deg, #5ff5be, #16a373);
  font-style: normal;
  font-weight: 900;
}

.pipeline-node h4 {
  position: absolute;
  left: 66px;
  top: 17px;
  margin: 0;
  color: #fff;
  font-size: 15px;
}

.pipeline-node b {
  display: block;
  margin: 7px 0 13px 52px;
  color: #5fe080;
  font-size: 13px;
}

.pipeline-node dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 9px;
  margin: 0;
  padding-top: 10px;
}

.pipeline-node dt,
.pipeline-node dd {
  margin: 0;
  color: #dce9f8;
  font-size: 13px;
}

.pipeline-node dd {
  text-align: right;
}

.pipeline-node p {
  margin: 12px -16px 0;
  padding: 10px 16px;
  color: #d8e6f8;
  background: rgba(2, 9, 20, 0.22);
  font-size: 12px;
}

.pipeline-node p span {
  width: 9px;
  height: 9px;
  display: inline-block;
  margin-right: 7px;
  border-radius: 50%;
  background: #35dc72;
}

.system-summary-grid {
  display: grid;
  grid-template-columns: 1.05fr 0.9fr 0.98fr;
  gap: 12px;
}

.system-panel-title {
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
}

.system-panel-title button {
  height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(42, 133, 227, 0.46);
  border-radius: 5px;
  color: #d9eaff;
  background: rgba(5, 18, 37, 0.72);
}

.edge-summary {
  display: grid;
  grid-template-columns: 1fr 150px;
  gap: 14px;
}

.edge-summary .system-panel-title {
  grid-column: 1 / -1;
  margin-bottom: 0;
}

.edge-metrics,
.ingress-mini-grid,
.backend-mini-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.edge-metrics div,
.ingress-mini-grid div,
.backend-mini-grid div {
  min-height: 76px;
  position: relative;
  padding: 12px;
  border: 1px solid rgba(42, 133, 227, 0.22);
  border-radius: 6px;
  background: rgba(6, 24, 50, 0.45);
}

.edge-metrics div,
.ingress-mini-grid div,
.backend-mini-grid div {
  padding-left: 58px;
}

.edge-metrics i,
.ingress-mini-grid i,
.backend-mini-grid i {
  position: absolute;
  left: 14px;
  top: 16px;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #8fd7ff;
  background: rgba(47, 140, 255, 0.14);
  box-shadow: inset 0 0 0 1px rgba(47, 140, 255, 0.22);
  font-style: normal;
  font-weight: 800;
}

.edge-metrics span,
.ingress-mini-grid span,
.backend-mini-grid span {
  display: block;
  color: #c9d7eb;
  font-size: 12px;
}

.edge-metrics strong,
.ingress-mini-grid strong,
.backend-mini-grid strong {
  display: block;
  margin-top: 6px;
  color: #fff;
  font-size: 22px;
}

.edge-metrics strong em {
  font-size: 13px;
  font-style: normal;
}

.edge-metrics small,
.ingress-mini-grid small,
.backend-mini-grid small {
  display: block;
  margin-top: 4px;
  color: #9fb2cb;
  font-size: 11px;
}

.donut-wrap {
  align-self: stretch;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 10px;
}

.donut-wrap h4 {
  margin: 0;
  color: #f1f7ff;
  font-size: 13px;
  font-weight: 800;
}

.system-donut {
  align-self: center;
  justify-self: center;
  width: 138px;
  height: 138px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: conic-gradient(#45d779 0 72%, #ffce48 72% 86%, #ff635c 86% 92%, rgba(117,151,194,.25) 92% 100%);
  box-shadow: inset 0 0 0 28px rgba(5, 16, 33, 0.96);
}

.system-donut strong {
  color: #fff;
  font-size: 30px;
}

.system-donut span {
  margin-top: -44px;
  color: #dce9f8;
  font-size: 13px;
}

.donut-wrap ul {
  display: grid;
  gap: 5px;
  margin: 0;
  padding: 0;
  color: #c9d7eb;
  font-size: 12px;
  list-style: none;
}

.donut-wrap li {
  display: flex;
  align-items: center;
  gap: 7px;
}

.donut-wrap li b {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.donut-wrap li b.ok { background: #45d779; }
.donut-wrap li b.warn { background: #ffce48; }
.donut-wrap li b.danger { background: #ff635c; }

.forward-result {
  margin: 12px 0 0;
  padding-top: 10px;
  border-top: 1px solid rgba(117, 151, 194, 0.16);
  color: #e6f1ff;
}

.forward-result b {
  margin-left: 14px;
  padding: 5px 12px;
  border-radius: 999px;
  color: #06101f;
  background: #45d779;
}

.forward-result span {
  margin-left: 10px;
  color: #c9d7eb;
  font-size: 12px;
}

.system-alert-table table {
  width: 100%;
  border-collapse: collapse;
}

.system-alert-table th,
.system-alert-table td {
  height: 32px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(117, 151, 194, 0.12);
  color: #dce9f8;
  text-align: left;
  font-weight: 400;
}

.system-alert-table th {
  color: #9fb2cb;
  background: rgba(26, 46, 73, 0.54);
  font-weight: 600;
}

.system-alert-table tbody td,
.system-alert-table tbody span {
  font-weight: 400;
}

.sys-badge {
  min-width: 56px;
  height: 23px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
}

.sys-badge.danger { color: #ff756d; border: 1px solid rgba(255, 91, 85, 0.42); background: rgba(255, 91, 85, 0.12); }
.sys-badge.warn,
.sys-badge.hold { color: #ffd05f; border: 1px solid rgba(255, 185, 40, 0.42); background: rgba(255, 185, 40, 0.12); }
.sys-badge.info { color: #8fc1ff; border: 1px solid rgba(47, 140, 255, 0.42); background: rgba(47, 140, 255, 0.12); }
.sys-badge.ok { color: #6ff08e; border: 1px solid rgba(37, 204, 113, 0.42); background: rgba(37, 204, 113, 0.12); }

.master-shell.light .system-kpi,
.master-shell.light .system-panel {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(58, 126, 204, 0.3);
  box-shadow: 0 12px 30px rgba(49, 91, 137, 0.12);
}

.master-shell.light .system-panel h3,
.master-shell.light .system-panel-title h3,
.master-shell.light .system-kpi strong,
.master-shell.light .pipeline-node h4,
.master-shell.light .pipeline-node dt,
.master-shell.light .pipeline-node dd,
.master-shell.light .edge-metrics strong,
.master-shell.light .ingress-mini-grid strong,
.master-shell.light .backend-mini-grid strong,
.master-shell.light .system-alert-table td {
  color: #102033;
}

.master-shell.light .system-kpi span,
.master-shell.light .system-kpi small,
.master-shell.light .edge-metrics span,
.master-shell.light .ingress-mini-grid span,
.master-shell.light .backend-mini-grid span,
.master-shell.light .system-alert-table th {
  color: #53677f;
}

.master-shell.light .pipeline-node,
.master-shell.light .edge-metrics div,
.master-shell.light .ingress-mini-grid div,
.master-shell.light .backend-mini-grid div {
  background: rgba(246, 250, 255, 0.86);
  border-color: rgba(58, 126, 204, 0.26);
}

.master-shell.light .system-donut {
  box-shadow: inset 0 0 0 28px rgba(255, 255, 255, 0.95);
}

.master-shell.light .system-donut strong,
.master-shell.light .system-donut span,
.master-shell.light .forward-result,
.master-shell.light .donut-wrap h4 {
  color: #102033;
}

.edge-page{display:grid;gap:12px}.edge-kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.edge-kpi,.edge-panel{border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.edge-kpi{min-height:96px;display:grid;grid-template-columns:62px 1fr;align-items:center;gap:12px;padding:12px}.edge-kpi i{width:54px;height:54px;display:grid;place-items:center;border-radius:50%;color:#06101f;font-style:normal;font-weight:900;font-size:22px;background:linear-gradient(135deg,#35b7ff,#1378ef);box-shadow:0 0 12px rgba(19,120,239,.24)}.edge-kpi.ok i{background:linear-gradient(135deg,#5ff5be,#16a373)}.edge-kpi.warn i{background:linear-gradient(135deg,#ffe16e,#ffb928)}.edge-kpi.danger i{color:#fff;background:linear-gradient(135deg,#ff7b70,#d64640)}.edge-kpi span{color:#e6f1ff;font-size:13px;font-weight:700}.edge-kpi strong{display:block;margin-top:5px;color:#fff;font-size:26px;line-height:1.1}.edge-kpi strong em{color:#dce9f8;font-size:14px;font-style:normal}.edge-kpi small{display:block;margin-top:5px;color:#c9d7eb;font-size:12px}.edge-kpi.ok small{color:#5fe080}.edge-kpi.warn small{color:#ffca4f}.edge-kpi.danger small{color:#ff756d}
.edge-main-grid{display:grid;grid-template-columns:minmax(760px,1.35fr) minmax(420px,.65fr);gap:12px;align-items:stretch}.edge-panel{min-width:0;padding:13px}.edge-list-panel,.edge-detail-panel{display:flex;flex-direction:column}.edge-panel h3{margin:0;color:#f1f7ff;font-size:16px;font-weight:800}.edge-panel h3 small{color:#9fb2cb;font-weight:500}.edge-filter-row{display:grid;grid-template-columns:repeat(5,120px) 1fr 90px;gap:8px;margin:13px 0 10px}.edge-filter-row button,.edge-filter-row label{height:34px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.edge-filter-row button{padding:0 26px 0 10px;text-align:left}.filter-toggle{position:relative}.filter-toggle::after{content:'';position:absolute;right:10px;top:50%;width:7px;height:7px;border-right:1px solid currentColor;border-bottom:1px solid currentColor;transform:translateY(-65%) rotate(45deg);opacity:.75}.edge-filter-row label{display:grid;grid-template-columns:1fr 34px;align-items:center}.edge-filter-row input{min-width:0;border:0;background:transparent;color:#eaf4ff;padding-left:12px;outline:0}.edge-table{width:100%;border-collapse:collapse;font-size:12px}.edge-table th,.edge-table td{height:34px;padding:0 8px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:center;white-space:nowrap;font-weight:400}.edge-table th{color:#9fb2cb;background:rgba(26,46,73,.54);font-weight:600}.edge-table td:nth-child(2),.edge-table td:nth-child(3),.edge-table th:nth-child(2),.edge-table th:nth-child(3){text-align:left}.edge-table tr.selected{background:rgba(22,103,219,.18);box-shadow:inset 0 0 0 1px rgba(33,130,255,.7)}.radio{width:15px;height:15px;display:inline-block;border-radius:50%;border:1px solid #56708f}.radio.on{border:3px solid #4ea0ff;box-shadow:0 0 10px rgba(78,160,255,.4)}.edge-badge{min-width:44px;height:22px;display:inline-grid;place-items:center;border-radius:5px;font-size:11px;font-weight:500}.edge-badge.ok{color:#6ff08e;background:rgba(37,204,113,.14)}.edge-badge.idle,.edge-badge.path{color:#82bdff;background:rgba(47,140,255,.14)}.edge-badge.warn{color:#ffd05f;background:rgba(255,185,40,.14)}.edge-pagination{display:grid;grid-template-columns:1fr auto 120px;align-items:center;margin-top:auto;padding-top:12px;color:#c9d7eb}.edge-pagination div{display:flex;gap:8px}.edge-pagination button{height:30px;min-width:30px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.edge-pagination button.active{background:rgba(22,103,219,.52);border-color:#1683ff}
.edge-detail-head{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(117,151,194,.16);padding-bottom:10px}.edge-detail-head span{color:#54e987}.edge-detail-list{display:grid;grid-template-columns:120px 1fr;gap:0;margin:8px 0 14px}.edge-detail-list dt,.edge-detail-list dd{height:28px;margin:0;border-bottom:1px solid rgba(117,151,194,.1);color:#dce9f8;font-size:12px}.edge-detail-list dt{color:#9fb2cb}.edge-detail-list dd.ok{color:#61e483}.edge-detail-panel h4{margin:12px 0 10px;color:#eaf4ff;font-size:13px}.edge-live-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.edge-live-grid div{min-height:38px;display:grid;grid-template-columns:24px minmax(0,1fr) auto;align-items:center;gap:7px;padding:8px;border:1px solid rgba(42,133,227,.22);border-radius:5px;background:rgba(6,24,50,.45)}.edge-live-grid i{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;color:#8fc1ff;background:rgba(47,140,255,.14);font-style:normal;font-size:11px}.edge-live-grid span{display:block;color:#9fb2cb;font-size:11px;white-space:nowrap}.edge-live-grid strong{display:block;margin-top:0;color:#eaf4ff;font-size:12px;text-align:right;font-weight:400;white-space:nowrap}.edge-live-grid strong.danger{color:#ff756d}.edge-recent-error{flex:1;margin-top:12px;padding:10px;border:1px solid rgba(117,151,194,.14);border-radius:5px}.edge-recent-error p{height:calc(100% - 28px);min-height:34px;display:grid;place-items:center;margin:0;color:#8fa3bd;border:1px solid rgba(117,151,194,.12);border-radius:5px}.edge-actions{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.edge-actions button{height:34px;border:1px solid rgba(42,133,227,.42);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.edge-actions button:first-child{background:rgba(22,103,219,.5)}
.edge-chart-row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metric-chart{min-height:220px;position:relative}.metric-chart h3{font-size:14px}.metric-chart h3 small{color:#9fb2cb}.metric-chart b{position:absolute;right:18px;top:18px;min-width:42px;height:24px;display:grid;place-items:center;border-radius:5px;color:#6ff08e;background:rgba(37,204,113,.14);font-size:12px;font-weight:500}.metric-chart b.warn{color:#ffd05f;background:rgba(255,185,40,.14)}.metric-chart>strong{display:block;margin-top:8px;color:#fff;font-size:21px}.metric-chart>span{position:absolute;left:28px;bottom:20px;color:#c9d7eb;font-size:12px}.mini-line{height:128px;margin-top:22px;border-radius:5px;background:linear-gradient(rgba(117,151,194,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(117,151,194,.1) 1px,transparent 1px);background-size:100% 32px,44px 100%;position:relative}.mini-line svg{position:absolute;inset:8px 10px 18px;width:calc(100% - 20px);height:calc(100% - 26px);overflow:visible}.mini-line polyline{fill:none;stroke:#2f8cff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 5px rgba(47,140,255,.36))}.mini-line circle{r:3.5;fill:#2f8cff;stroke:#06101f;stroke-width:1.5}.mini-line.green polyline{stroke:#42d779}.mini-line.green circle{fill:#42d779}.mini-line.purple polyline{stroke:#b28cff}.mini-line.purple circle{fill:#b28cff}.mini-line.orange polyline{stroke:#ffb928}.mini-line.orange circle{fill:#ffb928}.mini-line.cyan polyline{stroke:#26c8e8}.mini-line.cyan circle{fill:#26c8e8}
.master-shell.light .edge-kpi,.master-shell.light .edge-panel{background:rgba(255,255,255,.82);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .edge-panel h3,.master-shell.light .edge-kpi strong,.master-shell.light .edge-table td,.master-shell.light .edge-detail-list dd,.master-shell.light .edge-live-grid strong,.master-shell.light .metric-chart>strong{color:#102033}.master-shell.light .edge-kpi span,.master-shell.light .edge-kpi small,.master-shell.light .edge-table th,.master-shell.light .edge-detail-list dt,.master-shell.light .edge-live-grid span{color:#53677f}.master-shell.light .edge-filter-row button,.master-shell.light .edge-filter-row label,.master-shell.light .edge-pagination button,.master-shell.light .edge-actions button{background:rgba(255,255,255,.86);color:#21496f}.master-shell.light .edge-live-grid div,.master-shell.light .edge-metrics div{background:rgba(246,250,255,.86)}
.edge-filter-row button{font-size:11px;white-space:nowrap}
.edge-detail-list dd.ok{display:block;background:transparent;border-left:0;border-right:0;color:#61e483;font-weight:400}
.edge-live-grid strong.danger{display:block;background:transparent;border:0;color:#ff9f5a;font-weight:400}

.incident-page{display:grid;gap:12px}.incident-kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.incident-kpi,.incident-panel{border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.incident-kpi{min-height:92px;display:grid;grid-template-columns:58px 1fr;align-items:center;gap:12px;padding:12px}.incident-kpi i{width:50px;height:50px;display:grid;place-items:center;border-radius:50%;color:#fff;font-style:normal;font-weight:900;font-size:22px;background:linear-gradient(135deg,#ff7b70,#d64640);box-shadow:0 0 12px rgba(214,70,64,.24)}.incident-kpi.warn i{color:#06101f;background:linear-gradient(135deg,#ffe16e,#ffb928)}.incident-kpi.info i{background:linear-gradient(135deg,#58a8ff,#196dd1)}.incident-kpi.action i{background:linear-gradient(135deg,#b28cff,#7148d6)}.incident-kpi.done i{color:#06101f;background:linear-gradient(135deg,#5ff5be,#16a373)}.incident-kpi.time i{background:linear-gradient(135deg,#81c4ff,#2b6fae)}.incident-kpi span{color:#e6f1ff;font-size:13px;font-weight:700}.incident-kpi strong{display:block;margin-top:5px;color:#fff;font-size:24px;line-height:1.1}.incident-kpi strong em{color:#dce9f8;font-size:14px;font-style:normal}.incident-kpi small{display:block;margin-top:5px;color:#c9d7eb;font-size:12px}
.incident-main-grid{display:grid;grid-template-columns:minmax(680px,1.12fr) minmax(460px,.88fr);gap:12px;align-items:stretch}.incident-panel{min-width:0;padding:13px}.incident-list-panel{display:flex;flex-direction:column}.incident-filter-row{display:grid;grid-template-columns:repeat(4,120px) 1fr 34px;gap:8px;margin-bottom:10px}.incident-filter-row label{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:7px;color:#c9d7eb;font-size:12px}.incident-filter-row button,.incident-search,.incident-icon-btn{height:34px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.incident-filter-row button{padding:0 24px 0 10px;text-align:left;font-size:12px}.incident-search{display:grid;grid-template-columns:1fr 34px;align-items:center}.incident-search input{min-width:0;border:0;background:transparent;color:#eaf4ff;padding-left:12px;outline:0}.incident-icon-btn{display:grid;place-items:center;padding:0}.incident-table,.incident-history-table{width:100%;border-collapse:collapse;font-size:12px}.incident-list-panel .incident-table{flex:1}.incident-table th,.incident-table td,.incident-history-table th,.incident-history-table td{height:34px;padding:0 8px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:left;white-space:nowrap;font-weight:400}.incident-list-panel .incident-table th,.incident-list-panel .incident-table td{height:42px}.incident-table th,.incident-history-table th{color:#9fb2cb;background:rgba(26,46,73,.54);font-weight:600}.incident-table tr.selected{background:rgba(22,103,219,.18);box-shadow:inset 0 0 0 1px rgba(33,130,255,.7)}.incident-badge{min-width:54px;height:23px;display:inline-grid;place-items:center;border-radius:5px;font-size:12px;font-weight:500}.incident-badge.critical{color:#ff756d;border:1px solid rgba(255,91,85,.42);background:rgba(255,91,85,.12)}.incident-badge.warn,.incident-badge.wait{color:#ffd05f;border:1px solid rgba(255,185,40,.42);background:rgba(255,185,40,.12)}.incident-badge.info{color:#8fc1ff;border:1px solid rgba(47,140,255,.42);background:rgba(47,140,255,.12)}.incident-badge.action{color:#bda6ff;border:1px solid rgba(157,118,255,.42);background:rgba(157,118,255,.12)}.incident-pagination{display:grid;grid-template-columns:1fr auto 120px;align-items:center;margin-top:auto;padding-top:12px;color:#c9d7eb}.incident-pagination div{display:flex;gap:8px}.incident-pagination button{height:30px;min-width:30px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.incident-pagination button.active{background:rgba(22,103,219,.52);border-color:#1683ff}
.incident-detail-panel{display:flex;flex-direction:column}.incident-detail-head{display:flex;align-items:center;justify-content:space-between}.incident-detail-head h3{margin:0;color:#f1f7ff;font-size:16px}.incident-detail-panel h2{display:flex;gap:10px;align-items:center;margin:14px 0 12px;color:#fff;font-size:21px}.incident-detail-panel h2 i{width:24px;height:24px;display:grid;place-items:center;border-radius:50%;color:#06101f;background:#ffb928;font-style:normal}.incident-detail-grid{display:grid;grid-template-columns:90px 1fr 90px 1fr;margin:0 0 14px;border:1px solid rgba(117,151,194,.14);border-radius:5px}.incident-detail-grid dt,.incident-detail-grid dd{height:34px;margin:0;padding:0 10px;display:flex;align-items:center;border-bottom:1px solid rgba(117,151,194,.1);color:#dce9f8;font-size:12px}.incident-detail-grid dt{color:#9fb2cb}.incident-related-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.incident-related-grid div{min-height:82px;padding:10px;border:1px solid rgba(42,133,227,.22);border-radius:5px;background:rgba(6,24,50,.45)}.incident-related-grid span,.incident-related-grid small{display:block;color:#9fb2cb;font-size:11px}.incident-related-grid strong{display:block;margin:8px 0 4px;color:#fff;font-size:20px}.incident-impact{margin-top:12px;padding:10px 0;border-top:1px solid rgba(117,151,194,.16);border-bottom:1px solid rgba(117,151,194,.16)}.incident-impact h4,.incident-actions-text h4{margin:0 0 8px;color:#eaf4ff;font-size:13px}.incident-impact p{margin:0;color:#dce9f8;font-size:13px}.incident-impact i{color:#ffb928;font-style:normal}.incident-actions-text{padding-top:10px}.incident-actions-text ol{margin:0;padding-left:18px;color:#dce9f8;font-size:12px;line-height:1.7}.incident-actions{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:auto;padding-top:14px}.incident-actions button{height:34px;border:1px solid rgba(42,133,227,.42);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.incident-actions button:last-child{border-color:rgba(37,204,113,.42);background:rgba(37,204,113,.14);color:#8ff7a5}
.incident-bottom-grid{display:grid;grid-template-columns:minmax(680px,1.12fr) minmax(460px,.88fr);gap:12px}.incident-timeline h3{margin:0 0 8px;color:#f1f7ff;font-size:16px}.timeline-legend{display:flex;gap:18px;margin-bottom:8px;color:#c9d7eb;font-size:12px}.timeline-legend span::before{content:'';display:inline-block;width:9px;height:9px;margin-right:6px;border-radius:50%;background:#8fc1ff}.timeline-legend .critical::before{background:#ff635c}.timeline-legend .warn::before{background:#ffb928}.timeline-legend .info::before{background:#3d8cff}.timeline-legend .done::before{background:#50d779}.timeline-chart{display:grid;grid-template-columns:140px 1fr;min-height:150px}.timeline-labels{display:grid;grid-template-rows:repeat(5,1fr);color:#dce9f8;font-size:12px}.timeline-board{position:relative;border-left:1px solid rgba(117,151,194,.2);background:linear-gradient(rgba(117,151,194,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(117,151,194,.12) 1px,transparent 1px);background-size:100% 30px,25% 100%}.timeline-board .dot{position:absolute;width:12px;height:12px;border-radius:50%;transform:translate(-50%,-50%)}.timeline-board .critical{background:#ff635c}.timeline-board .warn{background:#ffb928}.timeline-board .info{background:#3d8cff}.timeline-board .done{background:#50d779}.timeline-btn{height:32px;margin-top:10px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#d9eaff;background:rgba(5,18,37,.72)}.incident-history .incident-detail-head{margin-bottom:10px}.incident-history-table td:last-child{text-align:right}
.master-shell.light .incident-kpi,.master-shell.light .incident-panel{background:rgba(255,255,255,.82);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .incident-kpi strong,.master-shell.light .incident-panel h3,.master-shell.light .incident-detail-panel h2,.master-shell.light .incident-related-grid strong,.master-shell.light .incident-table td,.master-shell.light .incident-history-table td{color:#102033}.master-shell.light .incident-kpi span,.master-shell.light .incident-kpi small,.master-shell.light .incident-table th,.master-shell.light .incident-history-table th,.master-shell.light .incident-related-grid span,.master-shell.light .incident-related-grid small{color:#53677f}.master-shell.light .incident-related-grid div{background:rgba(246,250,255,.86)}

.backend-db-page{display:grid;gap:12px}.backend-db-kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.backend-db-kpi,.backend-db-panel{border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.backend-db-kpi{min-height:104px;display:grid;grid-template-columns:58px 1fr;align-items:center;gap:12px;padding:13px}.backend-db-kpi i{width:52px;height:52px;display:grid;place-items:center;border-radius:50%;color:#fff;font-style:normal;font-weight:900;font-size:22px;background:linear-gradient(135deg,#4da6ff,#1a67cf);box-shadow:0 0 12px rgba(34,124,230,.2)}.backend-db-kpi.ok i{color:#06101f;background:linear-gradient(135deg,#77f4bd,#20a966)}.backend-db-kpi.purple i{background:linear-gradient(135deg,#bfa1ff,#6d50bf)}.backend-db-kpi.warn i{color:#06101f;background:linear-gradient(135deg,#ffe16e,#f1a31b)}.backend-db-kpi span{color:#e8f2ff;font-size:13px;font-weight:700}.backend-db-kpi strong{display:block;margin-top:5px;color:#fff;font-size:25px;line-height:1.08}.backend-db-kpi strong em{font-size:14px;font-style:normal;color:#d7e8fb}.backend-db-kpi small{display:block;margin-top:8px;color:#c6d5e8;font-size:11px}.backend-db-main-grid{display:grid;grid-template-columns:minmax(370px,.88fr) minmax(470px,1.12fr) minmax(340px,.85fr);gap:12px}.backend-db-bottom-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:12px}.backend-db-panel{min-width:0;padding:14px}.backend-db-panel h3{margin:0 0 12px;color:#f2f7ff;font-size:16px}.backend-db-panel h3 small{color:#91a8c4;font-size:11px;font-weight:500}.backend-db-table{width:100%;border-collapse:collapse;font-size:12px}.backend-db-table th,.backend-db-table td{height:39px;padding:0 8px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:left;white-space:nowrap;font-weight:400}.backend-db-table th{height:34px;color:#a9bad0;background:rgba(28,49,77,.58);font-weight:600}.backend-db-table td b:not(.db-badge){color:#5fe080;font-weight:500}.ok-dot{color:#50d779;font-size:11px}.backend-db-panel-footer{display:flex;align-items:center;justify-content:space-between;margin-top:12px;color:#cbd8ea;font-size:12px}.backend-db-panel-footer.right{justify-content:flex-end}.backend-db-panel-footer button,.postgres-status button{height:34px;border:1px solid rgba(42,133,227,.38);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.72);padding:0 14px}.request-flow{display:flex;flex-direction:column}.flow-chain{flex:1;display:grid;grid-template-columns:repeat(6,1fr);gap:14px;align-items:center;padding:18px 0 16px}.flow-chain div{position:relative;min-height:198px;display:grid;align-content:center;justify-items:center;gap:10px;border:1px solid rgba(116,153,200,.34);border-radius:6px;background:linear-gradient(180deg,rgba(23,45,76,.68),rgba(7,22,43,.88));text-align:center}.flow-chain div:not(:last-child)::after{content:'→';position:absolute;right:-13px;top:50%;transform:translateY(-50%);color:#9fb6d3;font-size:18px}.flow-chain i{font-style:normal;color:#cfe2f8;font-size:28px}.flow-chain strong{color:#fff;font-size:12px;line-height:1.35}.flow-chain b{width:17px;height:17px;display:grid;place-items:center;border-radius:50%;color:#06101f;background:#55d97d;font-size:10px}.flow-chain span{color:#dce9f8;font-size:11px;line-height:1.35}.flow-legend{display:flex;align-items:center;gap:24px;padding-top:14px;border-top:1px solid rgba(117,151,194,.15);color:#dce9f8;font-size:12px}.flow-legend span::before{content:'';display:inline-block;width:10px;height:10px;margin-right:7px;border-radius:50%;background:#50d779}.flow-legend .warn::before{background:#ffbd41}.flow-legend .error::before{background:#ff6963}.flow-legend .idle::before{background:#aebbd0}.flow-legend em{margin-left:auto;color:#c9d7eb;font-style:normal}.postgres-status ul{list-style:none;margin:0;padding:0;border:1px solid rgba(117,151,194,.13);border-radius:5px;overflow:hidden}.postgres-status li{min-height:38px;display:grid;grid-template-columns:1fr auto 48px;align-items:center;gap:10px;padding:0 10px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;font-size:12px}.postgres-status li:last-child{border-bottom:0}.postgres-status li span::before{content:'◉';margin-right:8px;color:#bdd0e8;font-size:10px}.postgres-status li strong{font-weight:400;color:#f2f7ff}.postgres-status li b,.db-badge{height:24px;min-width:46px;display:inline-grid;place-items:center;border-radius:5px;font-size:12px;font-weight:500}.postgres-status li b,.db-badge.ok{color:#5fe080;background:rgba(37,204,113,.14);border:1px solid rgba(37,204,113,.22)}.postgres-status button{float:right;margin-top:12px}.db-badge.reject{color:#ff756d;background:rgba(255,91,85,.12);border:1px solid rgba(255,91,85,.42)}.db-badge.duplicate,.db-badge.timeout{color:#ffd05f;background:rgba(255,185,40,.12);border:1px solid rgba(255,185,40,.42)}.backend-errors .backend-db-table td:nth-child(3){font-size:11px;color:#b8c7da}.db-table-summary .backend-db-table td:last-child{text-align:center}
.master-shell.light .backend-db-kpi,.master-shell.light .backend-db-panel{background:rgba(255,255,255,.84);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .backend-db-kpi strong,.master-shell.light .backend-db-panel h3,.master-shell.light .backend-db-table td,.master-shell.light .postgres-status li,.master-shell.light .postgres-status li strong,.master-shell.light .flow-chain strong{color:#102033}.master-shell.light .backend-db-kpi span,.master-shell.light .backend-db-kpi small,.master-shell.light .backend-db-table th,.master-shell.light .flow-chain span,.master-shell.light .flow-legend,.master-shell.light .backend-db-panel-footer{color:#50667f}.master-shell.light .flow-chain div,.master-shell.light .postgres-status ul{background:rgba(246,250,255,.86);border-color:rgba(58,126,204,.24)}

.branch-page{display:grid;gap:12px}.branch-filter-row{display:grid;grid-template-columns:190px 190px 190px 1fr 92px;gap:10px}.branch-filter-row label,.branch-filter-row button{height:38px;border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);color:#dcecff}.branch-filter-row label{display:grid;grid-template-columns:52px 1fr;align-items:center;gap:8px;padding:0 12px}.branch-filter-row label span{color:#93a9c4;font-size:12px}.branch-filter-row button{padding:0 24px 0 12px;text-align:left;font-size:12px}.branch-search{grid-template-columns:1fr 32px!important}.branch-search input{min-width:0;border:0;outline:0;background:transparent;color:#eaf4ff}.branch-reset{padding:0!important;text-align:center!important}.branch-main-grid{display:grid;grid-template-columns:minmax(670px,1.28fr) minmax(470px,.72fr);gap:12px}.branch-side-stack{display:grid;grid-template-rows:auto auto 1fr;gap:12px;min-width:0}.branch-panel{min-width:0;border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.branch-map-panel,.branch-panel{padding:14px}.branch-panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.branch-panel h3,.branch-panel-head h3{margin:0;color:#f2f7ff;font-size:16px}.branch-panel h3 small{color:#91a8c4;font-size:11px;font-weight:500}.branch-map-actions{display:flex;gap:8px}.branch-map-actions button,.branch-panel-head button{height:34px;border:1px solid rgba(42,133,227,.35);border-radius:6px;color:#dcecff;background:rgba(11,29,54,.86);padding:0 14px;font-weight:600}.branch-map-actions .primary,.branch-panel-head .primary{background:linear-gradient(135deg,rgba(20,112,216,.96),rgba(11,75,158,.96));border-color:rgba(70,158,255,.55)}.branch-map-actions .success{background:rgba(37,204,113,.18);border-color:rgba(37,204,113,.36)}.branch-map-stage{position:relative;height:542px;overflow:hidden;border:1px solid rgba(117,151,194,.13);border-radius:6px;background:linear-gradient(rgba(0,15,31,.18),rgba(0,15,31,.45)),url('/korea_road_backmap.png') center / cover no-repeat #061322}.branch-map-stage::after{content:'';position:absolute;inset:0;background:radial-gradient(circle at 55% 42%,rgba(25,126,229,.16),transparent 38%),linear-gradient(90deg,rgba(4,15,32,.45),transparent 35%,rgba(4,15,32,.26));pointer-events:none}.branch-map-legend{position:absolute;z-index:2;display:flex;gap:18px;padding:9px 12px;border:1px solid rgba(117,151,194,.18);border-radius:6px;background:rgba(3,13,28,.68);color:#dce9f8;font-size:12px}.branch-map-legend.top{left:16px;top:18px}.branch-map-legend.bottom{right:18px;bottom:18px;display:grid;gap:8px}.branch-map-legend span::before{content:'';display:inline-block;width:9px;height:9px;margin-right:7px;border-radius:50%;background:#50d779}.branch-map-legend .warn::before{background:#ffcf42}.branch-map-legend .info::before{background:#399bff}.branch-map-legend .caution::before{background:#ff9f43}.branch-map-legend .danger::before{background:#ff645d}.branch-zoom{position:absolute;left:16px;top:210px;z-index:2;display:grid;gap:6px}.branch-zoom button{width:36px;height:36px;border:1px solid rgba(117,151,194,.25);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.78);font-size:18px}.branch-pin{position:absolute;z-index:3;width:13px;height:13px;border-radius:50%;transform:translate(-50%,-50%);background:#50d779;box-shadow:0 0 0 4px rgba(80,215,121,.18),0 0 16px rgba(80,215,121,.55)}.branch-pin.warn{background:#ffcf42;box-shadow:0 0 0 4px rgba(255,207,66,.16),0 0 14px rgba(255,207,66,.5)}.branch-pin.info{background:#399bff;box-shadow:0 0 0 4px rgba(57,155,255,.16),0 0 14px rgba(57,155,255,.5)}.branch-detail dl,.gps-zone-card dl{display:grid;grid-template-columns:120px 1fr;gap:0;margin:0}.branch-detail dt,.branch-detail dd,.gps-zone-card dt,.gps-zone-card dd{min-height:34px;margin:0;padding:6px 8px;border-bottom:1px solid rgba(117,151,194,.1);color:#dce9f8;font-size:13px}.branch-detail dt,.gps-zone-card dt{color:#8fa3bd}.branch-detail dd{font-weight:600}.branch-detail code{float:right;color:#abd2ff;background:rgba(47,140,255,.14);padding:3px 6px;border-radius:4px}.branch-detail dd b{color:#55d779}.branch-detail small{color:#9fb2cb}.branch-badge{min-width:50px;height:24px;display:inline-grid;place-items:center;border-radius:999px;font-size:12px;font-weight:500}.branch-badge.ok{color:#70ee91;background:rgba(37,204,113,.15)}.branch-badge.warn{color:#ffd05f;background:rgba(255,185,40,.14)}.gps-zone-body{display:grid;grid-template-columns:240px 1fr;gap:14px}.gps-zone-map{position:relative;height:154px;border:1px solid rgba(42,133,227,.16);border-radius:6px;background:linear-gradient(rgba(117,151,194,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(117,151,194,.08) 1px,transparent 1px);background-size:24px 24px}.gps-zone-map span{position:absolute;color:#9fb2cb;font-size:11px}.gps-zone-map span:nth-child(1){left:50%;top:6px}.gps-zone-map span:nth-child(2){left:8px;top:50%}.gps-zone-map span:nth-child(3){right:8px;top:50%}.gps-zone-map span:nth-child(4){left:50%;bottom:6px}.gps-zone-map i{position:absolute;left:42px;right:42px;top:42px;bottom:36px;border:2px dashed #1fbf77;border-radius:6px;background:rgba(31,191,119,.08)}.gps-zone-map b{position:absolute;left:50%;top:50%;width:10px;height:10px;border-radius:50%;background:#ffcf42;box-shadow:0 0 12px rgba(255,207,66,.8)}.branch-devices{align-self:stretch}.branch-table{width:100%;border-collapse:collapse;font-size:13px}.branch-table th,.branch-table td{height:34px;padding:0 9px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:left;white-space:nowrap;font-weight:400}.branch-table th{color:#a9bad0;background:rgba(28,49,77,.58);font-weight:600}.branch-history{position:relative}.branch-history button{position:absolute;right:18px;bottom:14px;height:34px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.72);padding:0 14px}
.master-shell.light .branch-filter-row label,.master-shell.light .branch-filter-row button,.master-shell.light .branch-panel{background:rgba(255,255,255,.84);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .branch-panel h3,.master-shell.light .branch-table td,.master-shell.light .branch-detail dd,.master-shell.light .gps-zone-card dd{color:#102033}.master-shell.light .branch-filter-row label span,.master-shell.light .branch-table th,.master-shell.light .branch-detail dt,.master-shell.light .gps-zone-card dt,.master-shell.light .branch-panel h3 small{color:#53677f}.master-shell.light .branch-map-stage{background:linear-gradient(rgba(246,250,255,.1),rgba(246,250,255,.2)),url('/korea_road_backmap.png') center / cover no-repeat #eaf2fb}.master-shell.light .branch-map-legend{background:rgba(255,255,255,.86);border-color:rgba(58,126,204,.26)}

.branch-map-panel{display:flex;flex-direction:column}.branch-map-panel .branch-map-stage{flex:1;height:auto;min-height:542px}.branch-map-legend span::before{display:none}.branch-map-legend span{height:auto!important;min-width:0!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important}.branch-map-legend .ok{color:#70ee91}.branch-map-legend .warn{color:#ffd05f}.branch-map-legend .info{color:#8fc1ff}.branch-map-legend .caution{color:#ffb25f}.branch-map-legend .danger{color:#ff817a}.branch-map-legend.bottom span{display:flex;align-items:center;gap:7px}.branch-map-legend.bottom span::before{content:'';display:inline-block;width:9px;height:9px;margin:0;border-radius:50%;background:#50d779}.branch-map-legend.bottom .warn::before{background:#ffd05f}.branch-map-legend.bottom .caution::before{background:#ff9f43}.branch-map-legend.bottom .danger::before{background:#ff645d}.branch-map-marker,.branch-map-marker.ok,.branch-map-marker.warn,.branch-map-marker.danger{position:absolute;z-index:3;display:flex;align-items:center;gap:7px;height:auto!important;min-width:0!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;transform:translate(-10px,-50%);pointer-events:none}.branch-map-marker i{width:13px;height:13px;display:block;border-radius:50%;background:#50d779;box-shadow:0 0 0 4px rgba(80,215,121,.18),0 0 16px rgba(80,215,121,.55)}.branch-map-marker.warn i{background:#ffcf42;box-shadow:0 0 0 4px rgba(255,207,66,.16),0 0 14px rgba(255,207,66,.5)}.branch-map-marker.danger i{background:#ff645d;box-shadow:0 0 0 4px rgba(255,100,93,.16),0 0 14px rgba(255,100,93,.5)}.branch-map-marker b{min-width:max-content;padding:0!important;border:0!important;border-radius:0!important;color:#eaf4ff;background:transparent!important;font-size:12px;font-weight:600;box-shadow:none!important;text-shadow:0 2px 6px rgba(0,0,0,.9)}.master-shell.light .branch-map-marker b{color:#102033;background:transparent!important;border-color:transparent;text-shadow:0 1px 4px rgba(255,255,255,.85)}

.company-admin-page{display:grid;gap:12px}.company-admin-kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.company-admin-kpi,.company-admin-panel{border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.company-admin-kpi{min-height:96px;display:grid;grid-template-columns:56px 1fr;align-items:center;gap:12px;padding:12px}.company-admin-kpi i{width:50px;height:50px;display:grid;place-items:center;border-radius:50%;color:#fff;font-style:normal;font-weight:900;font-size:21px;background:linear-gradient(135deg,#4da6ff,#1a67cf);box-shadow:0 0 12px rgba(34,124,230,.2)}.company-admin-kpi.ok i{color:#06101f;background:linear-gradient(135deg,#77f4bd,#20a966)}.company-admin-kpi.warn i{color:#06101f;background:linear-gradient(135deg,#ffe16e,#f1a31b)}.company-admin-kpi.muted i{background:linear-gradient(135deg,#9fb2cb,#586a82)}.company-admin-kpi span{color:#e8f2ff;font-size:13px;font-weight:700}.company-admin-kpi strong{display:block;margin-top:5px;color:#fff;font-size:25px;line-height:1.08}.company-admin-kpi small{display:block;margin-top:7px;color:#c6d5e8;font-size:11px}.company-admin-filter-row{display:grid;grid-template-columns:130px 120px 120px 150px 1fr 112px;gap:10px}.company-admin-filter-row button,.company-admin-filter-row label{height:38px;border:1px solid rgba(42,133,227,.32);border-radius:6px;color:#dcecff;background:rgba(5,16,33,.72)}.company-admin-filter-row button{padding:0 24px 0 12px;text-align:left}.company-admin-filter-row .primary{padding:0;text-align:center;background:linear-gradient(135deg,rgba(20,112,216,.96),rgba(11,75,158,.96));border-color:rgba(70,158,255,.55);font-weight:700}.company-admin-filter-row label{display:grid;grid-template-columns:1fr 34px;align-items:center}.company-admin-filter-row input{min-width:0;border:0;background:transparent;color:#eaf4ff;padding-left:12px;outline:0}.company-admin-main-grid{display:grid;grid-template-columns:minmax(760px,1.3fr) minmax(360px,.7fr);gap:12px;align-items:stretch}.company-admin-side{display:grid;grid-template-rows:auto 1fr;gap:12px}.company-admin-panel{min-width:0;padding:14px}.company-panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.company-panel-head h3,.company-admin-panel h3{margin:0;color:#f2f7ff;font-size:16px}.company-panel-head h3 small{color:#91a8c4;font-size:11px;font-weight:500}.company-panel-head div{display:flex;gap:8px}.company-panel-head button,.company-admin-table button,.company-admin-pagination button{height:30px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.72);padding:0 10px}.company-admin-table{width:100%;border-collapse:collapse;font-size:12px}.company-admin-table th,.company-admin-table td{height:38px;padding:0 9px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:left;white-space:nowrap;font-weight:400}.company-admin-table th{height:34px;color:#a9bad0;background:rgba(28,49,77,.58);font-weight:600}.company-admin-table tr.selected{background:rgba(22,103,219,.16);box-shadow:inset 0 0 0 1px rgba(33,130,255,.56)}.company-admin-table td:first-child b{display:block;color:#fff;font-weight:600}.company-admin-table td:first-child small{display:block;margin-top:2px;color:#8fa3bd;font-size:11px}.company-admin-table td:last-child{display:flex;gap:6px;align-items:center}.company-state{min-width:48px;height:23px;display:inline-grid;place-items:center;border-radius:999px;font-size:12px;font-weight:500}.company-state.ok{color:#70ee91;background:rgba(37,204,113,.15)}.company-state.warn,.company-state.caution{color:#ffd05f;background:rgba(255,185,40,.14)}.company-state.danger{color:#ff817a;background:rgba(255,100,93,.14)}.company-admin-pagination{display:grid;grid-template-columns:1fr auto 110px;align-items:center;margin-top:12px;color:#c9d7eb;font-size:12px}.company-admin-pagination div{display:flex;gap:8px}.company-admin-pagination .active{background:rgba(22,103,219,.52);border-color:#1683ff}.company-detail-card dl{display:grid;grid-template-columns:100px 1fr;margin:0}.company-detail-card dt,.company-detail-card dd{min-height:34px;margin:0;padding:7px 8px;border-bottom:1px solid rgba(117,151,194,.1);color:#dce9f8;font-size:13px}.company-detail-card dt{color:#8fa3bd}.company-detail-card dd{font-weight:600}.company-detail-card small{color:#9fb2cb;font-weight:400}.company-detail-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.company-detail-actions button{height:34px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.72)}.company-link-card ul{display:grid;gap:8px;margin:0;padding:0;list-style:none}.company-link-card li{display:grid;grid-template-columns:1fr 92px 74px;align-items:center;gap:8px;min-height:38px;padding:0 10px;border:1px solid rgba(117,151,194,.12);border-radius:5px;color:#dce9f8;background:rgba(6,24,50,.38);font-size:12px}.company-link-card b{color:#8fc1ff;font-weight:500}.company-link-card em{color:#70ee91;font-style:normal}.company-link-card em.warn{color:#ffd05f}.company-admin-bottom-grid{display:grid;grid-template-columns:360px 1fr;gap:12px}.company-permission-summary>div{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.company-permission-summary span{min-height:76px;display:grid;place-items:center;border:1px solid rgba(117,151,194,.13);border-radius:6px;background:rgba(6,24,50,.38)}.company-permission-summary b{color:#91a8c4;font-size:12px}.company-permission-summary strong{color:#fff;font-size:24px}.company-admin-table.compact td,.company-admin-table.compact th{height:32px}
.master-shell.light .company-admin-kpi,.master-shell.light .company-admin-panel,.master-shell.light .company-admin-filter-row button,.master-shell.light .company-admin-filter-row label{background:rgba(255,255,255,.84);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .company-admin-kpi strong,.master-shell.light .company-panel-head h3,.master-shell.light .company-admin-panel h3,.master-shell.light .company-admin-table td,.master-shell.light .company-admin-table td:first-child b,.master-shell.light .company-detail-card dd,.master-shell.light .company-permission-summary strong{color:#102033}.master-shell.light .company-admin-kpi span,.master-shell.light .company-admin-kpi small,.master-shell.light .company-admin-table th,.master-shell.light .company-admin-table td:first-child small,.master-shell.light .company-detail-card dt,.master-shell.light .company-panel-head h3 small,.master-shell.light .company-permission-summary b{color:#53677f}.master-shell.light .company-link-card li,.master-shell.light .company-permission-summary span{background:rgba(246,250,255,.86);border-color:rgba(58,126,204,.24)}

.company-list-panel{display:flex;flex-direction:column}.company-list-panel .company-admin-table{flex:1}.company-list-panel .company-admin-table th,.company-list-panel .company-admin-table td{height:44px}.company-list-panel .company-admin-pagination{margin-top:auto;padding-top:12px}.edge-list-panel .edge-table{flex:1}.edge-list-panel .edge-table th,.edge-list-panel .edge-table td{height:39px}

.audit-log-page{display:grid;gap:12px}.audit-kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.audit-kpi,.audit-panel{border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.audit-kpi{min-height:96px;display:grid;grid-template-columns:56px 1fr;align-items:center;gap:12px;padding:12px}.audit-kpi i{width:50px;height:50px;display:grid;place-items:center;border-radius:50%;color:#fff;font-style:normal;font-weight:900;font-size:21px;background:linear-gradient(135deg,#4da6ff,#1a67cf);box-shadow:0 0 12px rgba(34,124,230,.2)}.audit-kpi.ok i{color:#06101f;background:linear-gradient(135deg,#77f4bd,#20a966)}.audit-kpi.warn i{color:#06101f;background:linear-gradient(135deg,#ffe16e,#f1a31b)}.audit-kpi.info i{background:linear-gradient(135deg,#69b5ff,#2c75d4)}.audit-kpi.danger i{background:linear-gradient(135deg,#ff7b70,#d64640)}.audit-kpi span{color:#e8f2ff;font-size:13px;font-weight:700}.audit-kpi strong{display:block;margin-top:5px;color:#fff;font-size:25px;line-height:1.08}.audit-kpi small{display:block;margin-top:7px;color:#c6d5e8;font-size:11px}.audit-filter-row{display:grid;grid-template-columns:120px 140px 130px 120px 1fr 104px;gap:10px}.audit-filter-row button,.audit-filter-row label{height:38px;border:1px solid rgba(42,133,227,.32);border-radius:6px;color:#dcecff;background:rgba(5,16,33,.72)}.audit-filter-row button{padding:0 24px 0 12px;text-align:left}.audit-filter-row .primary{padding:0;text-align:center;background:linear-gradient(135deg,rgba(20,112,216,.96),rgba(11,75,158,.96));border-color:rgba(70,158,255,.55);font-weight:700}.audit-filter-row label{display:grid;grid-template-columns:1fr 34px;align-items:center}.audit-filter-row input{min-width:0;border:0;background:transparent;color:#eaf4ff;padding-left:12px;outline:0}.audit-main-grid{display:grid;grid-template-columns:minmax(760px,1.28fr) minmax(380px,.72fr);gap:12px;align-items:stretch}.audit-side-stack{display:grid;grid-template-rows:auto 1fr;gap:12px;min-width:0}.audit-panel{min-width:0;padding:14px}.audit-list-panel{display:flex;flex-direction:column}.audit-panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.audit-panel-head h3,.audit-panel h3{margin:0;color:#f2f7ff;font-size:16px}.audit-panel-head h3 small{color:#91a8c4;font-size:11px;font-weight:500}.audit-panel-head button,.audit-pagination button{height:30px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.72);padding:0 10px}.audit-log-table{width:100%;border-collapse:collapse;font-size:12px}.audit-list-panel .audit-log-table{flex:1}.audit-log-table th,.audit-log-table td{height:38px;padding:0 9px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:left;white-space:nowrap;font-weight:400}.audit-list-panel .audit-log-table th,.audit-list-panel .audit-log-table td{height:42px}.audit-log-table th{height:34px;color:#a9bad0;background:rgba(28,49,77,.58);font-weight:600}.audit-log-table tr.selected{background:rgba(22,103,219,.16);box-shadow:inset 0 0 0 1px rgba(33,130,255,.56)}.audit-badge{min-width:48px;height:23px;display:inline-grid;place-items:center;border-radius:5px;font-size:12px;font-weight:500}.audit-badge.ok{color:#70ee91;background:rgba(37,204,113,.15);border:1px solid rgba(37,204,113,.22)}.audit-badge.warn{color:#ffd05f;background:rgba(255,185,40,.14);border:1px solid rgba(255,185,40,.34)}.audit-badge.info{color:#8fc1ff;background:rgba(47,140,255,.14);border:1px solid rgba(47,140,255,.34)}.audit-badge.danger{color:#ff817a;background:rgba(255,100,93,.14);border:1px solid rgba(255,100,93,.34)}.audit-pagination{display:grid;grid-template-columns:1fr auto 110px;align-items:center;margin-top:auto;padding-top:12px;color:#c9d7eb;font-size:12px}.audit-pagination div{display:flex;gap:8px}.audit-pagination .active{background:rgba(22,103,219,.52);border-color:#1683ff}.audit-detail-card dl{display:grid;grid-template-columns:94px 1fr;margin:0}.audit-detail-card dt,.audit-detail-card dd{min-height:34px;margin:0;padding:7px 8px;border-bottom:1px solid rgba(117,151,194,.1);color:#dce9f8;font-size:13px}.audit-detail-card dt{color:#8fa3bd}.audit-detail-card dd{font-weight:600}.audit-detail-card small{color:#9fb2cb;font-weight:400}.audit-risk-score{min-height:82px;display:grid;place-items:center;margin-bottom:12px;border:1px solid rgba(37,204,113,.22);border-radius:6px;background:rgba(37,204,113,.08)}.audit-risk-score strong{color:#70ee91;font-size:28px}.audit-risk-score span{color:#c9d7eb;font-size:12px}.audit-risk-card ul{display:grid;gap:8px;margin:0;padding:0;list-style:none}.audit-risk-card li{display:grid;grid-template-columns:1fr auto;align-items:center;min-height:34px;padding:0 10px;border:1px solid rgba(117,151,194,.12);border-radius:5px;color:#dce9f8;background:rgba(6,24,50,.38);font-size:12px}.audit-risk-card b{color:#70ee91;font-weight:500}.audit-risk-card b.warn{color:#ffd05f}.audit-bottom-grid{display:grid;grid-template-columns:360px 1fr;gap:12px}.audit-bars{display:grid;gap:12px}.audit-bars span{position:relative;height:32px;border:1px solid rgba(117,151,194,.13);border-radius:5px;background:rgba(6,24,50,.38);overflow:hidden}.audit-bars b{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,rgba(42,133,227,.6),rgba(42,133,227,.18))}.audit-bars em{position:relative;z-index:1;display:flex;align-items:center;height:100%;padding-left:10px;color:#eaf4ff;font-style:normal;font-size:12px}.audit-log-table.compact th,.audit-log-table.compact td{height:32px}
.master-shell.light .audit-kpi,.master-shell.light .audit-panel,.master-shell.light .audit-filter-row button,.master-shell.light .audit-filter-row label{background:rgba(255,255,255,.84);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .audit-kpi strong,.master-shell.light .audit-panel h3,.master-shell.light .audit-panel-head h3,.master-shell.light .audit-log-table td,.master-shell.light .audit-detail-card dd,.master-shell.light .audit-bars em{color:#102033}.master-shell.light .audit-kpi span,.master-shell.light .audit-kpi small,.master-shell.light .audit-log-table th,.master-shell.light .audit-detail-card dt,.master-shell.light .audit-panel-head h3 small,.master-shell.light .audit-risk-score span{color:#53677f}.master-shell.light .audit-risk-card li,.master-shell.light .audit-bars span{background:rgba(246,250,255,.86);border-color:rgba(58,126,204,.24)}

.settings-page{display:grid;gap:12px}.settings-kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.settings-kpi,.settings-panel{border:1px solid rgba(42,133,227,.28);border-radius:6px;background:rgba(5,16,33,.72);box-shadow:0 0 0 1px rgba(14,111,219,.08),0 18px 42px rgba(0,0,0,.32);backdrop-filter:blur(16px)}.settings-kpi{min-height:96px;display:grid;grid-template-columns:56px 1fr;align-items:center;gap:12px;padding:12px}.settings-kpi i{width:50px;height:50px;display:grid;place-items:center;border-radius:50%;color:#fff;font-style:normal;font-weight:900;font-size:21px;background:linear-gradient(135deg,#4da6ff,#1a67cf);box-shadow:0 0 12px rgba(34,124,230,.2)}.settings-kpi.ok i{color:#06101f;background:linear-gradient(135deg,#77f4bd,#20a966)}.settings-kpi.warn i{color:#06101f;background:linear-gradient(135deg,#ffe16e,#f1a31b)}.settings-kpi span{color:#e8f2ff;font-size:13px;font-weight:700}.settings-kpi strong{display:block;margin-top:5px;color:#fff;font-size:25px;line-height:1.08}.settings-kpi small{display:block;margin-top:7px;color:#c6d5e8;font-size:11px}.settings-main-grid{display:grid;grid-template-columns:minmax(720px,1.25fr) minmax(380px,.75fr);gap:12px;align-items:stretch}.settings-side-stack{display:grid;grid-template-rows:1fr 1fr;gap:12px;min-width:0}.settings-panel{min-width:0;padding:14px}.settings-panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.settings-panel h3,.settings-panel-head h3{margin:0;color:#f2f7ff;font-size:16px}.settings-panel-head button{height:32px;border:1px solid rgba(42,133,227,.35);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.72);padding:0 12px}.settings-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.settings-form-grid label{min-height:104px;display:grid;align-content:start;gap:8px;padding:12px;border:1px solid rgba(117,151,194,.13);border-radius:6px;background:rgba(6,24,50,.38)}.settings-form-grid span{color:#eaf4ff;font-size:13px;font-weight:700}.settings-form-grid select{height:34px;border:1px solid rgba(42,133,227,.28);border-radius:5px;color:#dcecff;background:rgba(5,18,37,.82);padding:0 10px}.settings-form-grid small{color:#8fa3bd;font-size:12px}.settings-security ul{display:grid;gap:9px;margin:0;padding:0;list-style:none}.settings-security li{display:grid;grid-template-columns:1fr auto 54px;align-items:center;gap:10px;min-height:38px;padding:0 10px;border:1px solid rgba(117,151,194,.12);border-radius:5px;color:#dce9f8;background:rgba(6,24,50,.38);font-size:12px}.settings-security b{font-weight:500;color:#f2f7ff}.settings-security em{height:23px;display:grid;place-items:center;border-radius:999px;color:#70ee91;background:rgba(37,204,113,.15);font-style:normal}.settings-security em.warn{color:#ffd05f;background:rgba(255,185,40,.14)}.settings-backup dl{display:grid;grid-template-columns:120px 1fr;margin:0}.settings-backup dt,.settings-backup dd{min-height:36px;margin:0;padding:7px 8px;border-bottom:1px solid rgba(117,151,194,.1);color:#dce9f8;font-size:13px}.settings-backup dt{color:#8fa3bd}.settings-backup dd{font-weight:600}.settings-bottom-grid{display:grid;grid-template-columns:420px 1fr;gap:12px}.settings-notification>div{display:grid;gap:9px}.settings-notification span{display:grid;grid-template-columns:110px 1fr 42px;align-items:center;gap:10px;min-height:42px;padding:0 10px;border:1px solid rgba(117,151,194,.13);border-radius:5px;background:rgba(6,24,50,.38)}.settings-notification b{color:#eaf4ff;font-size:13px}.settings-notification em{color:#8fa3bd;font-style:normal;font-size:12px}.settings-notification strong{height:23px;display:grid;place-items:center;border-radius:999px;color:#70ee91;background:rgba(37,204,113,.15);font-size:12px}.settings-table{width:100%;border-collapse:collapse;font-size:12px}.settings-table th,.settings-table td{height:34px;padding:0 9px;border-bottom:1px solid rgba(117,151,194,.12);color:#dce9f8;text-align:left;white-space:nowrap;font-weight:400}.settings-table th{color:#a9bad0;background:rgba(28,49,77,.58);font-weight:600}.settings-badge{min-width:48px;height:23px;display:inline-grid;place-items:center;border-radius:999px;font-size:12px;font-weight:500}.settings-badge.ok{color:#70ee91;background:rgba(37,204,113,.15)}.settings-badge.warn{color:#ffd05f;background:rgba(255,185,40,.14)}
.master-shell.light .settings-kpi,.master-shell.light .settings-panel{background:rgba(255,255,255,.84);border-color:rgba(58,126,204,.3);box-shadow:0 12px 30px rgba(49,91,137,.12)}.master-shell.light .settings-kpi strong,.master-shell.light .settings-panel h3,.master-shell.light .settings-panel-head h3,.master-shell.light .settings-form-grid span,.master-shell.light .settings-security b,.master-shell.light .settings-backup dd,.master-shell.light .settings-notification b,.master-shell.light .settings-table td{color:#102033}.master-shell.light .settings-kpi span,.master-shell.light .settings-kpi small,.master-shell.light .settings-form-grid small,.master-shell.light .settings-backup dt,.master-shell.light .settings-notification em,.master-shell.light .settings-table th{color:#53677f}.master-shell.light .settings-form-grid label,.master-shell.light .settings-security li,.master-shell.light .settings-notification span{background:rgba(246,250,255,.86);border-color:rgba(58,126,204,.24)}

.backend-db-page .flow-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  height: auto;
  padding: 0;
  border: 0;
  border-radius: 0;
  color: #dce9f8;
  background: transparent;
  box-shadow: none;
}

.backend-db-page .flow-legend span::before {
  flex: 0 0 10px;
  margin-right: 0;
}

.master-shell.light .backend-db-page .flow-legend span {
  color: #50667f;
}

.postgres-status li.wide-value {
  grid-template-columns: 1fr minmax(160px, auto);
}

.postgres-status li.wide-value strong {
  grid-column: 2 / -1;
  justify-self: stretch;
  text-align: right;
  white-space: nowrap;
}

.backend-errors .db-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  min-width: max-content;
  padding: 0 10px;
  white-space: nowrap;
}

.backend-errors .backend-db-table td:last-child {
  text-align: center;
}

.topbar {
  position: relative;
}

.header-tools .clock {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0;
  white-space: nowrap;
}

.dashboard-pipeline-table {
  table-layout: fixed;
}

.dashboard-pipeline-table td {
  padding: 0 8px;
  text-align: center;
}

.pipeline-table-icon {
  width: 46px;
}

.pipeline-table-name {
  width: 72px;
}

.dashboard-pipeline-table td:nth-child(4),
.dashboard-pipeline-table tr:not(:first-child) td:nth-child(2):not(.pipeline-table-name) {
  text-align: center;
}

.pipeline-spark {
  width: 72px;
  min-width: 72px;
}

.pipeline-spark .chart-js-panel {
  width: 64px;
  margin: 0 auto;
}

.pipeline-table-state {
  width: 132px;
}

.pipeline-table-state b {
  font-size: 15px;
  line-height: 1.2;
}

.pipeline-table-state span {
  font-size: 13px;
}

.alert-list li {
  grid-template-columns: 68px minmax(0, 1fr) 62px;
  min-height: 34px;
}

.alert-list b {
  width: 50px;
  padding: 4px 6px;
  font-size: 11px;
}

.alert-list span {
  font-size: 12px;
}

.alert-list time {
  font-size: 11px;
}

.system-donut-chart {
  position: relative;
  width: 138px;
  height: 138px;
  background: transparent;
}

.system-donut-chart .chart-js-panel {
  position: absolute;
  inset: 0;
}

.system-donut-center {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  text-align: center;
  pointer-events: none;
}

.system-donut-center strong,
.system-donut-center span {
  position: static;
}

.metric-chart .chart-js-panel,
.ingress-chart-grid .chart-js-panel,
.timeline-board .chart-js-panel,
.company-permission-summary .chart-js-panel {
  width: 100%;
}

.metric-chart > .chart-js-panel {
  margin-top: 24px;
}

.timeline-board.chart-timeline {
  padding: 0 8px;
}

.company-permission-summary .permission-stat-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.company-permission-summary .permission-stat-cards span {
  min-height: 52px;
}

.company-permission-summary .permission-stat-cards strong {
  font-size: 20px;
}

@media (max-width: 1439px) {
  .master-shell {
    min-width: 1280px;
  }
}
</style>
