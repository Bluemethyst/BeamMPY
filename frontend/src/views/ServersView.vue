<script setup lang="ts">
import UiRadio from '../components/UiRadio.vue'
import UiDialog from '../components/UiDialog.vue'
import UiBadge from '../components/UiBadge.vue'
import UiSearch from '../components/UiSearch.vue'
import UiProgress from '../components/UiProgress.vue'
import UiCheck from '../components/UiCheck.vue'
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, upload } from '../api'
import { useNotices, useServers } from '../stores'
import type { Operation, Server } from '../types'
import AppIcon from '../components/AppIcon.vue'
import UiButton from '../components/UiButton.vue'
import UiField from '../components/UiField.vue'
import StateBadge from '../components/StateBadge.vue'
import PowerControls from '../components/PowerControls.vue'
const store = useServers(), notices = useNotices(), router = useRouter()
const search = ref(''), mode = ref<'create' | 'import'>('create'), name = ref(''), directory = ref(''), port = ref<number | string>(30814)
const submitting = ref(false), error = ref(''), dialog = ref<InstanceType<typeof UiDialog>>()
const archiveInput = ref<HTMLInputElement>()
const authKey = ref(''), revealKey = ref(false), importKind = ref<'local' | 'upload'>('upload'), archive = ref<File>(), progress = ref(0)
const filtered = computed(() => store.servers.filter(server => server.name.toLowerCase().includes(search.value.toLowerCase())))
const running = computed(() => store.servers.filter(server => server.running).length)
const attention = computed(() => store.servers.filter(server => server.state === 'error').length)
async function open(value: 'create' | 'import') {
  mode.value = value; error.value = ''; name.value = ''; directory.value = ''; authKey.value = ''; revealKey.value = false; archive.value = undefined; progress.value = 0
  const used = new Set(store.servers.map(server => server.port))
  let candidate = 30814
  while (used.has(candidate) && candidate < 65535) candidate++
  port.value = candidate
  await nextTick(); dialog.value?.showModal()
}
async function submit() {
  submitting.value = true; error.value = ''
  try {
    let response: { server: Server; operation?: Operation }
    if (mode.value === 'import' && importKind.value === 'upload') {
      if (!archive.value) throw new Error('Choose a server ZIP archive.')
      const data = new FormData(); data.append('name', name.value); data.append('archive', archive.value)
      response = await upload('/servers/import', data, value => { progress.value = value })
    } else response = await api(mode.value === 'create' ? '/servers' : '/servers/import', 'POST', mode.value === 'create' ? { name: name.value, port: Number(port.value), auth_key: authKey.value } : { name: name.value, directory: directory.value })
    store.update(response.server)
    if (response.operation) void store.track(response.operation)
    dialog.value?.close()
    authKey.value = ''; archive.value = undefined
    notices.show(mode.value === 'create' ? 'Instance created. Downloading BeamMP…' : 'Server imported. The original source was preserved.')
    await router.push(`/servers/${response.server.id}/console`)
  } catch (err) { error.value = (err as Error).message }
  finally { submitting.value = false }
}
</script>
<template>
  <div class="page-heading"><div><h1>All servers<span class="heading-period">.</span></h1><p class="muted">A little control. A lot of open road.</p></div><div class="heading-actions"><UiButton variant="outlined" @click="open('import')"><AppIcon name="import" />Import server</UiButton><UiButton @click="open('create')"><AppIcon name="plus" />Create server</UiButton></div></div>
  <div class="stats-grid"><div class="stat m3e-card"><span class="stat-label">TOTAL INSTANCES</span><strong>{{ store.servers.length.toString().padStart(2, '0') }}</strong><span>On this host</span></div><div class="stat m3e-card"><span class="stat-label"><span class="status-dot online"></span>RUNNING</span><strong>{{ running.toString().padStart(2, '0') }}</strong><span>Ready for the road</span></div><div class="stat m3e-card"><span class="stat-label">STOPPED</span><strong>{{ (store.servers.length - running).toString().padStart(2, '0') }}</strong><span>{{ attention ? `${attention} need attention` : 'Ready when you are' }}</span></div></div>
  <div class="section-toolbar"><h2>Server instances <UiBadge>{{ store.servers.length }}</UiBadge></h2><UiSearch label="Search servers" v-model="search" placeholder="Search instances…" /></div>
  <div v-if="store.error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert"><span>{{ store.error }}</span><UiButton variant="text" @click="store.refresh">Retry</UiButton></div>
  <div v-if="store.loading && !store.servers.length" class="empty-state m3e-card" role="status"><m3e-loading-indicator aria-label="Loading servers" /><p>Loading instances…</p></div>
  <div v-else-if="!store.servers.length" class="empty-state m3e-card"><span class="empty-icon"><AppIcon name="servers" /></span><h2>Start your first engine</h2><p>Create a fresh BeamMP server or bring an existing installation into your workspace.</p><UiButton @click="open('create')"><AppIcon name="plus" />Create your first server</UiButton></div>
  <p v-else-if="!filtered.length" class="empty-state m3e-card">No instances match “{{ search }}”.</p>
  <div v-else class="server-grid"><article v-for="server in filtered" :key="server.id" class="server-card m3e-card m3e-card--outlined" :class="{ 'is-running': server.running }"><div class="server-card-top"><span class="server-art"><AppIcon name="servers" /></span><StateBadge :state="server.state" /></div><h3><RouterLink :to="`/servers/${server.id}/console`">{{ server.name }}</RouterLink></h3><p class="server-subtitle">{{ server.version || 'Imported installation' }}</p><div class="server-metadata"><div><span>PORT</span><strong>{{ server.port ?? '—' }}</strong></div><div><span>HOST</span><strong>Local machine</strong></div></div><p v-if="server.error" class="inline-error" role="alert">{{ server.error }}</p><div v-if="store.operations[server.id]" class="operation-status" role="status"><UiProgress :value="store.operations[server.id].progress" /><span>{{ store.operations[server.id].message }}</span></div><div class="server-card-actions"><PowerControls :server="server" /><RouterLink :to="`/servers/${server.id}/console`" class="console-link m3e-icon-button" :aria-label="`Open ${server.name} console`"><AppIcon name="arrow" /></RouterLink></div></article></div>
  <div class="host-note"><AppIcon name="servers" /><span>Each instance has its own configuration, resources, and console.</span><span class="host-note-end">ONE HOST. EVERY INSTANCE.</span></div>
  <UiDialog ref="dialog" :title="mode === 'create' ? 'Create a server' : 'Import a server'" :busy="submitting">
    <p class="muted">{{ mode === 'create' ? 'Install the official stable BeamMP build in its own directory.' : 'Upload a server ZIP, or import a folder or ZIP already on this host.' }}</p>
    <form @submit.prevent="submit">
      <UiField label="Server name" v-model="name" placeholder="Weekend drives" required maxlength="250" :disabled="submitting" />
      <template v-if="mode === 'create'">
        <UiField label="Port" type="number" v-model="port" required min="1024" max="65535" hint="Choose a unique TCP and UDP port for this instance." :disabled="submitting" />
        <UiField label="AuthKey" :type="revealKey ? 'text' : 'password'" v-model="authKey" required maxlength="256" autocomplete="off" hint="Required to start the server. Use a separate key for each instance." :disabled="submitting" />
        <div class="key-help"><UiCheck v-model="revealKey" label="Show AuthKey"  /><a href="https://keymaster.beammp.com" target="_blank" rel="noopener noreferrer">Get an AuthKey</a></div>
      </template>
      <template v-else>
        <fieldset class="import-options m3e-radio-group m3e-radio-group--horizontal" :disabled="submitting"><legend>Import source</legend><UiRadio label="Upload ZIP" v-model="importKind" value="upload" name="import-source" /><UiRadio label="Local folder or ZIP" v-model="importKind" value="local" name="import-source" /></fieldset>
        <div v-if="importKind === 'upload'" class="field"><label for="server-archive" class="field-label">Server ZIP archive</label><UiButton variant="outlined" :disabled="submitting" @click="archiveInput?.click()"><AppIcon name="import" />Choose server ZIP</UiButton><span class="field-hint">{{ archive?.name || 'No archive selected' }}</span><input ref="archiveInput" class="sr-only" id="server-archive" type="file" accept=".zip,application/zip" :disabled="submitting" @change="archive = ($event.target as HTMLInputElement).files?.[0]" /><span class="field-hint">ZIP the server folder with ServerConfig.toml, its compatible executable and Resources. The original archive is kept unchanged. Maximum 2 GiB by default.</span></div>
        <UiField v-else label="Absolute directory or ZIP path" v-model="directory" placeholder="C:\\BeamMP\\MyServer or /srv/backups/server.zip" required :disabled="submitting" hint="This path is on the panel host. Folders are registered in place; ZIPs are copied into a new instance." />
        <div v-if="submitting && importKind === 'upload'" class="operation-status" role="status"><UiProgress :value="progress" /><span>{{ progress < 100 ? `Uploading… ${progress}%` : 'Checking and importing the archive…' }}</span></div>
      </template>
      <p v-if="error" class="inline-error" role="alert">{{ error }}</p><div class="modal-actions"><UiButton variant="text" :disabled="submitting" @click="dialog?.close()">Cancel</UiButton><UiButton type="submit" :busy="submitting">{{ mode === 'create' ? 'Create and install' : 'Import server' }}</UiButton></div>
    </form>
  </UiDialog>
</template>
