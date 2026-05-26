<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { askChatbot } from '@/api/chatbot'

const quickQuestions = [
  '오늘 정산 현황 알려줘',
  '어제 정산 현황 알려줘',
  '날짜별 정산 현황 보여줘',
  '오늘 실시간 관제 현황 알려줘',
  '오늘 통행 이벤트 몇 건이야',
  '지난달 GPS 판정 현황 알려줘',
  '검수 대기 몇 건이야',
  '카메라 지연 이후 검수 건수 알려줘',
  '통신 지연으로 정산 보류된 건 몇 건이야',
  '장비 이상 현황 알려줘'
]

const isOpen = ref(false)
const isHidden = ref(false)
const isMaximized = ref(false)
const question = ref('')
const loading = ref(false)
const chatLog = ref(null)
const chatWindowRef = ref(null)
const MIN_CHAT_SIZE_STEP = -2
const MAX_CHAT_SIZE_STEP = 3
const CHAT_VIEWPORT_MARGIN = 12

// 뒤 대시보드가 보이는 정도. 값이 높을수록 챗봇 배경만 더 투명해진다.
const dashboardReveal = ref(0.4)
const chatSizeStep = ref(0)

const dashboardRevealPercent = computed(() => `${Math.round(dashboardReveal.value * 100)}%`)
const chatWindowScale = computed(() => 1 + chatSizeStep.value * 0.1)
const chatSizePercent = computed(() => (isMaximized.value ? 'MAX' : `${Math.round(chatWindowScale.value * 100)}%`))

// 채팅창 위치 저장값
// null이면 기본 위치인 우측 하단 버튼 위에 표시하고,
// 사용자가 드래그하면 left/top 좌표로 채팅창만 고정한다.
const chatWindowPosition = ref({
  left: null,
  top: null
})

const dragState = ref({
  dragging: false,
  pointerId: null,
  startX: 0,
  startY: 0,
  startLeft: 0,
  startTop: 0
})

const chatWindowStyle = computed(() => {
  const reveal = dashboardReveal.value
  const scale = chatWindowScale.value
  const style = {
    '--chat-width': `${Math.round(430 * scale)}px`,
    '--chat-height': `${Math.round(680 * scale)}px`,
    '--chat-shell-alpha': Math.max(0.08, 0.92 - reveal * 0.88),
    '--chat-panel-alpha': Math.max(0.1, 0.88 - reveal * 0.8),
    '--chat-message-alpha': Math.max(0.18, 0.96 - reveal * 0.78),
    '--chat-control-alpha': Math.max(0.18, 0.96 - reveal * 0.76),
    '--chat-table-alpha': Math.max(0.16, 0.92 - reveal * 0.76),
    '--chat-header-alpha': Math.max(0.25, 0.88 - reveal * 0.63)
  }

  if (isMaximized.value) {
    return {
      ...style,
      left: '28px',
      top: '28px',
      right: '28px',
      bottom: '28px'
    }
  }

  if (chatWindowPosition.value.left === null || chatWindowPosition.value.top === null) {
    return style
  }

  return {
    ...style,
    left: `${chatWindowPosition.value.left}px`,
    top: `${chatWindowPosition.value.top}px`,
    right: 'auto',
    bottom: 'auto'
  }
})

const messages = ref([
  {
    role: 'bot',
    text: '안녕하세요. HiFive 회원용 대시보드 챗봇입니다. 실시간 관제, 통행 이벤트, GPS 판정, 정산, CCTV, 검수, 장비 상태를 질문해 주세요.',
    table: [],
    guideCards: []
  }
])

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function loadChatWindowPosition() {
  const saved = localStorage.getItem('hifive-chatbot-window-position')
  if (!saved) {
    return
  }

  try {
    const parsed = JSON.parse(saved)
    if (typeof parsed.left === 'number' && typeof parsed.top === 'number') {
      chatWindowPosition.value = {
        left: parsed.left,
        top: parsed.top
      }
    }
  } catch {
    localStorage.removeItem('hifive-chatbot-window-position')
  }
}

