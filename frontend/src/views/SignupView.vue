<script setup>
import { reactive, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const form = reactive({
  email: '',
  password: '',
  passwordConfirm: '',
  memberName: '',
  plateNumber: ''
})
const message = ref(null)
const messageType = ref('error')

async function handleSubmit() {
  message.value = null
  if (!form.email || !form.password || !form.memberName) {
    message.value = '이메일, 비밀번호, 이름을 모두 입력해 주세요.'
    messageType.value = 'error'
    return
  }
  if (form.password.length < 6) {
    message.value = '비밀번호는 6자 이상이어야 합니다.'
    messageType.value = 'error'
    return
  }
  if (form.password !== form.passwordConfirm) {
    message.value = '비밀번호 확인이 일치하지 않습니다.'
    messageType.value = 'error'
    return
  }

  const { passwordConfirm, ...payload } = form
  const result = await auth.signUp(payload)
  if (result.ok) {
    message.value = '회원가입이 완료되었습니다. 로그인 페이지로 이동합니다.'
    messageType.value = 'success'
    setTimeout(() => router.push('/login'), 800)
  } else {
    message.value = result.message
    messageType.value = 'error'
  }
}
</script>

<template>
  <section class="min-h-[80vh] flex items-center justify-center bg-cloud px-6 py-16">
    <div class="w-full max-w-lg card shadow-sm">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">CREATE ACCOUNT</p>
      <h1 class="font-headline text-3xl mt-2 text-deep">JOIN HI-FIVE.</h1>
      <p class="text-sm text-navy/70 mt-2">이메일 계정으로 회원가입 후 허용된 관제 대시보드에 접속합니다.</p>

      <form class="mt-8 grid sm:grid-cols-2 gap-4" @submit.prevent="handleSubmit">
        <div class="sm:col-span-2">
          <label class="block text-xs font-semibold text-navy/70 mb-1">이메일 *</label>
          <input v-model.trim="form.email" type="email" class="input-field" placeholder="user@company.com" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">비밀번호 *</label>
          <input v-model="form.password" type="password" class="input-field" placeholder="6자 이상" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">비밀번호 확인 *</label>
          <input v-model="form.passwordConfirm" type="password" class="input-field" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">이름 *</label>
          <input v-model.trim="form.memberName" type="text" class="input-field" placeholder="홍길동" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">차량번호</label>
          <input v-model.trim="form.plateNumber" type="text" class="input-field" placeholder="12가3456" />
        </div>

        <p
          v-if="message"
          class="sm:col-span-2 text-sm"
          :class="messageType === 'error' ? 'text-red-500' : 'text-emerald-600'"
        >{{ message }}</p>

        <button type="submit" class="btn-primary sm:col-span-2 w-full" :disabled="auth.loading">
          {{ auth.loading ? '처리 중...' : '회원가입' }}
        </button>
      </form>

      <div class="mt-6 text-sm text-navy/70 flex justify-between">
        <RouterLink to="/" class="hover:text-brand">메인으로</RouterLink>
        <RouterLink to="/login" class="hover:text-brand">이미 계정이 있나요?</RouterLink>
      </div>
    </div>
  </section>
</template>
