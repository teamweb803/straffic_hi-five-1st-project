<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { adminApi } from '@/api/admin'

const router = useRouter()
const auth = useAuthStore()
const nowText = ref('')
const activeMenu = ref('대시보드')
const memberSubOpen = ref(true)
const activeTab = ref('companies')
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

const kpiCards = [
  { title: '전체 회원사', value: '24', delta: '전일 대비 ▲ 2', tone: 'purple', icon: 'check' },
  { title: '전체 지점(관제센터)', value: '38', delta: '전일 대비 ▲ 1', tone: 'blue', icon: 'square' },
  { title: '오늘 전체 통행', value: '128,456', delta: '전일 대비 ▲ 12.5%', tone: 'green', icon: 'person' },
  { title: '미정산 건수', value: '1,248', delta: '전일 대비 ▼ 5.3%', tone: 'yellow', icon: 'won', deltaTone: 'down' },
  { title: '시스템 상태', value: '정상', delta: '모든 시스템 정상 운영 중', tone: 'cyan', icon: 'diamond' }
]

const filteredCompanies = computed(() => companies.filter((c) => c.name.includes(search.value)))
const filteredMembers = computed(() => members.value.filter((member) => {
  const keyword = search.value.toLowerCase()
  return !keyword || member.email?.toLowerCase().includes(keyword) || member.memberName?.toLowerCase().includes(keyword)
}))
const topCenters = computed(() => centers.slice(0, 5))

function updateTime() {
  const now = new Date()
  const pad = (v) => String(v).padStart(2, '0')
  nowText.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}
