<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

const chromeHiddenRoutes = ['home', 'dashboard', 'dashboard-compact', 'master-admin']
const useGlobalChrome = computed(() => !chromeHiddenRoutes.includes(route.name))

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
