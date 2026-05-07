<script setup>
import { reactive, ref } from 'vue'
import { useBoardStore } from '@/stores/board'

const board = useBoardStore()
const form = reactive({
  title: '',
  content: '',
  plateNumber: '',
  vehicleCount: 1,
  recognitionConfidence: 1
})
const submitting = ref(false)
const message = ref('')

async function submit() {
  if (!form.title.trim() || !form.content.trim()) {
    message.value = '제목과 내용을 입력해 주세요.'
    return
  }
  submitting.value = true
  const result = await board.create({ ...form })
  submitting.value = false
  message.value = result.ok ? '문의가 접수되었습니다.' : result.message
}
</script>

<template>
  <section class="contact-page">
    <div class="max-w-7xl mx-auto px-6 grid lg:grid-cols-[0.9fr_1.1fr] gap-10">
      <aside>
        <p class="eyebrow">CONTACT</p>
        <h1>도입 문의와 시연 요청을 남겨주세요.</h1>
        <div class="contact-cards">
          <div><span>메일</span><strong>contact@hifive.io</strong></div>
          <div><span>운영 시간</span><strong>평일 09:00-18:00</strong></div>
          <div><span>시연 범위</span><strong>GPS, OCR, 관제, 정산</strong></div>
        </div>
      </aside>
      <form @submit.prevent="submit">
        <label>제목<input v-model="form.title" placeholder="OO 지점 PoC 문의" /></label>
        <label>내용<textarea v-model="form.content" rows="7" placeholder="회사명, 담당자, 연락처, 검토 중인 차로 정보를 적어주세요." /></label>
        <div class="form-grid">
          <label>차량번호<input v-model="form.plateNumber" placeholder="12가3456" /></label>
          <label>차량 수<input v-model.number="form.vehicleCount" type="number" min="1" /></label>
          <label>신뢰도<input v-model.number="form.recognitionConfidence" type="number" min="0" max="1" step="0.01" /></label>
        </div>
        <p v-if="message">{{ message }}</p>
        <button :disabled="submitting">{{ submitting ? '전송 중...' : '문의 보내기' }}</button>
      </form>
    </div>
  </section>
</template>

<style scoped>
.contact-page{padding:100px 0;background:linear-gradient(135deg,#07101f,#0b1840);color:white}
.eyebrow{font-family:monospace;font-size:12px;letter-spacing:.28em;color:#38bef5;font-weight:800}
h1{margin-top:14px;font-size:52px;line-height:1.08;font-weight:900}
.contact-cards{display:grid;gap:12px;margin-top:36px}.contact-cards div{padding:18px;border:1px solid rgba(56,190,245,.22);border-radius:14px;background:rgba(255,255,255,.05)}
.contact-cards span{display:block;color:#8ca5c8;font-size:12px}.contact-cards strong{display:block;margin-top:6px}
form{padding:28px;border-radius:20px;background:white;color:#0b1840;display:grid;gap:16px}
label{display:grid;gap:7px;font-size:13px;font-weight:800}input,textarea{width:100%;padding:13px 14px;border:1px solid rgba(11,24,64,.14);border-radius:12px;font:inherit}
.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}button{height:48px;border:0;border-radius:999px;background:#1b3be8;color:white;font-weight:900;cursor:pointer}p{color:#1b3be8;font-weight:800}
</style>