function statusClass(s) {
  if (s === '정상') return 'ok'
  if (s === '주의') return 'caution'
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
  if (menu === '회원사 관리') memberSubOpen.value = !memberSubOpen.value
  if (menu === '대시보드') kpiSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  if (menu === '회원사 목록' || menu === '계정 관리' || menu === '권한 관리') {
    activeTab.value = menu === '회원사 목록' ? 'companies' : menu === '계정 관리' ? 'accounts' : 'permissions'
    companySection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  if (menu === '지점(관제센터) 관리') centerSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  if (menu === '단말기 관리' || menu === '시스템 모니터링') mapSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  if (menu === '공지사항' || menu === '감사 로그' || menu === '설정') noticeSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
    <!-- ▼ Background particles -->
    <div class="bg-particles">
      <span v-for="n in 60" :key="n" class="particle" :style="{ left: ((n*37)%100)+'%', top: ((n*53)%100)+'%', animationDelay: (n*0.13)+'s' }"></span>
    </div>

    <!-- ▼ Sidebar -->
    <aside class="sidebar">
      <div class="brand-header">
        <span class="brand-mark">◆</span>
        <div>
          <strong>HI-FIVE<small>Master</small></strong>
          <span>Admin Dashboard</span>
        </div>
      </div>

      <nav class="side-nav">
        <button :class="{ active: activeMenu === '대시보드' }" @click="activateMenu('대시보드')">
          <i class="ico">⌂</i>대시보드
        </button>
        <button class="has-sub" :class="{ active: activeMenu === '회원사 관리' }" @click="activateMenu('회원사 관리')">
          <i class="ico">▤</i>회원사 관리<em>{{ memberSubOpen ? '∧' : '∨' }}</em>
        </button>
        <div v-if="memberSubOpen" class="submenu">
          <button :class="{ active: activeMenu === '회원사 목록' }" @click="activateMenu('회원사 목록')">회원사 목록</button>
          <button :class="{ active: activeMenu === '계정 관리' }" @click="activateMenu('계정 관리')">계정 관리</button>
          <button :class="{ active: activeMenu === '권한 관리' }" @click="activateMenu('권한 관리')">권한 관리</button>
          <button :class="{ active: activeMenu === '요금 정산 관리' }" @click="activateMenu('요금 정산 관리')">요금 정산 관리</button>
        </div>
        <button :class="{ active: activeMenu === '지점(관제센터) 관리' }" @click="activateMenu('지점(관제센터) 관리')">
          <i class="ico">◎</i>지점(관제센터) 관리
        </button>
        <button :class="{ active: activeMenu === '단말기 관리' }" @click="activateMenu('단말기 관리')">
          <i class="ico">▢</i>단말기 관리
        </button>
        <button :class="{ active: activeMenu === '시스템 모니터링' }" @click="activateMenu('시스템 모니터링')">
          <i class="ico">≡</i>시스템 모니터링
        </button>
        <button :class="{ active: activeMenu === '공지사항' }" @click="activateMenu('공지사항')">
          <i class="ico">◇</i>공지사항
        </button>
        <button :class="{ active: activeMenu === '감사 로그' }" @click="activateMenu('감사 로그')">
          <i class="ico">▭</i>감사 로그
        </button>
        <button :class="{ active: activeMenu === '설정' }" @click="activateMenu('설정')">
          <i class="ico">⚙</i>설정
        </button>
      </nav>

      <div class="quick-section">
        <p>빠른 메뉴</p>
        <button class="quick-pill" @click="activateMenu('회원사 목록')">회원사 추가</button>
        <button class="quick-pill" @click="activateMenu('지점(관제센터) 관리')">지점 추가</button>
        <button class="quick-pill" @click="activateMenu('공지사항')">공지사항 등록</button>
        <button class="quick-pill" @click="activateMenu('시스템 모니터링')">시스템 공지</button>
      </div>

      <p class="copyright">© 2025 HI-FIVE All rights reserved.</p>
    </aside>

    <!-- ▼ Content -->
    <div class="content">
      <header class="topbar">
        <div class="top-brand">
          <span class="brand-mark sm">◆</span>
          <strong>HI-FIVE</strong>
          <span class="top-sub">Master Admin Dashboard</span>
        </div>
        <div class="top-right">
          <span class="top-info"><i>⏱</i>{{ nowText }}</span>
          <span class="top-info ok"><i class="dot"></i>시스템 상태 : 정상</span>
          <span class="admin-info">
            <span class="avatar"></span>
            <strong>admin</strong>
            <small>최종 관리자</small>
          </span>
          <button class="top-btn" @click="router.push('/')">홈</button>
          <button class="top-btn" @click="logout">로그아웃</button>
        </div>
      </header>

      <main>
        <!-- ▼ KPI Row -->
        <section ref="kpiSection" class="kpi-row">
          <article v-for="card in kpiCards" :key="card.title" class="kpi-card">
            <div class="kpi-icon" :class="card.tone">
              <span v-if="card.icon === 'check'">✓</span>
              <span v-else-if="card.icon === 'square'">▣</span>
              <span v-else-if="card.icon === 'person'">♟</span>
              <span v-else-if="card.icon === 'won'">₩</span>
              <span v-else-if="card.icon === 'diamond'">◆</span>
            </div>
            <div class="kpi-body">
              <p class="kpi-title">{{ card.title }}</p>
              <strong class="kpi-value">{{ card.value }}</strong>
              <em class="kpi-delta" :class="card.deltaTone || 'up'">{{ card.delta }}</em>
            </div>
          </article>
        </section>

        <!-- ▼ Map + Right stack -->
        <section ref="mapSection" class="map-row">
          <article class="panel map-panel">
            <div class="panel-head">
              <h2><span class="bar"></span>전국 지점 위치 현황</h2>
              <button class="link-btn">위치 편집</button>
            </div>
            <div class="map-body">
              <div class="map-legend">
                <div><span class="dot ok"></span><strong>정상</strong><em>28</em></div>
                <div><span class="dot caution"></span><strong>주의</strong><em>7</em></div>
                <div><span class="dot danger"></span><strong>점검중</strong><em>3</em></div>
              </div>
              <div class="korea-map">
                <button v-for="c in centers" :key="c.name" class="marker" :class="[statusClass(c.status), { selected: selectedCenter === c.name }]" :style="{ left: c.x + '%', top: c.y + '%' }" @click="selectedCenter = c.name">
                  <span class="m-dot"></span>
                  <span class="m-label">
                    <strong>{{ c.name }}</strong>
                    <em :class="statusClass(c.status)">{{ c.status }}</em>
                  </span>
                </button>
                <div class="map-zoom">
                  <button>◎</button>
                  <button>+</button>
                  <button>−</button>
                </div>
              </div>
            </div>
          </article>

          <div class="right-stack">
            <article ref="centerSection" class="panel">
              <div class="panel-head">
                <h2><span class="bar"></span>지점별 실시간 통행 현황 (상위 5)</h2>
              </div>
              <table>
                <thead><tr><th>지점명</th><th>현재 통행</th><th>오늘 통행</th><th>상태</th><th>대시보드</th></tr></thead>
                <tbody>
                  <tr v-for="c in topCenters" :key="c.name">
                    <td>{{ c.name }}</td>
                    <td>{{ c.current.toLocaleString() }}</td>
                    <td>{{ c.today.toLocaleString() }}</td>
                    <td><span class="status" :class="statusClass(c.status)">{{ c.status }}</span></td>
                    <td><button class="enter-btn" @click="enterCenter(c)">진입</button></td>
                  </tr>
                </tbody>
              </table>
            </article>

            <article ref="noticeSection" class="panel">
              <div class="panel-head">
                <h2><span class="bar"></span>시스템 공지사항</h2>
                <button class="link-btn">더보기 ›</button>
              </div>
              <ul class="notice-list">
                <li><span><b>[공지]</b> 시스템 점검 안내 (05/25 00:00 ~ 02:00)</span><time>2025-05-20</time></li>
                <li><span><b>[안내]</b> 요금 정산 시스템 업데이트 완료</span><time>2025-05-19</time></li>
                <li><span><b>[안내]</b> GPS 단말기 펌웨어 업데이트 안내</span><time>2025-05-18</time></li>
                <li><span><b>[공지]</b> 개인정보 처리방침 변경 안내</span><time>2025-05-15</time></li>
              </ul>
            </article>
          </div>
        </section>

        <!-- ▼ Donut + Member tabs -->
        <section ref="companySection" class="company-row">
          <article class="panel donut-panel">
            <div class="panel-head"><h2><span class="bar"></span>회원사 통계</h2></div>
            <div class="donut-wrap">
              <div class="donut">
                <span><strong>24</strong></span>
              </div>
              <ul class="donut-legend">
                <li><i class="ok-bg"></i><span>정상</span><strong>18 (75%)</strong></li>
                <li><i class="caution-bg"></i><span>주의</span><strong>4 (16.7%)</strong></li>
                <li><i class="inactive-bg"></i><span>비활성</span><strong>2 (8.3%)</strong></li>
              </ul>
            </div>
          </article>

          <article class="panel members-panel">
            <div class="tab-bar">
              <button :class="{ active: activeTab === 'companies' }" @click="activeTab = 'companies'">회원사 목록</button>
              <button :class="{ active: activeTab === 'accounts' }" @click="activeTab = 'accounts'">계정 관리</button>
              <button :class="{ active: activeTab === 'permissions' }" @click="activeTab = 'permissions'">권한 관리</button>
              <div class="tab-tools">
                <input v-model.trim="search" class="search-input" type="search" placeholder="회원사명 검색..." />
                <button class="add-btn">회원사 추가</button>
              </div>
            </div>
            <p v-if="memberMessage" class="message">{{ memberMessage }}</p>

            <table v-if="activeTab === 'companies'">
              <thead><tr><th>회원사명</th><th>대표자</th><th>연락처</th><th>이메일</th><th>지점 수</th><th>상태</th><th>관리</th></tr></thead>
              <tbody>
                <tr v-for="c in filteredCompanies" :key="c.email">
                  <td>{{ c.name }}</td>
                  <td>{{ c.owner }}</td>
                  <td>{{ c.phone }}</td>
                  <td>{{ c.email }}</td>
                  <td>{{ c.centers }}</td>
                  <td><span class="status" :class="statusClass(c.status)">{{ c.status }}</span></td>
                  <td><button class="row-btn">수정</button><button class="row-btn">권한</button></td>
                </tr>
                <tr v-if="filteredCompanies.length === 0"><td colspan="7" class="empty">검색 결과가 없습니다.</td></tr>
              </tbody>
            </table>

            <table v-else-if="activeTab === 'accounts'">
              <thead><tr><th>이메일</th><th>이름</th><th>역할</th><th>허용 대시보드</th><th>계정 상태</th><th>관리</th></tr></thead>
              <tbody>
                <tr v-for="m in filteredMembers" :key="m.email">
                  <td>{{ m.email }}</td>
                  <td>{{ m.memberName }}</td>
                  <td>{{ m.role }}</td>
                  <td>{{ m.assignedDashboardId ?? '-' }}</td>
                  <td><span class="status ok">정상</span></td>
                  <td><button class="row-btn">초기화</button><button class="row-btn">수정</button></td>
                </tr>
                <tr v-if="filteredMembers.length === 0"><td colspan="6" class="empty">계정 정보가 없습니다.</td></tr>
              </tbody>
            </table>

            <table v-else>
              <thead><tr><th>회원</th><th>계정 ID</th><th>권한 등급</th><th>접근 가능 지점</th><th>정산 권한</th><th>관리</th></tr></thead>
              <tbody>
                <tr v-for="m in filteredMembers" :key="m.email">
                  <td>{{ m.memberName }}</td>
                  <td>{{ m.email }}</td>
                  <td>{{ m.role }}</td>
                  <td>
                    <select :value="m.assignedDashboardId" @change="assignDashboard(m, $event.target.value)">
                      <option value="">미할당</option>
                      <option v-for="c in centers" :key="c.dashboardId" :value="c.dashboardId">{{ c.name }}</option>
                    </select>
                  </td>
                  <td>{{ m.role === 'MASTER_ADMIN' ? '전체' : '허용' }}</td>
                  <td><button class="row-btn">권한 수정</button></td>
                </tr>
                <tr v-if="filteredMembers.length === 0"><td colspan="6" class="empty">권한 정보가 없습니다.</td></tr>
              </tbody>
            </table>
          </article>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* ===== Shell ===== */
.master-shell{position:relative;min-height:100vh;min-width:1280px;display:grid;grid-template-columns:240px 1fr;color:#dcecff;background:radial-gradient(ellipse at 20% 10%,rgba(56,120,245,.18),transparent 40%),radial-gradient(ellipse at 80% 90%,rgba(120,80,200,.14),transparent 40%),#070b1a;font-family:'Inter','Pretendard',ui-sans-serif,system-ui,-apple-system,sans-serif;font-size:13px;line-height:1.5;overflow-x:hidden}
.bg-particles{position:fixed;inset:0;pointer-events:none;z-index:0}
.particle{position:absolute;width:2px;height:2px;border-radius:50%;background:rgba(180,210,255,.4);box-shadow:0 0 6px rgba(120,180,255,.4);animation:twinkle 4s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}
button,input,select{font:inherit;color:inherit;cursor:pointer}
h1,h2{margin:0;font-weight:600}

/* ===== Sidebar ===== */
.sidebar{position:relative;z-index:2;padding:22px 16px;display:flex;flex-direction:column;gap:18px;background:linear-gradient(180deg,rgba(8,14,32,.92),rgba(8,14,32,.78));border-right:1px solid rgba(56,120,245,.18);min-width:0}
.brand-header{display:flex;align-items:center;gap:12px;padding:6px 8px}
.brand-mark{display:grid;place-items:center;width:34px;height:34px;border:2px solid #38bef5;border-radius:8px;color:#38bef5;font-size:16px;background:rgba(56,190,245,.06);transform:rotate(0deg)}
.brand-mark.sm{width:28px;height:28px;font-size:13px}
.brand-header strong{display:block;font-size:15px;color:#fff;font-weight:700;letter-spacing:.02em}
.brand-header strong small{font-weight:400;color:#8aa6cc;margin-left:4px;font-size:11px}
.brand-header span{display:block;color:#8aa6cc;font-size:11px;letter-spacing:.04em}

.side-nav{display:flex;flex-direction:column;gap:2px}
.side-nav button{display:flex;align-items:center;gap:12px;padding:10px 12px;border:0;background:transparent;color:#a8c4e8;border-radius:8px;text-align:left;font-size:13px;transition:all .15s}
.side-nav button:hover{background:rgba(56,120,245,.08);color:#fff}
.side-nav button.active{background:rgba(56,190,245,.16);color:#fff;font-weight:600;box-shadow:inset 0 0 0 1px rgba(56,190,245,.3)}
.side-nav button .ico{width:18px;display:inline-block;text-align:center;color:#5a7da8;font-size:13px}
.side-nav button.active .ico{color:#38bef5}
.side-nav button.has-sub em{margin-left:auto;font-style:normal;color:#5a7da8;font-size:11px}
.submenu{display:flex;flex-direction:column;gap:1px;margin:2px 0 4px 18px;padding-left:14px;border-left:1px solid rgba(56,120,245,.2)}
.submenu button{padding:7px 12px;font-size:12.5px;color:#88a4cc}
.submenu button.active{background:rgba(56,190,245,.1);color:#38bef5;font-weight:600}

.quick-section{margin-top:8px;padding:14px;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:rgba(8,14,32,.6);display:flex;flex-direction:column;gap:8px}
.quick-section p{margin:0 0 4px;color:#8aa6cc;font-size:11px;letter-spacing:.06em}
.quick-pill{padding:10px;border:1px solid rgba(56,120,245,.22);border-radius:8px;background:rgba(20,36,68,.58);color:#dcecff;font-size:12.5px;text-align:center}
.quick-pill:hover{background:rgba(56,190,245,.18);border-color:rgba(56,190,245,.4)}
.copyright{margin:auto 0 0;color:#5a7da8;font-size:10.5px;text-align:center;padding-top:12px}

/* ===== Topbar ===== */
.content{position:relative;z-index:1;display:flex;flex-direction:column;min-width:0}
.topbar{height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid rgba(56,120,245,.18);background:rgba(8,14,32,.7);backdrop-filter:blur(8px)}
.top-brand{display:flex;align-items:center;gap:10px}
.top-brand strong{font-size:16px;color:#fff;font-weight:700}
.top-sub{color:#a8c4e8;font-size:13px}
.top-right{display:flex;align-items:center;gap:14px}
.top-info{display:inline-flex;align-items:center;gap:6px;color:#a8c4e8;font-size:12.5px}
.top-info i{font-style:normal;color:#5a7da8}
.top-info.ok{color:#7be9b8}
.top-info .dot{width:8px;height:8px;border-radius:50%;background:#33e6a1;box-shadow:0 0 10px #33e6a1}
.admin-info{display:flex;align-items:center;gap:8px;padding-left:14px;border-left:1px solid rgba(56,120,245,.2)}
.avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#5a7da8,#2c4870)}
.admin-info strong{font-size:13px;color:#fff;font-weight:600}
.admin-info small{color:#8aa6cc;font-size:11px}
.top-btn{padding:8px 18px;border:1px solid rgba(56,120,245,.3);border-radius:8px;background:rgba(20,36,68,.58);color:#dcecff;font-size:12.5px}
.top-btn:hover{background:rgba(56,190,245,.18)}

/* ===== Main ===== */
main{padding:22px 24px;display:flex;flex-direction:column;gap:18px;min-width:0}

/* KPI Row */
.kpi-row{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}
.kpi-card{display:flex;align-items:center;gap:16px;padding:18px 20px;border:1px solid rgba(56,120,245,.18);border-radius:12px;background:linear-gradient(145deg,rgba(20,30,58,.7),rgba(12,20,42,.55));backdrop-filter:blur(10px);min-width:0}
.kpi-icon{width:60px;height:60px;flex-shrink:0;border-radius:50%;display:grid;place-items:center;font-size:26px;font-weight:800;color:#fff}
.kpi-icon.purple{background:linear-gradient(135deg,#9264e0,#6d3fb8);box-shadow:0 0 24px rgba(146,100,224,.4)}
.kpi-icon.blue{background:linear-gradient(135deg,#3a78ed,#1f4fbf);box-shadow:0 0 24px rgba(58,120,237,.4)}
.kpi-icon.green{background:linear-gradient(135deg,#33e6a1,#1ba974);box-shadow:0 0 24px rgba(51,230,161,.35)}
.kpi-icon.yellow{background:linear-gradient(135deg,#ffd166,#e0a934);box-shadow:0 0 24px rgba(255,209,102,.35);color:#3a2700}
.kpi-icon.cyan{background:linear-gradient(135deg,#38bef5,#1a8bc4);box-shadow:0 0 24px rgba(56,190,245,.4)}
.kpi-body{flex:1;min-width:0}
.kpi-title{margin:0 0 4px;color:#a8c4e8;font-size:12.5px;font-weight:500}
.kpi-value{display:block;font-size:30px;font-weight:700;color:#fff;letter-spacing:-.01em;line-height:1.1;margin:2px 0 4px}
.kpi-delta{font-size:11.5px;color:#7be9b8;font-style:normal;font-weight:500}
.kpi-delta.down{color:#ff8a9a}

/* Panels */
.panel{border:1px solid rgba(56,120,245,.18);border-radius:12px;background:linear-gradient(145deg,rgba(20,30,58,.7),rgba(12,20,42,.55));backdrop-filter:blur(10px);padding:20px;display:flex;flex-direction:column;gap:14px;min-width:0;overflow:hidden}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px}
.panel-head h2{display:flex;align-items:center;gap:10px;font-size:15px;color:#fff;font-weight:600}
.bar{display:inline-block;width:3px;height:16px;border-radius:2px;background:linear-gradient(180deg,#38bef5,#3a78ed)}
.link-btn{padding:5px 10px;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(20,36,68,.58);color:#a8c4e8;font-size:11.5px}
.link-btn:hover{background:rgba(56,190,245,.18);color:#fff}

/* Map row */
.map-row{display:grid;grid-template-columns:1.42fr 1fr;gap:18px;min-width:0}
.map-panel{min-width:0}
.map-body{display:grid;grid-template-columns:140px 1fr;gap:16px;min-height:540px}
.map-legend{display:flex;flex-direction:column;gap:10px}
.map-legend div{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;padding:12px 14px;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:rgba(8,14,32,.5)}
.map-legend strong{color:#dcecff;font-size:12px;font-weight:500}
.map-legend em{color:#fff;font-size:18px;font-weight:700;font-style:normal}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.dot.ok{background:#33e6a1;box-shadow:0 0 10px #33e6a1}
.dot.caution{background:#ffd166;box-shadow:0 0 10px #ffd166}
.dot.danger{background:#ff5d6c;box-shadow:0 0 10px #ff5d6c}

.korea-map{position:relative;border:1px solid rgba(56,120,245,.18);border-radius:10px;background:radial-gradient(ellipse at 50% 50%,rgba(56,120,245,.12),transparent 60%),linear-gradient(rgba(70,125,255,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(70,125,255,.06) 1px,transparent 1px),#040820;background-size:auto,28px 28px,28px 28px,auto;overflow:hidden}
.korea-map::before{content:'';position:absolute;inset:0;background:url('/korea_road_backmap.png') center/contain no-repeat;opacity:.45;mix-blend-mode:screen;filter:hue-rotate(190deg) brightness(1.2)}
.marker{position:absolute;background:transparent;border:0;padding:0;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;gap:4px;cursor:pointer;z-index:2}
.marker .m-dot{width:12px;height:12px;border-radius:50%;background:#33e6a1;box-shadow:0 0 14px #33e6a1,0 0 0 3px rgba(51,230,161,.18)}
.marker.caution .m-dot{background:#ffd166;box-shadow:0 0 14px #ffd166,0 0 0 3px rgba(255,209,102,.18)}
.marker.danger .m-dot{background:#ff5d6c;box-shadow:0 0 14px #ff5d6c,0 0 0 3px rgba(255,93,108,.18)}
.marker .m-label{padding:5px 10px;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(8,14,32,.85);display:flex;flex-direction:column;align-items:center;gap:1px;backdrop-filter:blur(4px)}
.marker .m-label strong{color:#fff;font-size:11px;font-weight:600;white-space:nowrap}
.marker .m-label em{font-size:10px;font-style:normal;font-weight:600}
.marker.ok em{color:#33e6a1}
.marker.caution em{color:#ffd166}
.marker.danger em{color:#ff5d6c}
.marker.selected{filter:drop-shadow(0 0 12px rgba(56,190,245,.6))}
.map-zoom{position:absolute;left:14px;bottom:14px;display:flex;flex-direction:column;gap:6px;z-index:3}
.map-zoom button{width:32px;height:32px;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(8,14,32,.85);color:#a8c4e8}
.map-zoom button:hover{background:rgba(56,190,245,.2);color:#fff}

.right-stack{display:flex;flex-direction:column;gap:18px;min-width:0}

/* Tables */
table{width:100%;border-collapse:collapse}
thead th{text-align:left;padding:9px 10px;color:#7290b8;font-size:11.5px;font-weight:600;border-bottom:1px solid rgba(56,120,245,.16);background:rgba(8,14,32,.4)}
tbody td{padding:11px 10px;border-bottom:1px solid rgba(56,120,245,.08);color:#dcecff;font-size:12.5px;vertical-align:middle}
tbody tr:hover{background:rgba(56,190,245,.06)}
tbody tr:last-child td{border-bottom:0}
.empty{text-align:center;color:#5a7da8;padding:24px}
.status{display:inline-flex;min-width:48px;justify-content:center;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;background:rgba(255,255,255,.04)}
.status.ok{background:rgba(51,230,161,.14);color:#33e6a1;border:1px solid rgba(51,230,161,.3)}
.status.caution{background:rgba(255,209,102,.14);color:#ffd166;border:1px solid rgba(255,209,102,.3)}
.status.danger{background:rgba(255,93,108,.14);color:#ff5d6c;border:1px solid rgba(255,93,108,.3)}
.enter-btn,.row-btn{padding:5px 14px;border:1px solid rgba(56,120,245,.3);border-radius:6px;background:rgba(20,36,68,.58);color:#a8c4e8;font-size:11.5px;margin-right:4px}
.enter-btn:hover,.row-btn:hover{background:rgba(56,190,245,.2);color:#fff}

/* Notice list */
.notice-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:0}
.notice-list li{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 4px;border-bottom:1px dashed rgba(56,120,245,.12);font-size:13px;color:#dcecff}
.notice-list li:last-child{border-bottom:0}
.notice-list b{color:#38bef5;font-weight:600;margin-right:4px}
.notice-list time{color:#7290b8;font-size:11.5px;white-space:nowrap}

/* Donut */
.company-row{display:grid;grid-template-columns:340px 1fr;gap:18px;min-width:0}
.donut-wrap{display:flex;align-items:center;gap:18px;padding:8px 4px}
.donut{position:relative;width:160px;height:160px;border-radius:50%;background:conic-gradient(#33e6a1 0 75%,#ffd166 75% 91.7%,#5a7da8 91.7% 100%);display:grid;place-items:center;flex-shrink:0}
.donut::before{content:'';position:absolute;inset:18px;border-radius:50%;background:linear-gradient(145deg,rgba(20,30,58,.95),rgba(12,20,42,.95))}
.donut span{position:relative;z-index:1;display:grid;place-items:center;color:#fff}
.donut strong{font-size:32px;font-weight:700}
.donut-legend{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px;flex:1;min-width:0}
.donut-legend li{display:grid;grid-template-columns:14px 1fr auto;align-items:center;gap:10px;font-size:12.5px;color:#a8c4e8}
.donut-legend strong{color:#fff;font-weight:600}
.donut-legend i{width:10px;height:10px;border-radius:50%;display:inline-block}
.ok-bg{background:#33e6a1}.caution-bg{background:#ffd166}.inactive-bg{background:#5a7da8}

/* Members panel */
.members-panel{padding:0;overflow:hidden}
.tab-bar{display:flex;align-items:center;gap:0;padding:0 0 0 16px;border-bottom:1px solid rgba(56,120,245,.18)}
.tab-bar button{padding:14px 18px;border:0;background:transparent;color:#7290b8;font-size:13px;font-weight:500;border-bottom:2px solid transparent;margin-bottom:-1px}
.tab-bar button.active{color:#38bef5;border-bottom-color:#38bef5;font-weight:600}
.tab-tools{margin-left:auto;display:flex;align-items:center;gap:10px;padding:10px 16px}
.search-input{width:240px;padding:8px 12px;border:1px solid rgba(56,120,245,.22);border-radius:8px;background:rgba(8,14,32,.5);color:#fff;font-size:12.5px}
.search-input:focus{outline:0;border-color:#38bef5}
.add-btn{padding:8px 16px;border:1px solid rgba(56,190,245,.4);border-radius:8px;background:linear-gradient(135deg,#1b3be8,#38bef5);color:#fff;font-size:12.5px;font-weight:600}
.add-btn:hover{filter:brightness(1.08)}
.message{margin:0;padding:12px 18px;color:#ff8a9a;font-size:12.5px;background:rgba(255,93,108,.08);border-bottom:1px solid rgba(255,93,108,.18)}
.members-panel table{padding:0 0}
.members-panel thead th{padding:11px 16px}
.members-panel tbody td{padding:13px 16px}
select{padding:5px 10px;border:1px solid rgba(56,120,245,.22);border-radius:6px;background:rgba(8,14,32,.6);color:#dcecff;font-size:12px}
</style>
