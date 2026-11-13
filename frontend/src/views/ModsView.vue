<script setup lang="ts">
import UiBadge from '../components/UiBadge.vue'
import UiSearch from '../components/UiSearch.vue'
import UiProgress from '../components/UiProgress.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, upload } from '../api'
import { useNotices, useServers } from '../stores'
import type { Mod } from '../types'
import AppIcon from '../components/AppIcon.vue'
import UiButton from '../components/UiButton.vue'
import StateBadge from '../components/StateBadge.vue'
import ServerTabs from '../components/ServerTabs.vue'
const id = String(useRoute().params.id), store = useServers(), notices = useNotices()
const server = computed(() => store.servers.find(item => item.id === id))
const mods = ref<Mod[]>([]), search = ref(''), loading = ref(true), busy = ref(false), error = ref(''), progress = ref(0), uploading = ref(false), file = ref<HTMLInputElement>()
const locked = computed(() => !server.value || server.value.running || !!store.operations[id] || busy.value)
const filtered = computed(() => mods.value.filter(mod => mod.filename.toLowerCase().includes(search.value.toLowerCase())))
function size(bytes: number) { return bytes >= 1024**3 ? `${(bytes / 1024**3).toFixed(1)} GiB` : bytes >= 1024**2 ? `${(bytes / 1024**2).toFixed(1)} MiB` : `${Math.max(1, Math.ceil(bytes / 1024))} KiB` }
async function load() {
  loading.value = true; error.value = ''
  try { await store.refresh(); mods.value = (await api<{ mods: Mod[] }>(`/servers/${id}/mods`)).mods }
  catch (err) { error.value = (err as Error).message }
  finally { loading.value = false }
}
async function toggle(mod: Mod) {
  busy.value = true; error.value = ''
  try { mods.value = (await api<{ mods: Mod[] }>(`/servers/${id}/mods/state`, 'POST', { filename: mod.filename, enabled: !mod.enabled })).mods; notices.show(`${mod.filename} ${mod.enabled ? 'disabled' : 'enabled'}.`) }
  catch (err) { error.value = (err as Error).message }
  finally { busy.value = false }
}
async function uploadFiles(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files || [])
  if (!files.length) return
  busy.value = true; uploading.value = true; error.value = ''; progress.value = 0
  try {
    for (let index = 0; index < files.length; index++) {
      const data = new FormData(); data.append('file', files[index])
      mods.value = (await upload<{ mods: Mod[] }>(`/servers/${id}/mods/upload`, data, value => { progress.value = Math.round((index * 100 + value) / files.length) })).mods
    }
    notices.show(`${files.length === 1 ? 'Mod' : 'Mods'} uploaded and enabled. Changes apply on the next start.`)
  } catch (err) { const message = (err as Error).message; await load(); error.value = message }
  finally { busy.value = false; uploading.value = false; if (file.value) file.value.value = '' }
}
onMounted(load)
</script>
<template>
  <RouterLink to="/servers" class="m3e-button m3e-button--text back-link"><AppIcon name="back" />All servers</RouterLink><div class="page-heading"><div><span class="eyebrow">SERVER INSTANCE</span><h1>{{ server?.name || 'Mods' }}</h1><div v-if="server" class="instance-caption"><StateBadge :state="server.state" /><span>Make every drive your own</span></div></div><UiButton :disabled="locked" @click="file?.click()"><AppIcon name="import" />Upload mods</UiButton><input ref="file" class="sr-only" type="file" accept=".zip,application/zip" multiple aria-label="Mod ZIP files" :disabled="locked" @change="uploadFiles" /></div>
  <ServerTabs :server-id="id"><div class="section-toolbar"><h2>Mod manager <UiBadge>{{ mods.length }}</UiBadge></h2><UiSearch label="Search mods" v-model="search" placeholder="Find a mod…" /></div>
  <p v-if="server?.running || store.operations[id]" class="info-banner m3e-surface m3e-surface--container-high m3e-surface--shape-large">Stop this server before uploading, enabling or disabling mods.</p><div v-if="error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert">{{ error }}<UiButton variant="text" @click="load">Retry</UiButton></div><div v-if="uploading" class="operation-status" role="status"><UiProgress :value="progress" /><span>{{ progress < 100 ? `Uploading… ${progress}%` : 'Validating ZIP files…' }}</span></div>
  <div v-if="loading" class="empty-state m3e-card" role="status"><m3e-loading-indicator aria-label="Loading mods" /></div><div v-else-if="!mods.length" class="empty-state m3e-card"><span class="empty-icon"><AppIcon name="mods" /></span><h2>A fresh garage</h2><p>Upload vehicle or map mod ZIPs to share them with your players.</p><UiButton :disabled="locked" @click="file?.click()">Upload your first mod</UiButton></div>
  <div v-else class="mod-list m3e-list"><article v-for="mod in filtered" :key="`${mod.enabled}-${mod.filename}`" class="mod-row m3e-list-item"><span class="server-art m3e-list-item__leading"><AppIcon :name="mod.maps.length ? 'map' : 'mods'" /></span><div class="mod-details m3e-list-item__content"><h3>{{ mod.filename }}</h3><p class="muted">{{ size(mod.size) }}<span v-if="mod.maps.length"> · {{ mod.maps.map(map => map.name).join(', ') }}</span></p><p v-if="mod.error" class="inline-error">{{ mod.error }}</p></div><div class="m3e-list-item__trailing mod-actions"><UiBadge :tone="mod.enabled ? 'positive' : 'neutral'">{{ mod.enabled ? 'Enabled' : 'Disabled' }}</UiBadge><UiButton :variant="mod.enabled ? 'outlined' : 'tonal'" :disabled="locked || (!mod.enabled && !!mod.error)" :aria-label="`${mod.enabled ? 'Disable' : 'Enable'} ${mod.filename}`" @click="toggle(mod)">{{ mod.enabled ? 'Disable' : 'Enable' }}</UiButton></div></article><p v-if="!filtered.length" class="empty-state m3e-card">No mods match your search.</p></div><p class="content-footnote">Disabled ZIPs are kept outside the Client folder so BeamMP will not load them. Uploads never replace existing ZIPs. Maximum 2 GiB per file by default.</p>
  </ServerTabs>
</template>
