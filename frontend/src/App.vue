<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

// home route uses its own site-header / cta-section.
// Other routes show the global AppHeader / AppFooter.
const useGlobalChrome = computed(() => route.name !== 'home')

onMounted(() => {
  auth.hydrate()
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <AppHeader v-if="useGlobalChrome" />
    <main class="flex-1">
      <router-view />
    </main>
    <AppFooter v-if="useGlobalChrome" />
  </div>
</template>
