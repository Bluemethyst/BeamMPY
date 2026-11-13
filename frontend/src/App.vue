<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNotices, useServers, useSession } from './stores'
import AppIcon from './components/AppIcon.vue'
import UiButton from './components/UiButton.vue'
import UiIconButton from './components/UiIconButton.vue'
import AppearanceMenu from './components/AppearanceMenu.vue'
import { useAppearance } from './appearance'
import { version } from '../package.json'
import AppNotices from './components/AppNotices.vue'
const session = useSession(), servers = useServers(), notices = useNotices()
useAppearance()
const router = useRouter(), route = useRoute()
const menuOpen = ref(false)
const mobileMedia = matchMedia('(max-width: 760px)'), mobile = ref(mobileMedia.matches)
function resizeNavigation() { mobile.value = mobileMedia.matches; menuOpen.value = false }
mobileMedia.addEventListener('change', resizeNavigation)
const destination = computed(() => ['/account', '/users'].includes(route.path) ? route.path : route.params.id ? `/servers/${String(route.params.id)}/console` : '/servers')
function navigate(event: CustomEvent<{ value: string }>) { event.preventDefault(); void router.push(event.detail.value) }
function drawerChanged(event: CustomEvent<{ open: boolean }>) { menuOpen.value = event.detail.open }
const bootstrapError = ref('')
router.onError(error => { bootstrapError.value = error.message })
let poll: ReturnType<typeof setInterval> | undefined
watch(() => session.user, user => {
  if (poll) clearInterval(poll)
  if (user && !user.must_change_password) { void servers.refresh(); poll = setInterval(() => { if (!document.hidden) void servers.refresh() }, 2000) }
  else servers.reset()
}, { immediate: true })
watch(() => route.fullPath, () => { menuOpen.value = false })
onUnmounted(() => { if (poll) clearInterval(poll); mobileMedia.removeEventListener('change', resizeNavigation) })
async function logout() {
  try { await session.logout(); await router.replace('/login') }
  catch (err) { notices.show((err as Error).message, true) }
}
function reload() { location.reload() }
</script>
<template>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <div v-if="bootstrapError" class="connection-screen"><h1>Unable to reach the panel</h1><p>{{ bootstrapError }}</p><UiButton @click="reload">Reconnect</UiButton></div>
  <div v-else-if="!session.ready" class="connection-screen" role="status"><m3e-loading-indicator aria-label="Connecting" /><p>Connecting to BeamMPY…</p></div>
  <template v-else>
    <div v-if="session.user" class="application">
      <m3e-navigation-drawer :key="mobile ? 'modal' : 'permanent'" class="workspace-drawer" :variant="mobile ? 'modal' : 'permanent'" label="Main navigation" dialog-label="Workspace navigation" :open.prop="menuOpen" :selected.prop="destination" @selection-change="navigate($event)" @open-change="drawerChanged($event)">
        <RouterLink to="/servers" class="brand" aria-label="BeamMPY home"><span class="brand-mark"><AppIcon name="servers" /></span><span>BeamM<span class="brand-p">P</span><span class="brand-y">Y</span><small>SERVER CONTROLLER</small></span></RouterLink>
        <m3e-navigation-item value="/servers" icon="dns" :badge="String(servers.servers.length)">All servers</m3e-navigation-item>
        <m3e-navigation-item value="/account" icon="person">My account</m3e-navigation-item>
        <m3e-navigation-item v-if="session.user.is_admin" value="/users" icon="group">Users</m3e-navigation-item>
        <div v-if="servers.servers.length" class="m3e-navigation-drawer__headline">Your instances</div>
        <m3e-navigation-item v-for="server in servers.servers" :key="server.id" :value="`/servers/${server.id}/console`" :icon="server.running ? 'play_circle' : 'dns'">{{ server.name }}</m3e-navigation-item>
        <div class="sidebar-bottom"><div class="local-label"><AppIcon name="check_circle" />Local host</div><p>Built for the open road.</p><span class="version-label">BeamMPY · v{{ version }}</span></div>
      </m3e-navigation-drawer>
      <div class="main-shell">
        <header class="m3e-top-app-bar topbar"><div v-if="mobile" class="m3e-top-app-bar__navigation"><UiIconButton label="Toggle navigation" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen"><AppIcon name="menu" /></UiIconButton></div><div class="m3e-top-app-bar__actions"><span class="m3e-badge m3e-badge--large info-badge user-avatar" :title="session.user.username">{{ session.user.username[0]?.toUpperCase() }}</span><AppearanceMenu /><UiIconButton label="Log out" @click="logout"><AppIcon name="logout" /></UiIconButton></div></header>
        <main id="main-content" class="main-content" tabindex="-1"><RouterView :key="route.fullPath" /></main>
        <footer class="page-footer">BeamMPY <span>Independent, open source server management</span></footer>
      </div>
    </div>
    <main v-else id="main-content" class="auth-shell"><RouterView :key="route.path" /></main>
  </template>
  <AppNotices />
</template>
