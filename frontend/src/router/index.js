import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { hideAuth: true } },
  { path: '/signup', name: 'signup', component: () => import('@/views/SignupView.vue'), meta: { hideAuth: true } },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { requiresAuth: true, requiresDashboard: true } },
  { path: '/dashboard-compact', name: 'dashboard-compact', component: () => import('@/views/CompactControlDashboardView.vue'), meta: { requiresAuth: true, requiresDashboard: true } },
  { path: '/master-admin', name: 'master-admin', component: () => import('@/views/MasterAdminDashboardView.vue'), meta: { requiresAuth: true, requiresMasterAdmin: true } },
  { path: '/company', name: 'company', component: () => import('@/views/CompanyView.vue') },
  { path: '/solution', name: 'solution', component: () => import('@/views/SolutionView.vue') },
  { path: '/technology', name: 'technology', component: () => import('@/views/TechnologyView.vue') },
  { path: '/guide', name: 'guide', component: () => import('@/views/GuideView.vue') },
  { path: '/contact', name: 'contact', component: () => import('@/views/ContactView.vue') },
  { path: '/preview', name: 'preview', component: () => import('@/views/SubpagePreviewView.vue') },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } }
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  auth.hydrate()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresMasterAdmin && !auth.isMasterAdmin) {
    return { name: 'dashboard' }
  }
  if (to.meta.requiresDashboard && auth.isMasterAdmin && !to.query.center) {
    return { name: 'master-admin' }
  }
  if (to.meta.requiresDashboard && !auth.assignedDashboardId && !(auth.isMasterAdmin && to.query.center)) {
    return { name: 'home' }
  }
  if (to.meta.hideAuth && auth.isLoggedIn) {
    return auth.isMasterAdmin ? { name: 'master-admin' } : { name: 'dashboard' }
  }
})

export default router
