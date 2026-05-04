<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { createHeroWave } from '@/composables/heroWave'

const waveCanvasEl = ref(null)
let waveStop = null

onMounted(() => { waveStop = createHeroWave(waveCanvasEl.value) })
onBeforeUnmount(() => { waveStop?.dispose() })
</script>

<template>
  <section class="snap-section hero" id="hero">
    <canvas ref="waveCanvasEl" id="waveCanvas" aria-hidden="true"></canvas>
    <div class="section-inner hero-corporate reveal">
      <div class="hero-navline">
        <span class="hero-mark">하이파이브 모빌리티 인텔리전스</span>
        <span>AI 톨링 전환 스튜디오</span>
      </div>
      <div class="hero-visual" aria-label="Smart tolling roadway animation">
        <div class="road-scene" aria-hidden="true">
          <div class="road-skyline"></div>
          <div class="data-arc a1"></div>
          <div class="data-arc a2"></div>
          <div class="data-arc a3"></div>
          <div class="gantry"><div class="gantry-bar"><div class="gantry-scan"></div></div></div>
          <div class="road-perspective"><div class="road-surface"></div></div>
          <div class="vehicle"></div>
        </div>
        <div class="hero-copy-block">
          <p class="hero-eyebrow">Smart Tolling Conversion Platform</p>
          <h1 class="hero-title">THE ROAD<br><span class="shimmer">MOVES</span><br>WITHOUT STOP.</h1>
          <p class="hero-lead">HiFive는 차로 기반 요금 수납을 끊김 없는 도로 지능화 서비스로 전환하는 기업형 스마트톨링 솔루션을 설계합니다.</p>
          <div class="hero-actions">
            <a class="btn primary" href="#core">핵심 기술 보기</a>
            <RouterLink class="btn" to="/login">관리자 관제 보기</RouterLink>
          </div>
        </div>
        <div class="visual-caption" aria-label="Service domains">
          <span>현장 AI</span><span>요금 정책</span><span>관제 UX</span>
        </div>
      </div>
      <div class="hero-footerline" aria-label="HiFive corporate positioning">
        <span>인프라 전략</span><span>운영 지능화</span><span>전환형 서비스</span>
      </div>
    </div>
  </section>
</template>
