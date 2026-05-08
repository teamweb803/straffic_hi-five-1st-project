import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { boardApi } from '@/api/board'

export const useBoardStore = defineStore('board', () => {
  const posts = ref([])
  const loading = ref(false)
  const error = ref(null)

  const total = computed(() => posts.value.length)
  const lowConfidencePosts = computed(() =>
    posts.value.filter((p) => p.recognitionConfidence < 0.7)
  )

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      const { data } = await boardApi.list()
      // 백엔드 응답이 LocalDateTime 배열일 수 있어 createdAt 정규화
      posts.value = data.map((p) => ({
        ...p,
        createdAt: normalizeCreatedAt(p.createdAt)
      }))
    } catch (err) {
      error.value = err?.response?.data?.message ?? '게시글을 불러오지 못했습니다.'
    } finally {
      loading.value = false
    }
  }

  async function create(form) {
    error.value = null
    try {
      await boardApi.create(form)
      await fetchAll()
      return { ok: true }
    } catch (err) {
      const msg = err?.response?.data?.message ?? '게시글 등록에 실패했습니다.'
      error.value = msg
      return { ok: false, message: msg }
    }
  }

  function normalizeCreatedAt(raw) {
    if (!raw) return null
    if (typeof raw === 'string') return raw
    if (Array.isArray(raw)) {
      // [year, month, day, hour, minute, second, nano]
      const [y, m, d, h = 0, mi = 0, s = 0] = raw
      return new Date(y, m - 1, d, h, mi, s).toISOString()
    }
    return raw
  }

  return { posts, loading, error, total, lowConfidencePosts, fetchAll, create }
})
