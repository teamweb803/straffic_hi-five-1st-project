<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { adminApi } from '@/api/admin'

const router = useRouter()
const auth = useAuthStore()
const nowText = ref('')
const activeMenu = ref('대시보드')
const activeTab = ref('members')
const selectedCenter = ref('서울 톨게이트')
const search = ref('')
const members = ref([])
const memberMessage = ref('')
const kpiSection = ref(null)
const mapSection = ref(null)
const centerSection = ref(null)
const noticeSection = ref(null)
const companySection = ref(null)
let timer = null

const centers = [
  { name: '서울 톨게이트', current: 1248, today: 12456, status: '정상', x: 48, y: 24, dashboardId: 'SEOUL-TOLL' },
  { name: '수원 톨게이트', current: 987, today: 9876, status: '정상', x: 44, y: 34, dashboardId: 'SUWON-TOLL' },
  { name: '대전 톨게이트', current: 765, today: 7654, status: '주의', x: 48, y: 49, dashboardId: 'DAEJEON-TOLL' },
  { name: '대구 톨게이트', current: 532, today: 5321, status: '점검중', x: 62, y: 60, dashboardId: 'DAEGU-TOLL' },
  { name: '부산 톨게이트', current: 1102, today: 11023, status: '정상', x: 68, y: 78, dashboardId: 'BUSAN-TOLL' },
  { name: '광주 톨게이트', current: 624, today: 6120, status: '정상', x: 38, y: 69, dashboardId: 'GWANGJU-TOLL' },
  { name: '강릉 톨게이트', current: 410, today: 4320, status: '정상', x: 69, y: 27, dashboardId: 'GANGNEUNG-TOLL' },
  { name: '제주 톨게이트', current: 302, today: 2210, status: '정상', x: 37, y: 90, dashboardId: 'JEJU-TOLL' }
]

const companies = [
  { name: '하이패스 서울(주)', owner: '김서울', phone: '02-1234-5678', email: 'seoul@hipass.com', centers: 5, status: '정상' },
  { name: '수원 하이패스(주)', owner: '이수원', phone: '031-234-5678', email: 'suwon@hipass.com', centers: 4, status: '정상' },
  { name: '대전 하이패스(주)', owner: '박대전', phone: '042-345-6789', email: 'daejeon@hipass.com', centers: 3, status: '주의' },
  { name: '대구 하이패스(주)', owner: '최대구', phone: '053-456-7890', email: 'daegu@hipass.com', centers: 4, status: '정상' },
  { name: '부산 하이패스(주)', owner: '정부산', phone: '051-567-8901', email: 'busan@hipass.com', centers: 6, status: '정상' }
]

const filteredCompanies = computed(() => companies.filter((company) => company.name.includes(search.value)))
const filteredMembers = computed(() => members.value.filter((member) => {
  const keyword = search.value.toLowerCase()
  return !keyword || member.email?.toLowerCase().includes(keyword) || member.memberName?.toLowerCase().includes(keyword)
}))
const topCenters = computed(() => centers.slice(0, 5))

function updateTime() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function statusClass(status) {
  if (status === '정상') return 'ok'
  if (status === '주의') return 'caution'
  return 'danger'
}

async function fetchMembers() {
  const { data } = await adminApi.members()
  members.value = data
}

async function assignDashboard(member, dashboardId) {
  const { data } = await adminApi.assignDashboard(member.email, dashboardId)
  members.value = members.value.map((item) => item.email === data.email ? data : item)
  memberMessage.value = `${data.memberName} 회원을 ${dashboardId || '미할당'} 대시보드에 연결했습니다.`
}

function enterCenter(center) {
  selectedCenter.value = center.name
  router.push({ path: '/dashboard', query: { center: center.dashboardId } })
}

