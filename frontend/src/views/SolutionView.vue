<script setup>
const solutions = [
  {
    code: '01',
    title: 'Edge OCR',
    desc: 'YOLOv8 + EasyOCR/PaddleOCR 기반 엣지 인식. 카메라 단에서 즉시 차량/번호판 추출.'
  },
  {
    code: '02',
    title: 'Crossing Engine',
    desc: '가상 통과선 알고리즘이 ENTRY / EXIT 을 결정. GPS 와 결합해 구간 요금 계산.'
  },
  {
    code: '03',
    title: 'gRPC Stream',
    desc: '엣지 → 백엔드 사이를 Protobuf 바이너리로 압축 송신. JSON 대비 70% 페이로드 감소.'
  },
  {
    code: '04',
    title: 'Review Queue',
    desc: 'OCR 저신뢰도 케이스를 검수 큐로 자동 분리. 관리자 보정 후 정산 반영.'
  },
  {
    code: '05',
    title: 'Operator Dashboard',
    desc: '실시간 KPI, 통과 로그, GPS 구간 현황을 한 화면에서 모니터링.'
  },
  {
    code: '06',
    title: 'Open API',
    desc: '회원/요금/검수 API 와 통과 이벤트 webhook. 외부 정산 시스템과 즉시 연동.'
  }
]
</script>

<template>
  <section class="py-24 bg-white">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">SOLUTION</p>
      <h1 class="font-headline text-5xl mt-2 text-deep">FROM CAMERA TO BILL.</h1>
      <p class="mt-6 max-w-2xl text-navy/70 leading-relaxed">
        HiFive 는 도로의 카메라부터 정산 시스템까지를 하나의 흐름으로 연결합니다.
      </p>
    </div>
  </section>

  <section class="py-16 bg-cloud">
    <div class="max-w-7xl mx-auto px-6 grid md:grid-cols-2 lg:grid-cols-3 gap-5">
      <article v-for="s in solutions" :key="s.code" class="card hover:border-brand transition">
        <span class="font-mono text-xs text-brand">{{ s.code }}</span>
        <h3 class="text-lg font-bold mt-3 text-navy">{{ s.title }}</h3>
        <p class="mt-3 text-sm text-navy/70 leading-relaxed">{{ s.desc }}</p>
      </article>
    </div>
  </section>

  <section class="py-24 bg-white">
    <div class="max-w-7xl mx-auto px-6">
      <p class="font-mono text-xs tracking-[0.3em] text-brand">PIPELINE</p>
      <h2 class="font-headline text-4xl mt-2 text-deep">END-TO-END FLOW.</h2>
      <ol class="mt-10 space-y-3 text-sm">
        <li class="card flex gap-4 items-start">
          <span class="font-mono text-brand">01</span>
          <p><strong class="text-deep">차로 카메라</strong> — 차량/번호판 ROI 추출 (YOLOv8 + OpenCV).</p>
        </li>
        <li class="card flex gap-4 items-start">
          <span class="font-mono text-brand">02</span>
          <p><strong class="text-deep">엣지 FastAPI</strong> — OCR + 가상 통과선 판정 + GPS 결합.</p>
        </li>
        <li class="card flex gap-4 items-start">
          <span class="font-mono text-brand">03</span>
          <p><strong class="text-deep">gRPC 스트리밍</strong> — Protobuf 바이너리로 백엔드까지 송신.</p>
        </li>
        <li class="card flex gap-4 items-start">
          <span class="font-mono text-brand">04</span>
          <p><strong class="text-deep">Spring Boot 백엔드</strong> — 정산 / 검수 / 회원 / 게시판 처리.</p>
        </li>
        <li class="card flex gap-4 items-start">
          <span class="font-mono text-brand">05</span>
          <p><strong class="text-deep">Vue 관제 대시보드</strong> — 실시간 모니터링 + 저신뢰 차량 보정.</p>
        </li>
      </ol>
    </div>
  </section>
</template>
