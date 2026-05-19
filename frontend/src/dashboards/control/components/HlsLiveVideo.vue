<script setup>
import Hls from 'hls.js'
import { onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  live: { type: Boolean, default: false }
})

const emit = defineEmits(['error'])
const videoRef = shallowRef(null)

let hls = null
let stalledAt = 0

function destroyPlayer() {
  if (hls) {
    hls.destroy()
    hls = null
  }
  if (videoRef.value) {
    videoRef.value.removeAttribute('src')
    videoRef.value.load()
  }
}

function play(video) {
  video.play().catch(() => {})
}

function syncToLiveIfNeeded(video) {
  const livePosition = hls?.liveSyncPosition
  if (!Number.isFinite(livePosition)) return
  if (livePosition - video.currentTime > 4) {
    video.currentTime = livePosition
  }
}

function recoverHlsError(data) {
  const video = videoRef.value
  if (!video || !hls) return

  if (data?.type === Hls.ErrorTypes.NETWORK_ERROR) {
    hls.startLoad(-1)
    play(video)
    return
  }

  if (data?.type === Hls.ErrorTypes.MEDIA_ERROR) {
    hls.recoverMediaError()
    play(video)
    return
  }

  emit('error')
}

function handleStalled() {
  const now = Date.now()
  if (now - stalledAt < 1500) return
  stalledAt = now

  const video = videoRef.value
  if (!video) return
  hls?.startLoad(-1)
  syncToLiveIfNeeded(video)
  play(video)
}

function attachPlayer() {
  const video = videoRef.value
  destroyPlayer()
  if (!video || !props.src || !props.live) return

  video.muted = true
  video.playsInline = true

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = props.src
    play(video)
    return
  }

  if (!Hls.isSupported()) {
    emit('error')
    return
  }

  hls = new Hls({
    lowLatencyMode: false,
    backBufferLength: 10,
    maxBufferLength: 20,
    maxMaxBufferLength: 30,
    liveSyncDurationCount: 4,
    liveMaxLatencyDurationCount: 8,
    maxLiveSyncPlaybackRate: 1.2,
    startFragPrefetch: true,
    manifestLoadingTimeOut: 10000,
    levelLoadingTimeOut: 10000,
    fragLoadingTimeOut: 20000
  })
  hls.on(Hls.Events.ERROR, (_, data) => {
    if (data?.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR) {
      handleStalled()
      return
    }
    if (data?.fatal) recoverHlsError(data)
  })
  hls.on(Hls.Events.MANIFEST_PARSED, () => play(video))
  hls.on(Hls.Events.LEVEL_UPDATED, () => syncToLiveIfNeeded(video))
  hls.on(Hls.Events.FRAG_BUFFERED, () => {
    syncToLiveIfNeeded(video)
    play(video)
  })
  hls.loadSource(props.src)
  hls.attachMedia(video)
}

watch(() => [props.src, props.live], attachPlayer)
onMounted(attachPlayer)
onBeforeUnmount(destroyPlayer)
</script>

<template>
  <video
    ref="videoRef"
    class="dashboard-live-frame"
    autoplay
    muted
    playsinline
    @error="emit('error')"
    @stalled="handleStalled"
    @waiting="handleStalled"
  />
</template>
