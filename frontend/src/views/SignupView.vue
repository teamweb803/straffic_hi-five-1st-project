<script setup>
import { reactive, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const form = reactive({
  memberId: '',
  password: '',
  passwordConfirm: '',
  memberName: '',
  plateNumber: ''
})
const message = ref(null)
const messageType = ref('error')

async function handleSubmit() {
  message.value = null
  if (!form.memberId || !form.password || !form.memberName) {
    message.value = '필수 항목을 모두 입력해 주세요.'
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
      <h1 class="font-headline text-3xl mt-2 text-deep">JOIN HIFIVE.</h1>
      <p class="text-sm text-navy/70 mt-2">차량 정보를 등록하면 통과 이력과 정산 내역을 확인할 수 있습니다.</p>

      <form class="mt-8 grid sm:grid-cols-2 gap-4" @submit.prevent="handleSubmit">
        <div class="sm:col-span-2">
          <label class="block text-xs font-semibold text-navy/70 mb-1">아이디 *</label>
          <input v-model="form.memberId" type="text" class="input-field" placeholder="member_id" />
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
          <input v-model="form.memberName" type="text" class="input-field" placeholder="홍길동" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">차량번호</label>
          <input v-model="form.plateNumber" type="text" class="input-field" placeholder="12가3456" />
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
        <RouterLink to="/" class="hover:text-brand">← 메인으로</RouterLink>
        <RouterLink to="/login" class="hover:text-brand">이미 계정이 있나요?</RouterLink>
      </div>
    </div>
  </section>
</template>
