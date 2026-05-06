<script setup>
// Core Engine 섹션 — 4개 엔진 카드
</script>

<template>
  <section class="snap-section core" id="core">
    <div class="section-inner">
      <p class="section-label reveal">Core Engine</p>
      <h2 class="section-title reveal">FOUR LAYERS.<br>ONE FLOW.</h2>
      <div class="engine-grid">
        <article class="engine-card reveal">
          <div class="engine-index"><span>01</span><span class="engine-tag">AI Engine</span></div>
          <div class="engine-visual">
            <svg class="mini-svg" viewBox="0 0 160 50" fill="none" role="img" aria-label="AI plate">
              <path class="wave-path" d="M0,20 Q20,5 40,20 Q60,35 80,20 Q100,5 120,20 Q140,35 160,20" stroke="#6D85FF" stroke-width="2"/>
              <path class="wave-path" d="M0,20 Q20,5 40,20 Q60,35 80,20 Q100,5 120,20 Q140,35 160,20" stroke="#B7C5E8" stroke-width="1.3" style="animation-delay:.5s"/>
              <rect x="40" y="28" width="80" height="18" rx="2" stroke="#56678F" stroke-width="1" fill="#172240"/>
              <text x="80" y="40" text-anchor="middle" fill="#DCE5FF" font-family="Fira Mono" font-size="8" letter-spacing="1.5">123가 4567</text>
              <line x1="40" y1="37" x2="120" y2="37" stroke="#7890FF" stroke-width="1.1" class="beam"/>
            </svg>
          </div>
          <h3>번호판 인식 AI</h3>
          <p>YOLO 기반 객체 탐지와 OCR 추출을 엣지에서 결합해 고속 주행 환경의 번호판을 안정적으로 식별합니다.</p>
          <div class="engine-foot"><strong>97.3%</strong>Recognition Accuracy</div>
        </article>

        <article class="engine-card reveal">
          <div class="engine-index"><span>02</span><span class="engine-tag">GPS Toll</span></div>
          <div class="engine-visual">
            <svg class="mini-svg" viewBox="0 0 160 50" fill="none" role="img" aria-label="GPS route">
              <path d="M12,44 Q50,10 80,18 Q110,26 148,6" stroke="#3A496F" stroke-width="1" stroke-dasharray="4 3"/>
              <path d="M12,44 Q50,10 80,18 Q110,26 148,6" stroke="#6D85FF" stroke-width="2.1" class="route-line"/>
              <circle cx="12" cy="44" r="4" fill="#B7C5E8"/>
              <circle cx="148" cy="6" r="3.5" fill="#6ED7B7" opacity=".8"/>
              <circle cx="12" cy="44" r="3.5" stroke="#66769C" stroke-width=".7" fill="none" class="ping1"/>
              <circle cx="148" cy="6" r="3.5" stroke="#6ED7B7" stroke-width=".7" fill="none" class="ping2"/>
              <circle cx="80" cy="18" r="3.1" fill="#7890FF"/>
              <rect x="60" y="26" width="42" height="11" rx="2" fill="#172240" stroke="#56678F" stroke-width=".7"/>
              <text x="81" y="34" text-anchor="middle" fill="#DCE5FF" font-family="Fira Mono" font-size="7" letter-spacing=".5">23.4 km</text>
            </svg>
          </div>
          <h3>GPS 구간 요금 계산</h3>
          <p>진입, 주행, 이탈 좌표를 구간 그래프로 매핑해 통행거리 기반 정산을 실시간으로 수행합니다.</p>
          <div class="engine-foot"><strong>0.3s</strong>Processing Speed</div>
        </article>

        <article class="engine-card reveal">
          <div class="engine-index"><span>03</span><span class="engine-tag">Transport</span></div>
          <div class="engine-visual">
            <svg class="mini-svg" viewBox="0 0 160 50" fill="none" role="img" aria-label="WebTransport transfer">
              <rect x="20" y="10" width="90" height="10" rx="1.5" fill="#172240" stroke="#3A496F" stroke-width=".8"/>
              <text x="14" y="18" text-anchor="end" fill="#AEB9D6" font-family="Fira Mono" font-size="7">JSON</text>
              <text x="116" y="18" fill="#AEB9D6" font-family="Fira Mono" font-size="7">100%</text>
              <rect x="20" y="30" width="27" height="10" rx="1.5" fill="#263A74" stroke="#6D85FF" stroke-width=".8"/>
              <text x="14" y="38" text-anchor="end" fill="#8EA0FF" font-family="Fira Mono" font-size="7">WT</text>
              <text x="52" y="38" fill="#8EA0FF" font-family="Fira Mono" font-size="7">30%</text>
              <rect x="126" y="16" width="30" height="14" rx="2" fill="#172240" stroke="#5D79FF" stroke-width=".8"/>
              <text x="141" y="26" text-anchor="middle" fill="#DCE5FF" font-family="Fira Mono" font-size="8" font-weight="700">-70%</text>
              <line x1="20" y1="6" x2="20" y2="46" stroke="#3A496F" stroke-width=".8"/>
            </svg>
          </div>
          <h3>WebTransport 기반 고속 통신</h3>
          <p>Protobuf 스트림으로 엣지 장비와 중앙 서버 간 이벤트 전송량과 응답 지연을 줄입니다.</p>
          <div class="engine-foot"><strong>70%↓</strong>Transfer Reduction</div>
        </article>

        <article class="engine-card reveal">
          <div class="engine-index"><span>04</span><span class="engine-tag">Dashboard</span></div>
          <div class="engine-visual">
            <svg class="mini-svg" viewBox="0 0 160 50" fill="none" role="img" aria-label="Realtime dashboard">
              <rect x="14" y="32" width="12" height="14" rx="1.5" fill="#3A496F" class="bar-up bu1"/>
              <rect x="30" y="22" width="12" height="24" rx="1.5" fill="#4A5A82" class="bar-up bu2"/>
              <rect x="46" y="26" width="12" height="20" rx="1.5" fill="#405CB8" class="bar-up bu3"/>
              <rect x="62" y="14" width="12" height="32" rx="1.5" fill="#526DE0" class="bar-up bu4"/>
              <rect x="78" y="18" width="12" height="28" rx="1.5" fill="#637BDE" class="bar-up bu5"/>
              <rect x="94" y="10" width="12" height="36" rx="1.5" fill="#7890FF" class="bar-up bu6"/>
              <line x1="10" y1="46" x2="130" y2="46" stroke="#3A496F" stroke-width=".8"/>
              <circle cx="148" cy="10" r="4" fill="#6ED7B7"/>
              <circle cx="148" cy="10" r="4" stroke="#6ED7B7" stroke-width=".7" fill="none" class="ping1" style="animation-duration:2.2s"/>
            </svg>
          </div>
          <h3>실시간 관제 모니터링</h3>
          <p>통과 로그, 예외 검수, GPS 지도, 운영 지표를 하나의 Vue 기반 관제 화면으로 연결합니다.</p>
          <div class="engine-foot"><strong>24/7</strong>Live Monitoring</div>
        </article>
      </div>
    </div>
  </section>
</template>
