import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { hideAuth: true } },
  { path: '/signup', name: 'signup', component: () => import('@/views/SignupView.vue'), meta: { hideAuth: true } },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { requiresAuth: true } },
  { path: '/company', name: 'company', component: () => import('@/views/CompanyView.vue') },
  { path: '/solution', name: 'solution', component: () => import('@/views/SolutionView.vue') },
  { path: '/technology', name: 'technology', component: () => import('@/views/TechnologyView.vue') },
  { path: '/guide', name: 'guide', component: () => import('@/views/GuideView.vue') },
  { path: '/contact', name: 'contact', component: () => import('@/views/ContactView.vue') },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } }
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.hideAuth && auth.isLoggedIn) {
    return { name: 'home' }
  }
})

export default router
