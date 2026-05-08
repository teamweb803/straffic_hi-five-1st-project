<script setup>
import { reactive, ref } from 'vue'
import { useBoardStore } from '@/stores/board'

const board = useBoardStore()

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
  <div class="contact-page">
    <div class="bg" aria-hidden="true">
      <div class="lane"></div>
      <div class="lane lane-2"></div>
      <div class="lane lane-3"></div>
    </div>

    <div class="inner">
      <div class="head">
        <p class="eyebrow">CONTACT · 문의하기</p>
        <h1>1:1<br>도입 문의</h1>
        <p class="lead">평일 09:00 ~ 18:00 / contact@hifive.io</p>
        <ul class="meta">
          <li><span>회사</span><strong>HiFive Mobility Lab</strong></li>
          <li><span>전화</span><strong>02-000-0000</strong></li>
          <li><span>주소</span><strong>서울특별시 강남구</strong></li>
        </ul>
      </div>

      <form class="form" @submit.prevent="submit">
        <label>
          <span class="lbl">// 제목 *</span>
          <input v-model="form.title" type="text" placeholder="예) 지방도 OO 노선 PoC 문의" />
        </label>
        <label>
          <span class="lbl">// 내용 *</span>
          <textarea
            v-model="form.content"
            rows="5"
            placeholder="회사 / 부서 / 전화번호 / 검토 중인 노선 정보를 알려주세요."
          />
        </label>
        <div class="row">
          <label>
            <span class="lbl">// 차량번호 (선택)</span>
            <input v-model="form.plateNumber" type="text" placeholder="12가3456" />
          </label>
          <label>
            <span class="lbl">// 차량 수</span>
            <input v-model.number="form.vehicleCount" type="number" min="1" placeholder="1" />
          </label>
          <label>
            <span class="lbl">// 신뢰도</span>
            <input
              v-model.number="form.recognitionConfidence"
              type="number"
              min="0"
              max="1"
              step="0.01"
              placeholder="1.0"
            />
          </label>
        </div>

        <p
          v-if="message"
          class="msg"
          :class="messageType === 'error' ? 'is-error' : 'is-success'"
        >{{ message }}</p>

        <button type="submit" class="btn" :disabled="submitting">
          {{ submitting ? 'SENDING...' : 'SEND →' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.contact-page {
  --p-deep: #080C18;
  --p-navy: #0B1840;
  --p-blue: #1B3BE8;
  --p-sky: #38BEF5;
  --p-headline: 'Big Shoulders Display', sans-serif;
  --p-mono: 'Fira Mono', monospace;

  position: relative;
  min-height: 100vh;
  background: #0A1024;
  color: #fff;
  padding: 100px 36px 80px;
  overflow: hidden;
}

.bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(60% 70% at 30% 20%, rgba(27, 59, 232, 0.45), transparent 60%),
    radial-gradient(50% 60% at 90% 90%, rgba(56, 190, 245, 0.3), transparent 70%);
  pointer-events: none;
}
.lane {
  position: absolute;
  top: -10%;
  bottom: -10%;
  width: 3px;
  background: linear-gradient(180deg, transparent, var(--p-sky), transparent);
  animation: ct-flow 1.6s linear infinite;
}
.lane { left: 22%; }
.lane-2 { left: 50%; animation-delay: 0.4s; opacity: 0.7; }
.lane-3 { left: 78%; animation-delay: 0.8s; opacity: 0.5; }
@keyframes ct-flow {
  from { transform: translateY(-30%); opacity: 0.2; }
  50% { opacity: 0.85; }
  to { transform: translateY(30%); opacity: 0.1; }
}

.inner {
  position: relative;
  max-width: 1100px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 60px;
  align-items: start;
}

.head { padding-top: 8px; }
.eyebrow {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-sky);
  margin: 0 0 14px;
}
.head h1 {
  font-family: var(--p-headline);
  font-size: clamp(56px, 7vw, 110px);
  line-height: 0.86;
  margin: 0;
  color: #fff;
}
.lead {
  margin-top: 22px;
  font-family: var(--p-mono);
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  letter-spacing: 1.4px;
}
.meta {
  list-style: none;
  padding: 0;
  margin: 56px 0 0;
  display: grid;
  gap: 0;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  overflow: hidden;
}
.meta li {
  display: grid;
  grid-template-columns: 90px 1fr;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
}
.meta li:last-child { border-bottom: none; }
.meta li span {
  font-family: var(--p-mono);
  font-size: 11px;
  color: var(--p-sky);
  letter-spacing: 1px;
}
.meta li strong { color: #fff; font-size: 14px; }

.form {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.14);
  padding: 36px;
  display: grid;
  gap: 18px;
}
.form label { display: grid; gap: 6px; }
.lbl {
  font-family: var(--p-mono);
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--p-sky);
}
.form input,
.form textarea {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 0;
  padding: 14px 16px;
  color: #fff;
  font-family: inherit;
  font-size: 14px;
  outline: none;
  transition: border-color 160ms ease;
  width: 100%;
}
.form input:focus,
.form textarea:focus { border-color: var(--p-sky); }
.form textarea { resize: vertical; min-height: 120px; }
.row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }

.msg {
  font-family: var(--p-mono);
  font-size: 12px;
  margin: 0;
  letter-spacing: 0.5px;
}
.msg.is-error { color: #FF8A8A; }
.msg.is-success { color: #6EE7B7; }

.btn {
  background: var(--p-blue);
  color: #fff;
  border: none;
  padding: 16px;
  font-family: var(--p-headline);
  font-size: 22px;
  letter-spacing: 2px;
  cursor: pointer;
  transition: background 160ms ease;
}
.btn:hover { background: #1530c5; }
.btn:disabled {
  background: #26365F;
  cursor: not-allowed;
  opacity: 0.7;
}

@media (max-width: 900px) {
  .inner { grid-template-columns: 1fr; gap: 40px; }
  .row { grid-template-columns: 1fr; }
}
</style>
