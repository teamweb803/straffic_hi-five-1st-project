<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ memberId: '', password: '' })
const message = ref(null)
const messageType = ref('error')

async function handleSubmit() {
  message.value = null
  if (!form.memberId || !form.password) {
    message.value = '아이디와 비밀번호를 입력해 주세요.'
    messageType.value = 'error'
    return
  }
  const result = await auth.login(form)
  if (result.ok) {
    const redirect = route.query.redirect ?? '/dashboard'
    router.push(redirect)
  } else {
    message.value = result.message
    messageType.value = 'error'
  }
}
</script>

<template>
  <section class="min-h-[80vh] flex items-center justify-center bg-cloud px-6 py-16">
    <div class="w-full max-w-md card shadow-sm">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">SIGN IN</p>
      <h1 class="font-headline text-3xl mt-2 text-deep">WELCOME BACK.</h1>
      <p class="text-sm text-navy/70 mt-2">HiFive 관제 대시보드에 접속합니다.</p>

      <form class="mt-8 space-y-4" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">아이디</label>
          <input v-model="form.memberId" type="text" autocomplete="username" class="input-field" placeholder="member_id" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">비밀번호</label>
          <input v-model="form.password" type="password" autocomplete="current-password" class="input-field" placeholder="••••••••" />
        </div>

        <p
          v-if="message"
          class="text-sm"
          :class="messageType === 'error' ? 'text-red-500' : 'text-emerald-600'"
        >{{ message }}</p>

        <button type="submit" class="btn-primary w-full" :disabled="auth.loading">
          {{ auth.loading ? '로그인 중...' : '로그인' }}
        </button>
      </form>

      <div class="mt-6 text-sm text-navy/70 flex justify-between">
        <RouterLink to="/" class="hover:text-brand">← 메인으로</RouterLink>
        <RouterLink to="/signup" class="hover:text-brand">회원가입 →</RouterLink>
      </div>
    </div>
  </section>
</template>