function saveChatWindowPosition() {
  if (chatWindowPosition.value.left === null || chatWindowPosition.value.top === null) {
    localStorage.removeItem('hifive-chatbot-window-position')
    return
  }

  localStorage.setItem(
    'hifive-chatbot-window-position',
    JSON.stringify({
      left: chatWindowPosition.value.left,
      top: chatWindowPosition.value.top
    })
  )
}

function resetChatWindowPosition() {
  chatWindowPosition.value = {
    left: null,
    top: null
  }
  localStorage.removeItem('hifive-chatbot-window-position')
}

function keepChatWindowInViewport() {
  if (!chatWindowRef.value || isMaximized.value) {
    return
  }

  if (chatWindowPosition.value.left === null || chatWindowPosition.value.top === null) {
    return
  }

  const rect = chatWindowRef.value.getBoundingClientRect()
  const maxLeft = Math.max(CHAT_VIEWPORT_MARGIN, window.innerWidth - rect.width - CHAT_VIEWPORT_MARGIN)
  const maxTop = Math.max(CHAT_VIEWPORT_MARGIN, window.innerHeight - rect.height - CHAT_VIEWPORT_MARGIN)

  chatWindowPosition.value = {
    left: clamp(chatWindowPosition.value.left, CHAT_VIEWPORT_MARGIN, maxLeft),
    top: clamp(chatWindowPosition.value.top, CHAT_VIEWPORT_MARGIN, maxTop)
  }
  saveChatWindowPosition()
}

function startDrag(event) {
  if (!chatWindowRef.value || isMaximized.value) {
    return
  }

  const rect = chatWindowRef.value.getBoundingClientRect()
  dragState.value = {
    dragging: true,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startLeft: rect.left,
    startTop: rect.top
  }
  event.currentTarget.setPointerCapture(event.pointerId)
}

function moveDrag(event) {
  if (!dragState.value.dragging || dragState.value.pointerId !== event.pointerId) {
    return
  }

  const width = chatWindowRef.value?.offsetWidth || 420
  const height = chatWindowRef.value?.offsetHeight || 620
  const nextLeft = dragState.value.startLeft + event.clientX - dragState.value.startX
  const nextTop = dragState.value.startTop + event.clientY - dragState.value.startY
  const maxLeft = Math.max(CHAT_VIEWPORT_MARGIN, window.innerWidth - width - CHAT_VIEWPORT_MARGIN)
  const maxTop = Math.max(CHAT_VIEWPORT_MARGIN, window.innerHeight - height - CHAT_VIEWPORT_MARGIN)

  chatWindowPosition.value = {
    left: clamp(nextLeft, CHAT_VIEWPORT_MARGIN, maxLeft),
    top: clamp(nextTop, CHAT_VIEWPORT_MARGIN, maxTop)
  }
}

function endDrag(event) {
  if (!dragState.value.dragging || dragState.value.pointerId !== event.pointerId) {
    return
  }

  dragState.value.dragging = false
  dragState.value.pointerId = null
  saveChatWindowPosition()

  if (event.currentTarget.hasPointerCapture(event.pointerId)) {
    event.currentTarget.releasePointerCapture(event.pointerId)
  }
}

function openChat() {
  isOpen.value = true
  isHidden.value = false
  nextTick(() => {
    keepChatWindowInViewport()
    scrollToBottom()
  })
}

function closeChat() {
  isOpen.value = false
  isHidden.value = false
  isMaximized.value = false
  chatSizeStep.value = 0
  resetChatWindowPosition()
}

function toggleHidden() {
  isHidden.value = !isHidden.value
  if (isHidden.value) {
    isMaximized.value = false
  }
  nextTick(() => {
    keepChatWindowInViewport()
    scrollToBottom()
  })
}

function increaseChatSize() {
  isHidden.value = false
  if (chatSizeStep.value >= MAX_CHAT_SIZE_STEP) {
    isMaximized.value = true
  } else {
    isMaximized.value = false
    chatSizeStep.value += 1
  }
  nextTick(() => {
    keepChatWindowInViewport()
    scrollToBottom()
  })
}

