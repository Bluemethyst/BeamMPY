<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { useServers, useSession, useNotices } from '../stores'
import type { Statistics } from '../types'
import AppIcon from '../components/AppIcon.vue'
import ServerTabs from '../components/ServerTabs.vue'
import UiButton from '../components/UiButton.vue'
import UiCheck from '../components/UiCheck.vue'
import StateBadge from '../components/StateBadge.vue'
import StatisticsChart from '../components/StatisticsChart.vue'
const id = String(useRoute().params.id), store = useServers(), session = useSession(), notices = useNotices()
const rangeMenuId = useId()
const server = computed(() => store.servers.find(item => item.id === id))
const ranges = [{ value: '1h', label: 'Last hour' }, { value: '24h', label: 'Last 24 hours' }, { value: '7d', label: 'Last 7 days' }, { value: '30d', label: 'Last 30 days' }]
const range = ref('1h'), data = ref<Statistics>(), error = ref(''), busy = ref(false), loading = ref(true)
const live = computed(() => error.value ? undefined : data.value?.live)
const status = computed(() => ({ live: 'Live', stale: 'Observations are stale', stopped: 'Server stopped', unavailable: 'Waiting for resource observations' })[live.value?.status ?? 'unavailable'])
let active = true, generation = 0, timer: ReturnType<typeof setTimeout> | undefined
function number(value: number | null | undefined, unit = '') { return value == null ? '—' : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}${unit}` }
function uptime(value: number | null | undefined) {
  if (value == null) return '—'
  const minutes = Math.floor(value / 60), hours = Math.floor(minutes / 60), days = Math.floor(hours / 24)
  return days ? `${days}d ${hours % 24}h` : hours ? `${hours}h ${minutes % 60}m` : `${minutes}m ${Math.floor(value % 60)}s`
}
async function load() {
  if (timer) clearTimeout(timer)
  const started = ++generation
  try {
    const result = await api<Statistics>(`/servers/${id}/statistics?range=${range.value}`)
    if (active && started === generation && result.server_id === id) { data.value = result; error.value = '' }
  } catch (err) { if (active && started === generation) error.value = (err as Error).message }
  finally {
    if (active && started === generation) { loading.value = false; timer = setTimeout(() => { if (document.hidden) { timer = setTimeout(() => void load(), 5000) } else void load() }, 5000) }
  }
}
function select(event: CustomEvent<{ value: string }>) { range.value = event.detail.value; loading.value = true; void load() }
async function telemetry(enabled: boolean) {
  busy.value = true
  try {
    await api(`/servers/${id}/statistics/telemetry`, 'PUT', { enabled })
    notices.show(enabled ? 'Player statistics enabled. Start this server to begin collecting.' : 'Player statistics disabled. Existing history was kept.')
    if (active) await load()
  } catch (err) { if (active) error.value = (err as Error).message }
  finally { busy.value = false }
}
onMounted(async () => { await store.refresh(); if (active) void load() })
onUnmounted(() => { active = false; generation++; if (timer) clearTimeout(timer) })
</script>
<template>
  <RouterLink to="/servers" class="m3e-button m3e-button--text back-link"><AppIcon name="back" />All servers</RouterLink>
  <div class="page-heading"><div><span class="eyebrow">SERVER INSTANCE</span><h1>{{ server?.name || 'Statistics' }}</h1><div v-if="server" class="instance-caption"><StateBadge :state="server.state" /><span>Statistics for this server</span></div></div></div>
  <ServerTabs :server-id="id">
    <div class="section-toolbar"><h2>Statistics</h2><div class="statistics-actions"><UiButton :id="rangeMenuId" variant="outlined"><AppIcon name="date_range" />{{ ranges.find(item => item.value === range)?.label }}<AppIcon name="expand" /></UiButton><UiButton variant="text" :disabled="loading" @click="load">Refresh</UiButton></div></div>
    <m3e-menu :anchor="rangeMenuId" label="Statistics time range" @action="select($event)"><m3e-menu-item v-for="item in ranges" :key="item.value" type="radio" :value="item.value" :checked.prop="range === item.value">{{ item.label }}</m3e-menu-item></m3e-menu>
    <div v-if="error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert">{{ error }} Previously collected history may still be shown.<UiButton variant="text" @click="load">Retry</UiButton></div>
    <div v-if="loading && !data" class="empty-state m3e-card" role="status"><m3e-loading-indicator aria-label="Loading statistics" /></div>
    <template v-if="data">
      <p class="muted statistics-status" role="status">{{ error ? 'Unable to refresh statistics' : status }}<span v-if="live?.time"> · Last observation {{ new Date(live.time * 1000).toLocaleTimeString() }}</span></p>
      <div class="statistics-cards">
        <article class="statistics-value m3e-card"><span class="stat-label">SERVER CPU</span><strong>{{ number(live?.cpu, '%') }}</strong><span class="muted">100% = one logical CPU core</span></article>
        <article class="statistics-value m3e-card"><span class="stat-label">SERVER MEMORY</span><strong>{{ number(live?.memory) }} <small>MiB</small></strong><span class="muted">Resident memory of this process</span></article>
        <article class="statistics-value m3e-card"><span class="stat-label">UPTIME</span><strong>{{ uptime(live?.uptime) }}</strong><span class="muted">Since this server started</span></article>
        <article class="statistics-value m3e-card"><span class="stat-label">PLAYERS ONLINE</span><strong>{{ number(live?.players) }}</strong><span class="muted">{{ !data.telemetry_enabled ? 'Player statistics disabled' : live?.player_status === 'live' ? 'Current server count' : 'Waiting for player observations' }}</span></article>
      </div>
      <div class="statistics-charts"><StatisticsChart title="CPU usage" metric="cpu" unit="%" :points="data.history" :bucket-seconds="data.bucket_seconds" /><StatisticsChart title="Memory usage" metric="memory" unit="MiB" :points="data.history" :bucket-seconds="data.bucket_seconds" /></div>
      <section class="statistics-players" aria-label="Player activity"><div class="section-toolbar"><h3>Player activity</h3><p class="muted">Selected period · {{ number(data.summary.joins) }} successful joins · {{ number(data.summary.peak_players) }} peak online</p></div>
        <div v-if="session.user?.is_admin" class="statistics-plugin m3e-card m3e-card--outlined"><UiCheck label="Collect player statistics" :model-value="data.telemetry_enabled" :disabled="busy || !server || server.running || !!store.operations[id]" @update:model-value="telemetry" /><p class="muted">Enable while stopped to install the BeamMPY server plugin. It collects counts and successful joins without names or chat. No client mod is needed. Private instance resources are required.</p><p v-if="server?.running || store.operations[id]" class="muted">Stop this server and wait for its operation to finish to change player collection.</p></div>
        <p v-else-if="!data.telemetry_enabled" class="muted">Ask the administrator to enable player statistics for this server.</p>
        <StatisticsChart title="Players online" metric="players" unit="" :points="data.history" :bucket-seconds="data.bucket_seconds" />
      </section>
      <p class="content-footnote">Only this BeamMP server process is measured. Collection continues while the panel runs, even with no dashboard open. Minute history is kept for 30 days. Joins include repeat visits; player bars show peak concurrent counts. Missing observations are gaps.</p>
    </template>
  </ServerTabs>
</template>
