<script setup lang="ts">
import UiBadge from '../components/UiBadge.vue'
import UiSearch from '../components/UiSearch.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { useNotices, useServers, useSession } from '../stores'
import type { MapChoice } from '../types'
import AppIcon from '../components/AppIcon.vue'
import UiButton from '../components/UiButton.vue'
import StateBadge from '../components/StateBadge.vue'
import ServerTabs from '../components/ServerTabs.vue'
const id = String(useRoute().params.id), store = useServers(), notices = useNotices()
const server = computed(() => store.servers.find(item => item.id === id))
const maps = ref<MapChoice[]>([]), current = ref(''), search = ref(''), loading = ref(true), busy = ref(false), error = ref('')
const locked = computed(() => !useSession().can('maps', id) || !server.value || server.value.running || !!store.operations[id] || busy.value)
const filtered = computed(() => maps.value.filter(item => `${item.name} ${item.mod || ''}`.toLowerCase().includes(search.value.toLowerCase())))
async function load() {
  loading.value = true; error.value = ''
  try { await store.refresh(); const data = await api<{ maps: MapChoice[]; current: string }>(`/servers/${id}/maps`); maps.value = data.maps; current.value = data.current }
  catch (err) { error.value = (err as Error).message }
  finally { loading.value = false }
}
async function select(map: MapChoice) {
  busy.value = true; error.value = ''
  try { const data = await api<{ maps: MapChoice[]; current: string }>(`/servers/${id}/maps`, 'PUT', { path: map.path }); maps.value = data.maps; current.value = data.current; notices.show(`${map.name} selected. It will load on the next start.`) }
  catch (err) { error.value = (err as Error).message }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <RouterLink to="/servers" class="m3e-button m3e-button--text back-link"><AppIcon name="back" />All servers</RouterLink><div class="page-heading"><div><span class="eyebrow">SERVER INSTANCE</span><h1>{{ server?.name || 'Maps' }}</h1><div v-if="server" class="instance-caption"><StateBadge :state="server.state" /><span>Choose your next destination</span></div></div></div>
  <ServerTabs :server-id="id"><div class="section-toolbar"><h2>Map manager <UiBadge>{{ maps.length }}</UiBadge></h2><UiSearch label="Search maps" v-model="search" placeholder="Find a map…" /></div>
  <p v-if="server?.running || store.operations[id]" class="info-banner m3e-surface m3e-surface--container-high m3e-surface--shape-large">Stop this server and wait for its operation to finish before changing maps.</p><div v-if="error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert">{{ error }}<UiButton variant="text" @click="load">Retry</UiButton></div>
  <div v-if="loading" class="empty-state m3e-card" role="status"><m3e-loading-indicator aria-label="Loading maps" /></div>
  <template v-else><div class="map-grid"><article v-for="map in filtered" :key="map.path" class="map-card m3e-card m3e-card--outlined" :class="{ selected: current === map.path }"><div class="map-card-top"><span class="map-art"><AppIcon name="map" /></span><UiBadge>{{ map.kind === 'stock' ? 'Stock map' : 'Custom map' }}</UiBadge></div><h2>{{ map.name }}</h2><p class="muted">{{ map.mod || (map.kind === 'stock' ? 'Included with BeamNG.drive' : 'Map mod is not available') }}</p><code>{{ map.path }}</code><UiButton :variant="current === map.path ? 'tonal' : 'outlined'" :disabled="locked || !map.enabled || current === map.path" @click="select(map)"><AppIcon v-if="current === map.path" name="check" />{{ current === map.path ? 'Selected map' : map.enabled ? 'Use this map' : 'Enable its mod first' }}</UiButton></article></div><p v-if="!filtered.length" class="empty-state m3e-card">No maps match your search.</p><p class="content-footnote">Custom maps appear automatically when their ZIPs contain a levels folder and info.json. <RouterLink :to="`/servers/${id}/mods`">Manage map mods</RouterLink></p></template>
  </ServerTabs>
</template>
