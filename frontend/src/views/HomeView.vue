<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import HomeHeader from '@/views/home/HomeHeader.vue'
import SectionHero from '@/views/home/SectionHero.vue'
import SectionCore from '@/views/home/SectionCore.vue'
import SectionArchitecture from '@/views/home/SectionArchitecture.vue'
import SectionCta from '@/views/home/SectionCta.vue'
import '@/styles/home.css'

const rootEl = ref(null)
let revealObserver = null

onMounted(() => {
  // home 라우트 활성 시에만 글로벌 스타일(scroll-snap, body bg) 적용
  document.documentElement.classList.add('home-active')

  // reveal + 카운트업
  revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return
      entry.target.classList.add('is-visible')
      if (entry.target.classList.contains('metric') && !entry.target.dataset.done) {
        entry.target.dataset.done = 'true'
        const value = parseFloat(entry.target.dataset.count)
        const suffix = entry.target.dataset.suffix || ''
        const out = entry.target.querySelector('strong')
        const start = performance.now()
        const decimals = String(value).includes('.') ? 1 : 0
        const tick = (now) => {
          const ratio = Math.min((now - start) / 1200, 1)
          const eased = 1 - Math.pow(1 - ratio, 3)
          out.textContent = `${(value * eased).toFixed(decimals)}${suffix}`
          if (ratio < 1) requestAnimationFrame(tick)
        }
        requestAnimationFrame(tick)
      }
    })
  }, { threshold: 0.22 })
  rootEl.value?.querySelectorAll('.reveal').forEach((el) => revealObserver.observe(el))
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('home-active')
  revealObserver?.disconnect()
})
</script>

<template>
  <div ref="rootEl" class="home-page">
    <HomeHeader />
    <SectionHero />
    <SectionCore />
    <SectionArchitecture />
    <SectionCta />
  </div>
</template>