function decreaseChatSize() {
  isHidden.value = false
  if (isMaximized.value) {
    isMaximized.value = false
    chatSizeStep.value = MAX_CHAT_SIZE_STEP
  } else {
    chatSizeStep.value = Math.max(MIN_CHAT_SIZE_STEP, chatSizeStep.value - 1)
  }
  nextTick(() => {
    keepChatWindowInViewport()
    scrollToBottom()
  })
}

function toggleChat() {
  if (isOpen.value) {
    closeChat()
    return
  }
  openChat()
}

async function scrollToBottom() {
  await nextTick()
  if (chatLog.value) {
    chatLog.value.scrollTop = chatLog.value.scrollHeight
  }
}

function normalizeBotPayload(data) {
  const queryType = data?.query_type || ''
  const table = queryType === 'current_status'
    ? []
    : (Array.isArray(data?.table) ? data.table : [])

  return {
    role: 'bot',
    text: data?.answer || '응답이 비어 있습니다.',
    table,
    guideCards: Array.isArray(data?.guide_cards) ? data.guide_cards : [],
    filters: data?.filters || {},
    metadata: data?.metadata || {},
    queryType,
    answerSource: data?.answer_source || '',
    error: data?.status === 'error'
  }
}

function handleGuideCard(card) {
  if (card?.action === 'navigate' && card?.target) {
    window.dispatchEvent(new CustomEvent('hifive-dashboard-navigate', {
      detail: {
        target: card.target,
        category: card.category || card.target
      }
    }))
    messages.value.push({
      role: 'bot',
      text: `${card.target} 화면으로 이동했습니다.`,
      table: [],
      guideCards: []
    })
    nextTick(scrollToBottom)
    return
  }

  if (card?.question) {
    submitQuestion(card.question)
  }
}

