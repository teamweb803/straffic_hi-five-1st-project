<script setup>
import { reactive, ref } from 'vue'
import { useBoardStore } from '@/stores/board'

const board = useBoardStore()

// 1:1 문의는 백엔드 게시판 API 를 그대로 사용 (제목/내용 + 차량 정보)
const form = reactive({
  title: '',
  content: '',
  plateNumber: '',
  vehicleCount: 1,
  recognitionConfidence: 1.0
})
const submitting = ref(false)
const message = ref(null)
const messageType = ref('error')

async function submit() {
  message.value = null
  if (!form.title.trim() || !form.content.trim()) {
    message.value = '제목과 내용을 입력해 주세요.'
    messageType.value = 'error'
    return
  }
  submitting.value = true
  const result = await board.create({ ...form })
  submitting.value = false
  if (result.ok) {
    message.value = '문의가 접수되었습니다. 빠르게 회신드리겠습니다.'
    messageType.value = 'success'
    form.title = ''
    form.content = ''
    form.plateNumber = ''
    form.vehicleCount = 1
  } else {
    message.value = result.message
    messageType.value = 'error'
  }
}
</script>

<template>
  <section class="py-24 bg-deep text-white">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-sky">CONTACT</p>
      <h1 class="font-headline text-5xl mt-2">1:1 도입 문의</h1>
      <p class="mt-6 max-w-2xl text-white/70 leading-relaxed">
        도입 일정, 견적, PoC 신청 등 무엇이든 편하게 남겨주세요.
      </p>
    </div>
  </section>

  <section class="py-16 bg-cloud">
    <div class="max-w-3xl mx-auto px-6">
      <form class="card space-y-4" @submit.prevent="submit">
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">제목 *</label>
          <input v-model="form.title" class="input-field" placeholder="예) 지방도 OO노선 PoC 문의" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-navy/70 mb-1">내용 *</label>
          <textarea v-model="form.content" rows="6" class="input-field" placeholder="회사 / 부서 / 전화번호 / 검토 중인 노선 정보를 알려주세요." />
        </div>
        <div class="grid sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-xs font-semibold text-navy/70 mb-1">차량번호 (선택)</label>
            <input v-model="form.plateNumber" class="input-field" placeholder="12가3456" />
          </div>
          <div>
            <label class="block text-xs font-semibold text-navy/70 mb-1">차량 수</label>
            <input v-model.number="form.vehicleCount" type="number" min="1" class="input-field" />
          </div>
          <div>
            <label class="block text-xs font-semibold text-navy/70 mb-1">신뢰도</label>
            <input v-model.number="form.recognitionConfidence" type="number" min="0" max="1" step="0.01" class="input-field" />
          </div>
        </div>

        <p
          v-if="message"
          class="text-sm"
          :class="messageType === 'error' ? 'text-red-500' : 'text-emerald-600'"
        >{{ message }}</p>

        <button type="submit" class="btn-primary w-full" :disabled="submitting">
          {{ submitting ? '전송 중...' : '문의 보내기' }}
        </button>
      </form>

      <p class="mt-6 text-xs text-navy/60 text-center">
        contact@hifive.io · 02-000-0000 · 평일 09:00 ~ 18:00
      </p>
    </div>
  </section>
</template>
