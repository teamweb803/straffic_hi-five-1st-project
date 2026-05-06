<script setup>
const stacks = [
  { layer: 'AI / Vision', items: ['YOLOv8', 'OpenCV', 'EasyOCR', 'PaddleOCR'] },
  { layer: 'Edge / Ingress', items: ['WebTransport', 'aioquic', 'FastAPI', 'Protobuf'] },
  { layer: 'Backend', items: ['Spring Boot 3', 'Spring Security', 'JPA', 'PostgreSQL'] },
  { layer: 'Frontend', items: ['Vue.js 3', 'Pinia', 'Vue Router', 'Tailwind CSS'] },
  { layer: 'Infrastructure', items: ['GPS 연동', '가상 통과선 알고리즘', 'Docker', 'CI/CD'] }
]
</script>

<template>
  <section class="py-24 bg-deep text-white">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-sky">TECH STACK</p>
      <h1 class="font-headline text-5xl mt-2">BUILT ON OPEN STACKS.</h1>
      <p class="mt-6 max-w-2xl text-white/70 leading-relaxed">
        HiFive 는 검증된 오픈소스 위에서 동작합니다. 엣지부터 프론트까지 모두 모던하게.
      </p>
    </div>
  </section>

  <section class="py-16 bg-cloud">
    <div class="max-w-7xl mx-auto px-6 grid md:grid-cols-2 gap-5">
      <article v-for="stack in stacks" :key="stack.layer" class="card">
        <p class="font-mono text-xs text-brand">{{ stack.layer.toUpperCase() }}</p>
        <h3 class="font-headline text-2xl text-deep mt-2">{{ stack.layer }}</h3>
        <div class="mt-4 flex flex-wrap gap-2">
          <span
            v-for="item in stack.items"
            :key="item"
            class="text-xs font-semibold px-3 py-1 rounded-full bg-white border border-line text-navy"
          >{{ item }}</span>
        </div>
      </article>
    </div>
  </section>

  <section class="py-24">
    <div class="max-w-7xl mx-auto px-6 grid md:grid-cols-3 gap-5">
      <div class="card">
        <p class="font-mono text-xs text-brand">PERFORMANCE</p>
        <h3 class="font-headline text-3xl mt-2 text-deep">42ms</h3>
        <p class="text-sm text-navy/70 mt-3">P95 처리 지연. 엣지에서 백엔드까지 round-trip.</p>
      </div>
      <div class="card">
        <p class="font-mono text-xs text-brand">PAYLOAD</p>
        <h3 class="font-headline text-3xl mt-2 text-deep">-70%</h3>
        <p class="text-sm text-navy/70 mt-3">Protobuf 직렬화로 JSON 대비 페이로드 감소.</p>
      </div>
      <div class="card">
        <p class="font-mono text-xs text-brand">ACCURACY</p>
        <h3 class="font-headline text-3xl mt-2 text-deep">97.3%</h3>
        <p class="text-sm text-navy/70 mt-3">번호판 OCR 평균 신뢰도 (노이즈 환경 포함).</p>
      </div>
    </div>
  </section>
</template>
