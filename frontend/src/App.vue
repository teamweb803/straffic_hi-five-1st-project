<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

const chromeHiddenRoutes = ['home', 'dashboard', 'master-admin']
const useGlobalChrome = computed(() => !chromeHiddenRoutes.includes(route.name))
const isDashboardRoute = computed(() => ['dashboard', 'master-admin'].includes(route.name))

onMounted(() => {
  auth.hydrate()
})

watch(
  isDashboardRoute,
  (active) => {
    document.documentElement.classList.toggle('dashboard-route-active', active)
    document.body.classList.toggle('dashboard-route-active', active)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  document.documentElement.classList.remove('dashboard-route-active')
  document.body.classList.remove('dashboard-route-active')
})
</script>

<template>
  <div class="min-h-screen flex flex-col" :class="{ 'dashboard-app-shell': isDashboardRoute }">
    <AppHeader v-if="useGlobalChrome" />
    <main class="flex-1" :class="{ 'dashboard-app-main': isDashboardRoute }">
      <router-view />
    </main>
    <AppFooter v-if="useGlobalChrome" />
  </div>
</template>

<style>
html.dashboard-route-active,
body.dashboard-route-active {
  width: 100%;
  height: 100%;
  min-height: 100%;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden;
  background: #eef3f8;
}

body.dashboard-route-active #app {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100dvh;
  min-height: 100dvh;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden;
  background: #eef3f8;
}

.dashboard-app-shell {
  position: fixed;
  inset: 0;
  display: block;
  width: 100vw;
  height: 100dvh;
  min-height: 100dvh;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden;
  background: #eef3f8;
}

.dashboard-app-main {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  margin: 0 !important;
  padding: 0 !important;
  overflow: auto;
  background: #eef3f8;
}

.dashboard-app-main .master-shell,
.dashboard-app-main .ops-shell {
  width: 100%;
  min-width: 1440px;
  min-height: 100%;
  height: auto;
  margin: 0;
}
</style>