async function submitQuestion(text = question.value) {
  const trimmed = text.trim()
  if (!trimmed || loading.value) {
    return
  }

  messages.value.push({
    role: 'user',
    text: trimmed,
    table: [],
    guideCards: []
  })

  question.value = ''
  loading.value = true
  await scrollToBottom()

  try {
    // 중요:
    // 여기서 질문을 프론트에서 표준화하지 않는다.
    // "오늘 정산 얼마?", "어제 정산 얼마?", "5일 전 정산 얼마?" 같은 문장은
    // app.py에서 날짜/의도 파싱을 해야 한다.
    const data = await askChatbot(trimmed)
    messages.value.push(normalizeBotPayload(data))
  } catch (error) {
    if (error?.response?.data?.answer) {
      messages.value.push(normalizeBotPayload(error.response.data))
      loading.value = false
      await scrollToBottom()
      return
    }

    messages.value.push({
      role: 'bot',
      text: '챗봇 서버에 연결할 수 없습니다. FastAPI 챗봇 서버가 127.0.0.1:8000에서 실행 중인지 확인하세요.',
      table: [],
      guideCards: [],
      error: true
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

onMounted(() => {
  loadChatWindowPosition()
  nextTick(() => {
    keepChatWindowInViewport()
  })
  window.addEventListener('resize', keepChatWindowInViewport)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', keepChatWindowInViewport)
})
</script>

<template>
  <div class="dashboard-chatbot">
    <section
      v-if="isOpen"
      ref="chatWindowRef"
      class="chat-window"
      :class="{ 'is-hidden': isHidden, 'is-maximized': isMaximized }"
      aria-label="HiFive 챗봇"
      :style="chatWindowStyle"
    >
      <header class="chat-header">
        <div
          class="title-area drag-handle"
          title="마우스로 드래그해서 채팅창만 이동, 더블클릭하면 기본 위치로 초기화"
          @pointerdown="startDrag"
          @pointermove="moveDrag"
          @pointerup="endDrag"
          @pointercancel="endDrag"
          @dblclick="resetChatWindowPosition"
        >
          <strong>HiFive 챗봇</strong>
          <span>{{ isHidden ? '감춤 상태 · 버튼으로 복원' : '회원 대시보드 업무 도우미 · 창 이동' }}</span>
        </div>

        <div v-if="!isHidden" class="opacity-control">
          <label for="chat-reveal">투명도</label>
          <input
            id="chat-reveal"
            v-model.number="dashboardReveal"
            type="range"
            min="0"
            max="1"
            step="0.05"
            aria-label="챗봇 배경 투과 정도 조절"
          />
          <span class="opacity-value">{{ dashboardRevealPercent }}</span>
        </div>

        <div class="window-actions">
          <button type="button" class="window-action-btn" :aria-label="isHidden ? '챗봇 보이기' : '챗봇 감추기'" @click="toggleHidden">
            {{ isHidden ? '보이기' : '감추기' }}
          </button>
          <div v-if="!isHidden" class="size-actions" aria-label="챗봇 창 크기 조절">
            <button
              type="button"
              class="window-action-btn size-btn"
              aria-label="챗봇 창 축소"
              :disabled="!isMaximized && chatSizeStep <= MIN_CHAT_SIZE_STEP"
              @click="decreaseChatSize"
            >
              -
            </button>
            <span class="size-value">{{ chatSizePercent }}</span>
            <button
              type="button"
              class="window-action-btn size-btn"
              aria-label="챗봇 창 확대"
              :disabled="isMaximized"
              @click="increaseChatSize"
            >
              +
            </button>
          </div>
          <button type="button" class="window-action-btn close-btn" aria-label="챗봇 닫기" @click="closeChat">
            ×
          </button>
        </div>
      </header>

      <template v-if="!isHidden">
        <div ref="chatLog" class="chat-log">
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="chat-message"
          :class="[message.role, { error: message.error }]"
        >
          <p>{{ message.text }}</p>

          <div v-if="message.guideCards && message.guideCards.length" class="guide-list" aria-label="질문 가이드">
            <button
              v-for="card in message.guideCards"
              :key="`${index}-${card.title}-${card.question}`"
              type="button"
              class="guide-item"
              :disabled="loading || (!card.question && !card.target)"
              @click="handleGuideCard(card)"
            >
              <span class="guide-category">{{ card.category || '질문 가이드' }}</span>
              <span class="guide-main">
                <strong>{{ card.title }}</strong>
                <small v-if="card.desc">{{ card.desc }}</small>
              </span>
              <span class="guide-action" v-if="card.action === 'navigate' && card.target">{{ card.target }} 이동</span>
              <span class="guide-action" v-else-if="card.question">{{ card.question }}</span>
            </button>
          </div>

          <div v-if="message.table && message.table.length" class="answer-table-wrap">
            <table class="answer-table">
              <thead>
                <tr>
                  <th v-for="key in Object.keys(message.table[0])" :key="key">
                    {{ key }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in message.table" :key="rowIndex">
                  <td v-for="key in Object.keys(message.table[0])" :key="key">
                    {{ row[key] }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="loading" class="chat-message bot loading-message">
          <p>데이터를 조회하는 중입니다...</p>
        </div>
      </div>

      <div class="quick-list">
        <button
          v-for="item in quickQuestions"
          :key="item"
          type="button"
          :disabled="loading"
          @click="submitQuestion(item)"
        >
          {{ item }}
        </button>
      </div>

      <form class="chat-form" @submit.prevent="submitQuestion()">
        <input
          v-model="question"
          type="text"
          placeholder="질문을 입력하세요"
          :disabled="loading"
        />
        <button type="submit" :disabled="loading || !question.trim()">
          {{ loading ? '조회 중' : '전송' }}
        </button>
      </form>
      </template>
    </section>

    <button
      type="button"
      class="chat-toggle"
      :aria-label="isOpen ? '챗봇 닫기' : '챗봇 열기'"
      @click="toggleChat"
    >
      <span class="bubble-icon"></span>
      <strong>챗봇</strong>
    </button>
  </div>
</template>

<style scoped>
.dashboard-chatbot {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 2000;
  font-family: 'Noto Sans KR', sans-serif;
}

.chat-toggle {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 112px;
  height: 52px;
  border: 0;
  border-radius: 999px;
  background: #1b3be8;
  color: #ffffff;
  box-shadow: 0 18px 36px rgba(8, 12, 24, 0.28);
  cursor: pointer;
  font: inherit;
  font-weight: 800;
  justify-content: center;
}

.bubble-icon {
  position: relative;
  width: 21px;
  height: 17px;
  border: 2px solid #ffffff;
  border-radius: 9px;
}

.bubble-icon::after {
  content: '';
  position: absolute;
  right: 2px;
  bottom: -6px;
  width: 7px;
  height: 7px;
  border-right: 2px solid #ffffff;
  border-bottom: 2px solid #ffffff;
  transform: rotate(35deg);
}

.chat-window {
  position: fixed;
  right: 28px;
  bottom: 92px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  width: min(var(--chat-width, 430px), calc(100vw - 32px));
  height: min(var(--chat-height, 680px), calc(100vh - 128px));
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 112px);
  min-width: min(344px, calc(100vw - 32px));
  min-height: min(420px, calc(100vh - 112px));
  overflow: hidden;
  border: 1px solid rgba(11, 24, 64, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, var(--chat-shell-alpha, 0.52));
  box-shadow: 0 24px 70px rgba(8, 12, 24, 0.25);
  backdrop-filter: none;
}

.chat-window.is-hidden {
  grid-template-rows: auto;
  width: min(360px, calc(100vw - 32px));
  min-width: min(280px, calc(100vw - 32px));
  min-height: 0;
  height: auto;
}

.chat-window.is-maximized {
  width: auto;
  height: auto;
  max-width: none;
  max-height: none;
  min-width: 0;
  min-height: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px 14px 13px;
  background: linear-gradient(135deg, rgba(11, 24, 64, var(--chat-header-alpha, 0.7)), rgba(27, 59, 232, var(--chat-header-alpha, 0.7)));
  color: #ffffff;
}

.title-area {
  flex: 1 1 60px;
  min-width: 0;
  cursor: grab;
  user-select: none;
}

.title-area:active {
  cursor: grabbing;
}

.title-area strong {
  display: block;
  font-size: 15px;
}

.title-area span {
  display: block;
  margin-top: 2px;
  color: rgba(255, 255, 255, 0.76);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.opacity-control {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 0 1 122px;
  min-width: 122px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
  font-weight: 700;
}

.opacity-control label {
  white-space: nowrap;
}

.opacity-control input {
  width: 64px;
  accent-color: #ffffff;
  cursor: pointer;
}

.opacity-value {
  min-width: 28px;
  text-align: right;
  color: rgba(255, 255, 255, 0.72);
  font-size: 11px;
}

.window-actions {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 4px;
  flex: 0 0 auto;
}

.window-action-btn {
  flex: 0 0 auto;
  min-width: 36px;
  height: 32px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  padding: 0 6px;
}

.window-action-btn:hover {
  background: rgba(255, 255, 255, 0.18);
}

.window-action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.size-actions {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.size-btn {
  min-width: 28px;
  width: 28px;
  padding: 0;
  font-size: 17px;
}

.size-value {
  min-width: 36px;
  color: rgba(255, 255, 255, 0.76);
  font-size: 10px;
  font-weight: 800;
  text-align: center;
}

.close-btn {
  min-width: 28px;
  width: 28px;
  padding: 0;
  font-size: 20px;
}

.chat-log {
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  background: rgba(243, 246, 255, var(--chat-panel-alpha, 0.48));
}

.chat-message {
  width: fit-content;
  max-width: 92%;
  margin-bottom: 10px;
  padding: 11px 13px;
  border-radius: 8px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.chat-message p {
  margin: 0;
}

.chat-message small {
  display: block;
  margin-top: 4px;
  color: rgba(11, 24, 64, 0.48);
  font-size: 11px;
}

.chat-message.bot {
  width: fit-content;
  max-width: 92%;
  padding: 11px 13px;
  border-radius: 8px;
  border-top-left-radius: 3px;
  background: rgba(255, 255, 255, var(--chat-message-alpha, 0.7));
  border: 0;
  color: #000000;
}

.chat-message.user {
  margin-left: auto;
  background: #1b3be8;
  color: #ffffff;
}

.chat-message.error {
  color: #991b1b;
}

.loading-message {
  color: #64748b;
}

.guide-list {
  display: flex;
  flex-direction: column;
  margin-top: 10px;
  border-top: 1px solid rgba(11, 24, 64, 0.12);
}

.guide-item {
  width: 100%;
  border: 0;
  border-bottom: 1px solid rgba(11, 24, 64, 0.12);
  background: transparent;
  color: #0b1840;
  padding: 9px 0;
  cursor: pointer;
  font: inherit;
  text-align: left;
  display: grid;
  grid-template-columns: minmax(54px, auto) 1fr;
  gap: 4px 10px;
  align-items: start;
}

.guide-category {
  color: #1b3be8;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
}

.guide-main {
  min-width: 0;
}

.guide-main strong,
.guide-main small,
.guide-action {
  display: block;
}

.guide-main strong {
  color: #0f172a;
  font-size: 12px;
  line-height: 1.35;
  word-break: keep-all;
}

.guide-main small {
  margin-top: 2px;
  color: #475569;
  font-size: 11px;
  line-height: 1.35;
}

.guide-action {
  grid-column: 2;
  color: #1b3be8;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  line-height: 1.35;
  word-break: keep-all;
}

.guide-item:hover .guide-main strong,
.guide-item:hover .guide-action {
  color: #1230c4;
}

.guide-item:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.answer-table-wrap {
  width: 100%;
  max-width: 100%;
  margin-top: 10px;
  overflow-x: auto;
}

.answer-table {
  width: 100%;
  border-collapse: collapse;
  color: #000000;
  font-size: 11px;
  white-space: nowrap;
}

.answer-table th,
.answer-table td {
  border: 0;
  border-bottom: 1px solid rgba(11, 24, 64, 0.14);
  color: #000000;
  padding: 6px;
  text-align: left;
}

.answer-table th {
  background: transparent;
  font-weight: 800;
}

.answer-table td {
  background: transparent;
}

.quick-list {
  display: flex;
  min-height: 58px;
  gap: 8px;
  overflow-x: auto;
  padding: 12px 14px;
  border-top: 1px solid rgba(11, 24, 64, 0.1);
  background: rgba(255, 255, 255, var(--chat-control-alpha, 0.74));
}

.quick-list button {
  flex: 0 0 auto;
  border: 1px solid rgba(11, 24, 64, 0.12);
  border-radius: 999px;
  background: rgba(247, 249, 255, var(--chat-message-alpha, 0.72));
  color: #0b1840;
  padding: 8px 11px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
}

.quick-list button:hover {
  border-color: #1b3be8;
  color: #1b3be8;
}

.quick-list button:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.chat-form {
  display: flex;
  min-height: 66px;
  gap: 8px;
  padding: 14px;
  border-top: 1px solid rgba(11, 24, 64, 0.1);
  background: rgba(255, 255, 255, var(--chat-control-alpha, 0.74));
}

.chat-form input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(11, 24, 64, 0.14);
  border-radius: 10px;
  padding: 10px 11px;
  color: #0b1840;
  background: rgba(255, 255, 255, var(--chat-message-alpha, 0.72));
  font: inherit;
  font-size: 13px;
}

.chat-form input:focus {
  outline: 2px solid rgba(27, 59, 232, 0.18);
  border-color: #1b3be8;
}

.chat-form button {
  border: 0;
  border-radius: 10px;
  background: #1b3be8;
  color: #ffffff;
  padding: 0 15px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.chat-form button:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

@media (max-width: 560px) {
  .dashboard-chatbot {
    right: 16px;
    bottom: 16px;
  }

  .chat-window {
    right: 16px;
    bottom: 82px;
    width: calc(100vw - 32px);
    height: min(680px, calc(100vh - 112px));
    min-width: 0;
    max-height: calc(100vh - 104px);
  }

  .chat-window.is-maximized {
    left: 16px !important;
    top: 16px !important;
    right: 16px !important;
    bottom: 16px !important;
  }

  .opacity-control {
    order: 3;
    flex-basis: 100%;
    min-width: 0;
  }
}
</style>
