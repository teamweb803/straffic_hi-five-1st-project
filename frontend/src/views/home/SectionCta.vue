<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="snap-section cta-section" id="contact">
    <div class="section-inner footer-layout reveal">
      <div class="footer-main">
        <div>
          <p class="section-label">도입 문의</p>
          <h2 class="outline-title">NEXT<br>GENERATION<br>ROAD.</h2>
          <p class="cta-copy">HiFive는 AI 번호판 인식, GPS 구간 요금 계산, 실시간 관제 데이터를 하나의 운영 흐름으로 연결해 차세대 하이패스 전환의 운영 표준을 만듭니다.</p>
          <div class="footer-actions">
            <RouterLink class="btn primary" to="/contact">도입 문의하기</RouterLink>
            <RouterLink class="btn" to="/login">관리자 로그인</RouterLink>
          </div>
        </div>
        <aside class="footer-card" aria-label="HiFive footer information">
          <div class="footer-card-row"><span>회사</span><strong>HiFive Mobility Lab</strong></div>
          <div class="footer-card-row"><span>시스템</span><strong>Smart Tolling 시스템 v1.0</strong></div>
          <div class="footer-card-row"><span>구성</span><strong>AI LPR · GPS Fare · gRPC Stream</strong></div>
          <div class="footer-card-row"><span>문의</span><a href="mailto:contact@hifive.ai">contact@hifive.ai</a></div>
        </aside>
      </div>
      <div>
        <div class="cta-info">
          <span>엣지 AI 인식</span>
          <span>GPS 구간 정산</span>
          <span>실시간 관제 대시보드</span>
        </div>
        <div class="footer-bottom">
          <span>© 2026 HiFive. 스마트 모빌리티 톨링 플랫폼.</span>
          <span>정확한 신호, 멈춤 없는 흐름</span>
        </div>
      </div>
    </div>
  </section>
</template>
