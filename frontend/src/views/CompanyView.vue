<script setup>
const milestones = [
  { year: '2024', title: '창립', desc: '엣지 기반 스마트톨링 R&D 시작' },
  { year: '2025', title: '시범 사업', desc: '도시고속도로 1개 노선에서 PoC 진행' },
  { year: '2026', title: '확장', desc: 'gRPC 기반 차세대 톨링 시스템 정식 출시' }
]
</script>

<template>
  <section class="bg-deep text-white py-24">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-sky">ABOUT HIFIVE</p>
      <h1 class="font-headline text-5xl md:text-6xl mt-4">
        WE BUILD<br />THE INVISIBLE TOLL.
      </h1>
      <p class="mt-8 max-w-2xl text-white/70 leading-relaxed">
        HiFive 는 게이트 없이 흐르는 도로를 만드는 차세대 스마트톨링 기업입니다.
        엣지 컴퓨팅 + AI 비전 + gRPC 기반 분산 처리로,
        하이패스의 한계를 넘는 다음 세대 통행 인프라를 설계합니다.
      </p>
    </div>
  </section>

  <section class="py-24">
    <div class="max-w-7xl mx-auto px-6 grid md:grid-cols-3 gap-6">
      <div class="card">
        <p class="font-mono text-xs text-brand">MISSION</p>
        <h3 class="font-headline text-2xl mt-2 text-deep">FREE FLOW.</h3>
        <p class="text-sm text-navy/70 mt-3 leading-relaxed">
          물리적 게이트 없이 정확하게 통행료를 정산해, 도로의 흐름을 멈추지 않게 합니다.
        </p>
      </div>
      <div class="card">
        <p class="font-mono text-xs text-brand">VISION</p>
        <h3 class="font-headline text-2xl mt-2 text-deep">SMART HIGHWAY.</h3>
        <p class="text-sm text-navy/70 mt-3 leading-relaxed">
          전국 모든 유료 도로를 단일 플랫폼으로 연결하는 차세대 인프라.
        </p>
      </div>
      <div class="card">
        <p class="font-mono text-xs text-brand">VALUES</p>
        <h3 class="font-headline text-2xl mt-2 text-deep">EDGE FIRST.</h3>
        <p class="text-sm text-navy/70 mt-3 leading-relaxed">
          모든 결정은 가장 가까운 엣지에서. 빠르고 정확하게.
        </p>
      </div>
    </div>
  </section>

  <section class="py-24 bg-cloud">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">MILESTONES</p>
      <h2 class="font-headline text-4xl mt-2 text-deep">JOURNEY.</h2>
      <ol class="mt-12 grid md:grid-cols-3 gap-6">
        <li v-for="m in milestones" :key="m.year" class="card">
          <p class="font-headline text-3xl text-brand">{{ m.year }}</p>
          <p class="font-bold text-navy mt-2">{{ m.title }}</p>
          <p class="text-sm text-navy/70 mt-2">{{ m.desc }}</p>
        </li>
      </ol>
    </div>
  </section>
</template>