function activateMenu(menu) {
  activeMenu.value = menu
  if (menu === '대시보드') {
    kpiSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  if (menu === '회원사 관리') {
    activeTab.value = 'companies'
    companySection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  if (menu === '지점(관제센터) 관리') {
    centerSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  if (menu === '단말기 관리' || menu === '시스템 모니터링') {
    mapSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  if (menu === '공지사항' || menu === '감사 로그' || menu === '설정') {
    noticeSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function logout() {
  auth.logout().finally(() => router.push('/'))
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  fetchMembers().catch(() => {
    memberMessage.value = '회원 목록을 불러오지 못했습니다. admin 계정으로 로그인했는지 확인해 주세요.'
  })
})

onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="master-shell">
    <aside class="sidebar glass">
      <div class="sidebar-brand">
        <div class="logo-mark">H5</div>
        <div><strong>HI-FIVE</strong><span>Master Console</span></div>
      </div>
      <nav class="sidebar-nav">
        <button v-for="menu in ['대시보드','회원사 관리','지점(관제센터) 관리','단말기 관리','시스템 모니터링','공지사항','감사 로그','설정']" :key="menu" :class="{ active: activeMenu === menu }" @click="activateMenu(menu)">{{ menu }}</button>
      </nav>
      <div class="quick-menu">
        <p>빠른 메뉴</p>
        <button @click="activateMenu('회원사 관리')">회원사 추가</button>
        <button @click="activateMenu('지점(관제센터) 관리')">지점 추가</button>
        <button @click="activateMenu('공지사항')">공지사항 등록</button>
        <button @click="activateMenu('시스템 모니터링')">시스템 공지</button>
      </div>
    </aside>

    <div class="content-shell">
      <header class="topbar glass">
        <div><p class="eyebrow">HI-FIVE</p><h1>Master Admin Dashboard</h1></div>
        <div class="header-tools">
          <span class="pill">{{ nowText }}</span>
          <span class="pill ok"><i></i>시스템 상태: 정상</span>
          <span class="pill">최종 관리자: <strong>{{ auth.member?.memberName ?? 'admin' }}</strong></span>
          <button class="home-btn" @click="router.push('/')">홈으로</button>
          <button class="logout-btn" @click="logout">로그아웃</button>
        </div>
      </header>

      <main>
        <section ref="kpiSection" class="kpi-grid">
          <article class="kpi glass"><span class="icon">CO</span><p>전체 회원사</p><strong>24</strong><em>+2 전월 대비</em></article>
          <article class="kpi glass"><span class="icon">CT</span><p>전체 지점(관제센터)</p><strong>38</strong><em>+4 전월 대비</em></article>
          <article class="kpi glass"><span class="icon">TR</span><p>오늘 전체 통행</p><strong>128,456</strong><em>+8.7%</em></article>
          <article class="kpi glass"><span class="icon warn">₩</span><p>미정산 건수</p><strong>1,248</strong><em class="down">-3.2%</em></article>
          <article class="kpi glass"><span class="icon status-ok">OK</span><p>시스템 상태</p><strong>정상</strong><em>99.9% uptime</em></article>
        </section>

        <section ref="mapSection" class="main-grid">
          <article class="map-panel glass">
            <div class="panel-head"><div><p class="eyebrow">NATIONWIDE MAP</p><h2>전국 지점 위치 현황</h2></div><div class="map-tools"><button>+</button><button>-</button></div></div>
            <div class="map-body">
              <div class="state-summary"><div><span class="dot ok"></span><strong>28</strong><p>정상</p></div><div><span class="dot caution"></span><strong>7</strong><p>주의</p></div><div><span class="dot danger"></span><strong>3</strong><p>점검중</p></div></div>
              <div class="korea-map">
                <button v-for="center in centers" :key="center.name" class="marker" :class="[statusClass(center.status), { selected: selectedCenter === center.name }]" :style="{ left: center.x + '%', top: center.y + '%' }" @click="selectedCenter = center.name"><span>{{ center.name }}</span></button>
              </div>
            </div>
          </article>

          <div class="right-stack">
            <article ref="centerSection" class="glass panel">
              <div class="panel-head"><div><p class="eyebrow">TOP 5 CENTER</p><h2>지점별 실시간 통행 현황 상위 5</h2></div></div>
              <table><thead><tr><th>지점명</th><th>현재 통행</th><th>오늘 통행</th><th>상태</th><th>대시보드</th></tr></thead>
                <tbody><tr v-for="center in topCenters" :key="center.name" :class="{ selected: selectedCenter === center.name }"><td>{{ center.name }}</td><td>{{ center.current.toLocaleString() }}</td><td>{{ center.today.toLocaleString() }}</td><td><span class="status" :class="statusClass(center.status)">{{ center.status }}</span></td><td><button class="small-btn" @click="enterCenter(center)">진입</button></td></tr></tbody>
              </table>
            </article>
            <article ref="noticeSection" class="glass panel">
              <div class="panel-head"><div><p class="eyebrow">NOTICE</p><h2>시스템 공지사항</h2></div><button class="ghost-btn">더보기</button></div>
              <ul class="notice-list"><li><span>[공지] 시스템 점검 안내 (05/25 00:00 ~ 02:00)</span><time>05/20</time></li><li><span>[안내] 요금 정산 시스템 업데이트 완료</span><time>05/18</time></li><li><span>[안내] GPS 단말기 펌웨어 업데이트 안내</span><time>05/16</time></li><li><span>[공지] 개인정보 처리방침 변경 안내</span><time>05/12</time></li></ul>
            </article>
          </div>
        </section>

        <section ref="companySection" class="company-grid">
          <article class="glass panel donut-panel">
            <div class="panel-head"><div><p class="eyebrow">COMPANY STATUS</p><h2>회원사 통계</h2></div></div>
            <div class="donut-wrap"><div class="donut"><span>24<small>전체</small></span></div><div class="legend"><p><i class="ok-bg"></i>정상 <strong>18</strong></p><p><i class="caution-bg"></i>주의 <strong>4</strong></p><p><i class="inactive-bg"></i>비활성 <strong>2</strong></p></div></div>
          </article>

          <article class="glass panel company-panel">
            <div class="panel-head"><div><p class="eyebrow">MEMBER ADMIN</p><h2>회원 및 대시보드 연결 관리</h2></div><input v-model.trim="search" class="search-input" type="search" placeholder="회원사명, 이름, 이메일 검색" /></div>
            <div class="tab-row"><button :class="{ active: activeTab === 'companies' }" @click="activeTab = 'companies'">회원사 목록</button><button :class="{ active: activeTab === 'accounts' }" @click="activeTab = 'accounts'">계정 관리</button><button :class="{ active: activeTab === 'permissions' }" @click="activeTab = 'permissions'">권한 관리</button></div>
            <p v-if="memberMessage" class="message">{{ memberMessage }}</p>
            <table v-if="activeTab === 'companies'"><thead><tr><th>회원사명</th><th>대표자</th><th>연락처</th><th>이메일</th><th>지점 수</th><th>상태</th><th>관리</th></tr></thead><tbody><tr v-for="company in filteredCompanies" :key="company.email"><td>{{ company.name }}</td><td>{{ company.owner }}</td><td>{{ company.phone }}</td><td>{{ company.email }}</td><td>{{ company.centers }}</td><td><span class="status" :class="statusClass(company.status)">{{ company.status }}</span></td><td><button class="small-btn" @click="alert('회원사 정보가 수정되었습니다.')">수정</button><button class="small-btn" @click="alert('권한 정보가 저장되었습니다.')">권한</button></td></tr></tbody></table>
            <table v-else-if="activeTab === 'accounts'"><thead><tr><th>이메일</th><th>이름</th><th>역할</th><th>허용 대시보드</th><th>계정 상태</th><th>관리</th></tr></thead><tbody><tr v-for="member in filteredMembers" :key="member.email"><td>{{ member.email }}</td><td>{{ member.memberName }}</td><td>{{ member.role }}</td><td>{{ member.assignedDashboardId ?? '-' }}</td><td><span class="status ok">정상</span></td><td><button class="small-btn">비밀번호 초기화</button><button class="small-btn">수정</button><button class="small-btn">잠금</button></td></tr></tbody></table>
            <table v-else><thead><tr><th>회원</th><th>계정 ID</th><th>권한 등급</th><th>접근 가능 지점</th><th>정산 권한</th><th>관리</th></tr></thead><tbody><tr v-for="member in filteredMembers" :key="member.email"><td>{{ member.memberName }}</td><td>{{ member.email }}</td><td>{{ member.role }}</td><td><select :value="member.assignedDashboardId" @change="assignDashboard(member, $event.target.value)"><option value="">미할당</option><option v-for="center in centers" :key="center.dashboardId" :value="center.dashboardId">{{ center.name }}</option></select></td><td>{{ member.role === 'MASTER_ADMIN' ? '전체' : '허용' }}</td><td><button class="small-btn" @click="alert('권한 정보가 저장되었습니다.')">권한 수정</button></td></tr></tbody></table>
          </article>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.master-shell{min-height:100vh;min-width:1280px;display:grid;grid-template-columns:280px 1fr;gap:22px;padding:22px;color:#eaf4ff;background:radial-gradient(circle at 15% 8%,rgba(56,190,245,.14),transparent 28%),linear-gradient(135deg,#030711,#07142a 52%,#030711)}
.glass{border:1px solid rgba(79,171,255,.22);border-radius:18px;background:linear-gradient(145deg,rgba(13,24,49,.8),rgba(8,16,35,.58));box-shadow:0 18px 60px rgba(0,0,0,.32);backdrop-filter:blur(18px)}button,input,select{font:inherit}.sidebar{padding:20px;display:flex;flex-direction:column}.sidebar-brand{display:flex;align-items:center;gap:14px}.logo-mark,.icon{display:grid;place-items:center;border-radius:14px;background:#38bef5;color:#06111f;font-weight:900}.logo-mark{width:48px;height:48px}.sidebar-brand span{display:block;color:#8ca5c8;font-size:12px}.sidebar-nav{display:grid;gap:8px;margin-top:26px}.sidebar-nav button,.quick-menu button,.logout-btn,.home-btn,.small-btn,.ghost-btn,.tab-row button,.map-tools button{border:1px solid rgba(79,171,255,.22);border-radius:10px;background:rgba(7,15,31,.56);color:#dcecff;cursor:pointer}.sidebar-nav button{padding:12px;text-align:left}.sidebar-nav button.active,.tab-row button.active,.small-btn:hover,.home-btn:hover{background:rgba(56,190,245,.18);box-shadow:0 0 18px rgba(56,190,245,.2)}.quick-menu{margin-top:auto;display:grid;gap:8px}.quick-menu p{color:#38bef5;font-size:12px;font-weight:800}.quick-menu button{padding:10px}.topbar{height:82px;display:flex;align-items:center;justify-content:space-between;padding:0 22px}.eyebrow{margin:0 0 5px;color:#38bef5;font-size:11px;font-weight:800;letter-spacing:.22em}h1,h2{margin:0}.header-tools{display:flex;align-items:center;gap:10px}.pill{display:inline-flex;align-items:center;gap:8px;padding:9px 12px;border:1px solid rgba(115,179,255,.2);border-radius:999px;background:rgba(7,15,31,.72);font-size:13px}.pill i,.dot{width:8px;height:8px;border-radius:50%;background:#33e6a1}.logout-btn,.home-btn{height:36px;padding:0 14px}.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-top:18px}.kpi{padding:18px}.icon{width:42px;height:42px}.icon.warn{background:#ffd166}.icon.ok{background:#33e6a1}.kpi p{color:#8ca5c8;font-size:12px}.kpi strong{display:block;font-size:28px}.kpi em{color:#33e6a1;font-size:12px}.kpi em.down{color:#ff5d6c}.main-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:18px;margin-top:18px}.panel,.map-panel{padding:20px}.panel-head{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.map-body{display:grid;grid-template-columns:120px 1fr;gap:16px}.state-summary{display:grid;gap:10px}.state-summary div{padding:12px;border-radius:12px;background:rgba(3,10,24,.42)}.state-summary strong{display:block;font-size:22px}.state-summary p{margin:2px 0 0;color:#8ca5c8;font-size:12px}.korea-map{position:relative;height:430px;border:1px solid rgba(79,171,255,.14);border-radius:16px;background:linear-gradient(rgba(70,125,255,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(70,125,255,.1) 1px,transparent 1px),#061326;background-size:30px 30px}.map-shape.main{position:absolute;left:33%;top:8%;width:34%;height:76%;border-radius:48% 38% 44% 34%;background:rgba(56,190,245,.08);border:1px solid rgba(56,190,245,.22);transform:rotate(-12deg)}.map-shape.jeju{position:absolute;left:32%;top:88%;width:18%;height:6%;border-radius:50%;background:rgba(56,190,245,.08);border:1px solid rgba(56,190,245,.22)}.marker{position:absolute;width:14px;height:14px;border-radius:50%;transform:translate(-50%,-50%);border:0}.marker span{position:absolute;left:16px;top:-6px;white-space:nowrap;font-size:11px;color:#cfe5ff}.marker.selected{box-shadow:0 0 0 8px rgba(56,190,245,.18)}.ok,.marker.ok{color:#33e6a1!important;background:#33e6a1}.caution,.marker.caution{color:#ffd166!important;background:#ffd166}.danger,.marker.danger{color:#ff5d6c!important;background:#ff5d6c}.right-stack{display:grid;gap:18px}table{width:100%;border-collapse:collapse;background:rgba(2,9,22,.22);border-radius:14px;overflow:hidden}th,td{padding:12px;border-bottom:1px solid rgba(137,181,230,.08);text-align:left;font-size:13px}th{color:#7294bd;font-size:11px;letter-spacing:.12em}tr.selected{background:rgba(56,190,245,.14)}.status{display:inline-flex;padding:5px 8px;border-radius:999px;background:rgba(255,255,255,.06);font-size:11px;font-weight:900}.small-btn{height:30px;margin-right:6px;padding:0 10px}.notice-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}.notice-list li{display:flex;justify-content:space-between;color:#cfe5ff;font-size:13px}.notice-list time{color:#8ca5c8}.company-grid{display:grid;grid-template-columns:330px 1fr;gap:18px;margin-top:18px}.donut-wrap{display:flex;align-items:center;gap:22px}.donut{width:160px;height:160px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#33e6a1 0 75%,#ffd166 75% 91%,#4f5d75 91% 100%)}.donut span{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;background:#07142a;font-size:30px;font-weight:900}.donut small{display:block;font-size:12px;color:#8ca5c8}.legend p{display:flex;gap:8px;align-items:center}.legend i{width:10px;height:10px;border-radius:50%}.ok-bg{background:#33e6a1}.caution-bg{background:#ffd166}.inactive-bg{background:#4f5d75}.search-input{height:38px;min-width:260px;padding:0 12px;border-radius:10px;border:1px solid rgba(79,171,255,.22);background:rgba(7,15,31,.56);color:#fff}.tab-row{display:flex;gap:8px;margin-bottom:14px}.tab-row button{height:34px;padding:0 12px}.message{color:#8ca5c8;font-size:13px}select{height:32px;border-radius:8px;background:#07142a;color:#eaf4ff;border:1px solid rgba(79,171,255,.3)}
.header-tools .pill{color:#dcecff!important}
.header-tools .pill.ok{color:#33e6a1!important;background:rgba(51,230,161,.1)}
.icon.status-ok{background:#33e6a1!important;color:#06111f!important}
.kpi .icon.status-ok{color:#06111f!important}
.status.ok{background:rgba(51,230,161,.1);color:#33e6a1!important}
.status.caution{background:rgba(255,209,102,.12);color:#ffd166!important}
.status.danger{background:rgba(255,93,108,.12);color:#ff5d6c!important}
.korea-map{
  background:
    linear-gradient(rgba(6,19,38,.16),rgba(6,19,38,.72)),
    url('/korea_road_backmap.png'),
    #061326 !important;
  background-position:center !important;
  background-size:cover,contain,auto !important;
  background-repeat:no-repeat,no-repeat,no-repeat !important;
}
</style>
