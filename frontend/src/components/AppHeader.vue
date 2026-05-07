<script setup>
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const navLinks = [
  { to: '/company', label: '회사소개' },
  { to: '/solution', label: '솔루션' },
  { to: '/technology', label: '기술스택' },
  { to: '/guide', label: '도입안내' },
  { to: '/contact', label: '문의하기' }
]

const memberName = computed(() => auth.member?.memberName ?? '')
const dashboardRoute = computed(() => auth.isMasterAdmin ? '/master-admin' : '/dashboard')

async function handleLogout() {
  await auth.logout()
  router.push('/')
}
</script>

<template>
  <header class="sticky top-0 z-40 backdrop-blur bg-white/85 border-b border-line">
    <div class="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
      <RouterLink to="/" class="flex items-center gap-2">
        <span class="font-headline text-2xl tracking-wider text-deep">HiFive</span>
        <span class="font-mono text-[10px] text-navy/60 hidden sm:inline">SMART TOLLING</span>
      </RouterLink>

      <nav class="hidden md:flex items-center gap-7 text-sm font-semibold text-navy/80">
        <RouterLink
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="hover:text-brand transition-colors"
          active-class="text-brand"
        >
          {{ link.label }}
        </RouterLink>
        <RouterLink
          v-if="auth.isLoggedIn"
          :to="dashboardRoute"
          class="hover:text-brand transition-colors"
          active-class="text-brand"
        >대시보드</RouterLink>
      </nav>

      <div class="flex items-center gap-2">
        <template v-if="!auth.isLoggedIn">
          <RouterLink to="/login" class="btn-ghost text-sm py-2 px-4">로그인</RouterLink>
          <RouterLink to="/signup" class="btn-primary text-sm py-2 px-4">회원가입</RouterLink>
        </template>
        <template v-else>
          <RouterLink :to="dashboardRoute" class="hidden sm:inline text-sm text-navy/70 hover:text-brand">
            <strong class="text-navy">{{ memberName }}</strong>님
          </RouterLink>
          <button class="btn-ghost text-sm py-2 px-4" @click="handleLogout">로그아웃</button>
        </template>
      </div>
    </div>
  </header>
</template>
