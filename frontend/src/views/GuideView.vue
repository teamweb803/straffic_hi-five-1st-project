<script setup>
import { ref } from 'vue'

const steps = [
  { code: '01', title: '도입 상담', desc: '도로 운영사 / 지자체와 요구사항 인터뷰. 30분 화상 미팅으로 도입 가능성과 일정을 협의합니다.' },
  { code: '02', title: '설계 검토', desc: '카메라 위치, 가상 통과선 구획, GPS 결합 방식을 함께 설계해 노선별 구성도를 산출합니다.' },
  { code: '03', title: 'PoC', desc: '1개 노선에서 1주일 PoC. 인식 정확도, 정산 정합성, 응답 지연을 자동 리포트로 제공합니다.' },
  { code: '04', title: '본도입', desc: '엣지 노드 + 백엔드 + 대시보드 통합 구축, 운영 인수인계까지 평균 8주 내 완료.' }
]

const faqs = [
  { q: '기존 하이패스와 병행 가능한가요?', a: '네, 게이트형 시스템과 병렬 운영 가능합니다. 점진적 전환을 권장합니다.' },
  { q: 'OCR 신뢰도가 낮은 차량은 어떻게 처리되나요?', a: '저신뢰 케이스는 자동으로 검수 큐에 적재되며, 관리자 보정 후 정산이 진행됩니다.' },
  { q: '오프라인 환경에서도 동작하나요?', a: '엣지 노드는 자체 큐를 보유해 네트워크 단절 시에도 이벤트가 유실되지 않습니다.' }
]

const open = ref(0)
</script>

<template>
  <div class="guide-page">
    <section class="hero">
      <p class="eyebrow">ADOPTION GUIDE · 도입안내</p>
      <h1>FROM CALL<br>TO LIVE.</h1>
      <p class="lead">
        HiFive 도입은 4단계로 진행됩니다. 평균 8주 내 본 도입까지 완료할 수 있습니다.
      </p>
    </section>

    <section class="rail-section">
      <p class="rail-eyebrow">JOURNEY · 4 STEPS</p>
      <div class="rail">
        <div class="line"><div class="scan"></div></div>
        <div class="nodes">
          <article v-for="(s, i) in steps" :key="s.code" class="node">
            <span class="dot"></span>
            <p class="step-code">{{ s.code }}</p>
            <p class="step-title">{{ s.title }}</p>
            <p class="step-desc">{{ s.desc }}</p>
            <span class="step-mono">// step {{ String(i + 1).padStart(2, '0') }}</span>
          </article>
        </div>
      </div>
    </section>

    <section class="faq-section">
      <p class="rail-eyebrow">FAQ</p>
      <h2>자주 묻는 질문</h2>
      <ul class="faq-list">
        <li
          v-for="(item, idx) in faqs"
          :key="idx"
          :class="{ 'is-open': open === idx }"
        >
          <button type="button" class="faq-q" @click="open = open === idx ? -1 : idx">
            <span class="faq-num">Q{{ String(idx + 1).padStart(2, '0') }}</span>
            <span class="faq-text">{{ item.q }}</span>
            <span class="faq-toggle">{{ open === idx ? '−' : '+' }}</span>
          </button>
          <div v-show="open === idx" class="faq-a">
            <p>{{ item.a }}</p>
          </div>
        </li>
      </ul>
    </section>

    <section class="cta">
      <div class="cta-inner">
        <p class="cta-eyebrow">CONTACT</p>
        <h2 class="cta-title">READY TO START?</h2>
        <p class="cta-copy">평균 8주 내 본 도입까지. 30분 화상 미팅으로 시작합니다.</p>
        <router-link to="/contact" class="cta-btn">도입 문의하기 →</router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
.guide-page {
  --p-deep: #080C18;
  --p-navy: #0B1840;
  --p-blue: #1B3BE8;
  --p-sky: #38BEF5;
  --p-cloud: #E8EFFE;
  --p-line: rgba(11, 24, 64, 0.12);
  --p-headline: 'Big Shoulders Display', sans-serif;
  --p-mono: 'Fira Mono', monospace;
  background: #fff;
  color: var(--p-navy);
  min-height: 100vh;
}

.eyebrow,
.rail-eyebrow,
.cta-eyebrow {
  font-family: var(--p-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-blue);
  margin: 0 0 14px;
}
.cta-eyebrow { color: var(--p-sky); }

.hero {
  padding: 100px 36px 60px;
  max-width: 1220px;
  margin: 0 auto;
}
.hero h1 {
  font-family: var(--p-headline);
  font-size: clamp(56px, 8vw, 120px);
  line-height: 0.88;
  margin: 0;
  color: var(--p-deep);
}
.hero .lead {
  margin-top: 24px;
  max-width: 620px;
  color: rgba(11, 24, 64, 0.72);
  line-height: 1.8;
}

