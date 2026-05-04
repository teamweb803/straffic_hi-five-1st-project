<script setup>
const year = new Date().getFullYear()
</script>

<template>
  <footer class="bg-deep text-white/80 mt-24">
    <div class="max-w-7xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-10">
      <div>
        <p class="font-headline text-3xl tracking-wider text-white">HiFive</p>
        <p class="font-mono text-xs mt-2 text-white/50">NEXT-GEN SMART TOLLING SYSTEM</p>
        <p class="text-sm mt-4 text-white/60 leading-relaxed">
          엣지에서 인식, 클라우드에서 정산.<br />
          gRPC 기반 차세대 스마트톨링 플랫폼.
        </p>
      </div>
      <div>
        <p class="font-mono text-xs text-sky">PRODUCT</p>
        <ul class="mt-3 space-y-2 text-sm">
          <li><router-link to="/solution">솔루션</router-link></li>
          <li><router-link to="/technology">기술 스택</router-link></li>
          <li><router-link to="/guide">도입 안내</router-link></li>
        </ul>
      </div>
      <div>
        <p class="font-mono text-xs text-sky">CONTACT</p>
        <ul class="mt-3 space-y-2 text-sm">
          <li>contact@hifive.io</li>
          <li>02-000-0000</li>
          <li>서울특별시 강남구</li>
        </ul>
      </div>
    </div>
    <div class="border-t border-white/10">
      <div class="max-w-7xl mx-auto px-6 py-4 text-xs text-white/40 flex flex-wrap justify-between gap-2">
        <span>© {{ year }} HiFive Inc. All rights reserved.</span>
        <span class="font-mono">v0.1.0</span>
      </div>
    </div>
  </footer>
</template>
