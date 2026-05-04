<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const headerEl = ref(null)
const isLoggedIn = computed(() => auth.isLoggedIn)
const memberName = computed(() => auth.member?.memberName ?? '')

let onScroll = null
onMounted(() => {
  onScroll = () => headerEl.value?.classList.toggle('is-scrolled', window.scrollY > 12)
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})
onBeforeUnmount(() => {
  if (onScroll) window.removeEventListener('scroll', onScroll)
})

async function handleLogout() {
  await auth.logout()
  router.push('/')
}
</script>

<template>
  <header ref="headerEl" class="site-header" id="siteHeader">
    <div class="header-inner">
      <RouterLink class="logo" to="/" aria-label="HiFive 홈">HiFive</RouterLink>
      <nav class="nav" aria-label="주요 메뉴">
        <RouterLink to="/company">회사소개</RouterLink>
        <RouterLink to="/solution">솔루션</RouterLink>
        <RouterLink to="/technology">기술</RouterLink>
        <RouterLink to="/guide">도입안내</RouterLink>
        <RouterLink to="/contact">문의</RouterLink>
      </nav>
      <div class="auth">
        <template v-if="!isLoggedIn">
          <RouterLink class="btn" to="/login">로그인</RouterLink>
          <RouterLink class="btn primary" to="/signup">회원가입</RouterLink>
        </template>
        <template v-else>
          <RouterLink class="btn primary" to="/dashboard">{{ memberName || '대시보드' }}</RouterLink>
          <button class="btn" type="button" @click="handleLogout">로그아웃</button>
        </template>
      </div>
    </div>
  </header>
</template>
