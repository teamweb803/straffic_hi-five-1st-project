<script setup>
const steps = [
  { code: '01', title: '도입 상담', desc: '도로 운영사 / 지자체와 요구사항 인터뷰. 30분 화상 미팅.' },
  { code: '02', title: '설계 검토', desc: '카메라 위치, 가상 통과선 구획, GPS 결합 방식을 함께 설계.' },
  { code: '03', title: 'PoC', desc: '1개 노선에서 1주일 PoC. KPI 자동 리포트 제공.' },
  { code: '04', title: '본도입', desc: '엣지 노드 + 백엔드 + 대시보드 통합 구축, 운영 인수인계.' }
]

const faqs = [
  { q: '기존 하이패스와 병행 가능한가요?', a: '네, 게이트 형 시스템과 병렬 운영 가능합니다. 점진적 전환을 권장합니다.' },
  { q: 'OCR 신뢰도가 낮은 차량은 어떻게 처리되나요?', a: '저신뢰 케이스는 자동으로 검수 큐에 적재되며, 관리자 보정 후 정산이 진행됩니다.' },
  { q: '오프라인 환경에서도 동작하나요?', a: '엣지 노드는 자체 큐를 보유해 네트워크 단절 시에도 이벤트가 유실되지 않습니다.' }
]
</script>

<template>
  <section class="py-24 bg-white">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">ADOPTION GUIDE</p>
      <h1 class="font-headline text-5xl mt-2 text-deep">FROM CALL TO LIVE.</h1>
      <p class="mt-6 max-w-2xl text-navy/70 leading-relaxed">
        HiFive 도입은 4단계로 진행됩니다. 평균 8주 내 본 도입까지 완료할 수 있습니다.
      </p>
    </div>
  </section>

  <section class="py-16 bg-cloud">
    <div class="max-w-7xl mx-auto px-6 grid md:grid-cols-2 lg:grid-cols-4 gap-5">
      <article v-for="s in steps" :key="s.code" class="card">
        <span class="font-mono text-xs text-brand">{{ s.code }}</span>
        <h3 class="text-lg font-bold mt-3 text-navy">{{ s.title }}</h3>
        <p class="mt-3 text-sm text-navy/70 leading-relaxed">{{ s.desc }}</p>
      </article>
    </div>
  </section>

  <section class="py-24">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">FAQ</p>
      <h2 class="font-headline text-4xl mt-2 text-deep">자주 묻는 질문</h2>
      <ul class="mt-10 space-y-3">
        <li v-for="(item, idx) in faqs" :key="idx" class="card">
          <p class="font-bold text-deep">Q. {{ item.q }}</p>
          <p class="mt-2 text-sm text-navy/70 leading-relaxed">A. {{ item.a }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>