.rail-section {
  max-width: 1220px;
  margin: 0 auto;
  padding: 60px 36px 100px;
}
.rail {
  position: relative;
  padding: 30px 0;
}
.line {
  position: absolute;
  top: 80px;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(11, 24, 64, 0.12);
  overflow: hidden;
}
.scan {
  position: absolute;
  top: 0;
  left: 0;
  width: 24%;
  height: 100%;
  background: linear-gradient(90deg, transparent, var(--p-sky), var(--p-blue), transparent);
  animation: rail-sweep 3.6s linear infinite;
}
@keyframes rail-sweep { to { transform: translateX(380%); } }
.nodes {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  position: relative;
}
.node {
  padding: 100px 18px 0;
  border-right: 1px dashed rgba(11, 24, 64, 0.12);
  position: relative;
}
.node:last-child { border-right: none; }
.dot {
  position: absolute;
  top: 71px;
  left: 18px;
  width: 18px;
  height: 18px;
  background: var(--p-blue);
  border-radius: 50%;
  box-shadow: 0 0 0 6px rgba(27, 59, 232, 0.18);
}
.step-code {
  font-family: var(--p-headline);
  font-size: 56px;
  color: var(--p-blue);
  margin: 0 0 6px;
  line-height: 1;
}
.step-title {
  font-weight: 700;
  color: var(--p-deep);
  margin: 6px 0;
  font-size: 16px;
}
.step-desc {
  color: rgba(11, 24, 64, 0.7);
  font-size: 13px;
  line-height: 1.6;
  margin: 0 0 16px;
}
.step-mono {
  font-family: var(--p-mono);
  font-size: 11px;
  color: var(--p-sky);
  letter-spacing: 1px;
}

.faq-section {
  background: var(--p-cloud);
  padding: 80px 36px 100px;
}
.faq-section > * { max-width: 1220px; margin-left: auto; margin-right: auto; }
.faq-section h2 {
  font-family: var(--p-headline);
  font-size: clamp(36px, 4.5vw, 60px);
  margin: 0 0 36px;
  color: var(--p-deep);
}
.faq-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
.faq-list li {
  background: #fff;
  border: 1px solid var(--p-line);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 200ms ease, box-shadow 200ms ease;
}
.faq-list li.is-open {
  border-color: var(--p-blue);
  box-shadow: 0 12px 28px rgba(27, 59, 232, 0.1);
}
.faq-q {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  background: transparent;
  border: none;
  padding: 22px 24px;
  text-align: left;
  cursor: pointer;
  font-family: inherit;
  color: inherit;
}
.faq-num {
  font-family: var(--p-mono);
  font-size: 12px;
  color: var(--p-sky);
  letter-spacing: 1px;
}
.faq-text {
  flex: 1;
  font-weight: 700;
  color: var(--p-deep);
  font-size: 15px;
}
.faq-toggle {
  font-family: var(--p-headline);
  font-size: 28px;
  color: var(--p-blue);
  line-height: 1;
}
.faq-a {
  padding: 0 24px 22px 56px;
  color: rgba(11, 24, 64, 0.72);
  line-height: 1.8;
  font-size: 14px;
}

.cta {
  background: #0A1024;
  color: #fff;
  padding: 80px 36px;
}
.cta-inner { max-width: 1220px; margin: 0 auto; }
.cta-title {
  font-family: var(--p-headline);
  font-size: clamp(40px, 6vw, 80px);
  margin: 0 0 18px;
  color: #fff;
}
.cta-copy {
  color: #AEB9D6;
  margin: 0 0 32px;
  line-height: 1.7;
}
.cta-btn {
  display: inline-flex;
  align-items: center;
  padding: 14px 28px;
  background: var(--p-blue);
  color: #fff;
  font-family: var(--p-headline);
  font-size: 20px;
  letter-spacing: 1px;
  border-radius: 6px;
  transition: background 160ms ease, transform 160ms ease;
}
.cta-btn:hover { background: #1530c5; transform: translateY(-2px); }

@media (max-width: 900px) {
  .nodes { grid-template-columns: repeat(2, 1fr); }
  .node:nth-child(2) { border-right: none; }
  .node:nth-child(1),
  .node:nth-child(2) { padding-bottom: 40px; }
}
@media (max-width: 560px) {
  .nodes { grid-template-columns: 1fr; }
  .node { border-right: none; border-bottom: 1px dashed rgba(11, 24, 64, 0.12); padding-bottom: 30px; }
  .node:last-child { border-bottom: none; }
  .line { display: none; }
  .dot { display: none; }
}
</style>
