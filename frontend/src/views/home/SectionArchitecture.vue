<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { createDecisionFlow } from '@/composables/decisionFlow'

const networkCanvasEl = ref(null)
let stop = null

onMounted(() => { stop = createDecisionFlow(networkCanvasEl.value) })
onBeforeUnmount(() => { stop?.dispose() })
</script>

<template>
  <section class="snap-section architecture" id="architecture">
    <div class="section-inner arch-layout">
      <div class="arch-heading reveal">
        <p class="section-label">Data Architecture</p>
        <h2 class="section-title">EDGE TO DECISION.</h2>
      </div>
      <div class="arch-body">
        <div class="network-panel reveal">
          <canvas ref="networkCanvasEl" id="networkCanvas" aria-hidden="true"></canvas>
          <div class="network-legend">
            <span>Edge</span><span>YOLO</span><span>OCR</span>
            <span>FastAPI</span><span>SpringBoot</span>
            <span>PostgreSQL</span><span>Vue</span>
          </div>
        </div>
        <div class="metrics">
          <div class="metric reveal" style="--value:97.3%" data-count="97.3" data-suffix="%">
            <strong>0%</strong><span>번호판 인식 정확도</span>
            <div class="progress"><i></i></div>
          </div>
          <div class="metric reveal" style="--value:70%" data-count="70" data-suffix="%↓">
            <strong>0%↓</strong><span>수동 정산 업무 감소</span>
            <div class="progress"><i></i></div>
          </div>
          <div class="metric reveal" style="--value:99.9%" data-count="99.9" data-suffix="%">
            <strong>0%</strong><span>관제 시스템 가동률</span>
            <div class="progress"><i></i></div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
