<script setup lang="ts">
import UiCheck from '../components/UiCheck.vue'
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useNotices, useServers, useSession } from '../stores'
import type { Settings } from '../types'
import AppIcon from '../components/AppIcon.vue'
import ServerTabs from '../components/ServerTabs.vue'
import UiButton from '../components/UiButton.vue'
import UiField from '../components/UiField.vue'
import StateBadge from '../components/StateBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
const route = useRoute(), store = useServers(), notices = useNotices(), id = String(route.params.id)
const router = useRouter()
const deleteOpen = ref(false), deleteFiles = ref(false), deletionName = ref(''), deleting = ref(false), deletionError = ref(''), removed = ref(false)
const server = computed(() => store.servers.find(item => item.id === id))
const settings = ref<Settings>(), saved = ref(''), authKey = ref(''), replaceKey = ref(false), loading = ref(true), busy = ref(false), error = ref('')
const dirty = computed(() => settings.value && (JSON.stringify(settings.value) !== saved.value || replaceKey.value))
const locked = computed(() => !server.value || server.value.running || !!store.operations[id])
const leaveDialog = ref(false)
let leave: ((value: boolean) => void) | undefined
onBeforeRouteLeave(() => { if (removed.value || !dirty.value || !useSession().user) return true; leaveDialog.value = true; return new Promise<boolean>(resolve => { leave = resolve }) })
async function load() {
  loading.value = true; error.value = ''
  try { await store.refresh(); settings.value = (await api<{ config: Settings }>(`/servers/${id}/config`)).config; saved.value = JSON.stringify(settings.value) }
  catch (err) { error.value = (err as Error).message }
  finally { loading.value = false }
}
async function save() {
  if (!settings.value) return
  busy.value = true; error.value = ''
  try {
    const { has_auth_key, AuthKey, Map, ...values } = settings.value
    const body = replaceKey.value ? { ...values, AuthKey: authKey.value } : values
    settings.value = (await api<{ config: Settings }>(`/servers/${id}/config`, 'PUT', body)).config
    saved.value = JSON.stringify(settings.value); authKey.value = ''; replaceKey.value = false
    await store.refresh(); notices.show('Configuration saved. Changes apply on the next start.')
  } catch (err) { error.value = (err as Error).message }
  finally { busy.value = false }
}
function decide(value: boolean) { leaveDialog.value = false; leave?.(value) }
async function deleteServer() {
  deleting.value = true; deletionError.value = ''
  try {
    await api(`/servers/${id}`, 'DELETE', { confirmation: deletionName.value, delete_files: deleteFiles.value })
    removed.value = true; deleteOpen.value = false
    store.servers = store.servers.filter(item => item.id !== id)
    delete store.operations[id]
    notices.show(deleteFiles.value ? 'Server and its instance files deleted.' : 'Server removed. Its files remain on disk.')
    await router.replace('/servers')
    await store.refresh()
  } catch (err) { deletionError.value = (err as Error).message }
  finally { deleting.value = false }
}
onMounted(load)
</script>
<template>
  <RouterLink to="/servers" class="m3e-button m3e-button--text back-link"><AppIcon name="back" />All servers</RouterLink><div class="page-heading"><div><span class="eyebrow">SERVER INSTANCE</span><h1>{{ server?.name || 'Server configuration' }}</h1><div v-if="server" class="instance-caption"><StateBadge :state="server.state" /><span>Port {{ server.port ?? '—' }}</span></div></div></div>
  <ServerTabs :server-id="id">
  <div v-if="loading" class="empty-state m3e-card" role="status"><m3e-loading-indicator aria-label="Loading configuration" /></div><div v-if="error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert">{{ error }}<UiButton v-if="!settings" variant="text" @click="load">Retry</UiButton></div>
  <template v-if="settings && !loading"><div v-if="locked" class="info-banner m3e-surface m3e-surface--container-high m3e-surface--shape-large">Stop this instance and wait for its operation to finish before editing configuration.</div><form class="settings-form" @submit.prevent="save"><fieldset :disabled="locked || busy"><section class="settings-section"><div><span class="eyebrow">IDENTITY</span><h2>Make it yours</h2><p class="muted">How your server appears to players.</p></div><div class="settings-fields"><UiField label="Server name" v-model="settings.Name" required maxlength="250" /><UiField label="Description" v-model="settings.Description" multiline maxlength="1000" /><UiField label="Tags" v-model="settings.Tags" maxlength="100" hint="Comma-separated BeamMP server tags." /></div></section><section class="settings-section"><div><span class="eyebrow">CONNECTION</span><h2>Open the road</h2><p class="muted">Network settings and player capacity.</p></div><div class="settings-fields"><div class="field-row"><UiField label="Port" type="number" v-model="settings.Port" required min="1024" max="65535" /><UiField label="Bind IP" v-model="settings.IP" required :hint="settings.IP.includes(':') ? 'Use :: for IPv4 + IPv6, or ::1 for local-only access.' : 'IPv4-only binds can break joining BeamMP 3.9.x. Use :: for all interfaces, ::1 for local-only, or ::ffff: followed by a specific IPv4 address.'" /></div><div class="field-row"><UiField label="Maximum players" type="number" v-model="settings.MaxPlayers" required min="1" max="100000" /><UiField label="Cars per player" type="number" v-model="settings.MaxCars" required min="1" max="100000" /></div><UiCheck kind="switch" label="Private server" hint="Hide this instance from the public server list." v-model="settings.Private" /><UiCheck kind="switch" label="Allow guests" hint="Let guest accounts join the server." v-model="settings.AllowGuests" /></div></section><section class="settings-section"><div><span class="eyebrow">AUTHENTICATION</span><h2>Keep your key safe</h2><p class="muted">Get an AuthKey from <a href="https://keymaster.beammp.com" target="_blank" rel="noopener noreferrer">BeamMP Keymaster</a>. Use a separate key for each running instance.</p></div><div class="settings-fields"><div class="key-status"><AppIcon name="check" v-if="settings.has_auth_key" /><span>{{ settings.has_auth_key ? 'An AuthKey is configured. Its value is hidden.' : 'No AuthKey is configured.' }}</span></div><UiCheck v-model="replaceKey" :label="settings.has_auth_key ? 'Replace or clear the AuthKey' : 'Set an AuthKey'"  /><UiField v-if="replaceKey" label="New AuthKey" type="password" v-model="authKey" autocomplete="off" hint="Leaving this empty clears the saved key. Otherwise the existing key is kept." /></div></section><section class="settings-section"><div><span class="eyebrow">DIAGNOSTICS</span><h2>A clearer picture</h2><p class="muted">Control what the server records and shares.</p></div><div class="settings-fields"><UiCheck kind="switch" label="Log chat" hint="Include player chat in the BeamMP server log." v-model="settings.LogChat" /><UiCheck kind="switch" label="Debug logging" hint="Verbose output for troubleshooting." v-model="settings.Debug" /><UiCheck kind="switch" label="Information packets" hint="Allow clients to request server information." v-model="settings.InformationPacket" /></div></section></fieldset><div class="save-bar"><span>{{ dirty ? 'You have unsaved changes.' : 'Changes apply the next time this server starts.' }}</span><UiButton type="submit" :busy="busy" :disabled="locked || !dirty"><AppIcon name="check" />Save configuration</UiButton></div></form></template>
  <section v-if="server && settings && !loading && useSession().user?.is_admin" class="danger-zone m3e-card m3e-card--outlined"><div><span class="eyebrow">DELETE SERVER</span><h2>Delete this server</h2><p class="muted">Remove this instance from the panel. You can also choose to permanently delete its files.</p></div><UiButton class="danger-button" :disabled="locked || busy" @click="deleteOpen = true; deletionError = ''; deletionName = ''; deleteFiles = false">Delete server</UiButton></section>
  </ServerTabs>
  <ConfirmDialog :open="deleteOpen" title="Delete this server?" :message="`This removes ${server?.name || 'this server'} from your workspace.`" confirm="Delete server" danger :busy="deleting" :disabled="deletionName !== server?.name" @close="deleteOpen = false" @confirm="deleteServer"><UiField label="Type the server name to confirm" v-model="deletionName" autocomplete="off" /><UiCheck v-model="deleteFiles" label="Also permanently delete the instance files" :disabled="deleting"  /><p class="field-hint deletion-path">{{ deleteFiles ? 'These files will be permanently deleted:' : 'These files will remain on disk:' }} <code>{{ server?.directory }}</code></p><p v-if="deletionError" class="inline-error" role="alert">{{ deletionError }}</p></ConfirmDialog>
  <ConfirmDialog :open="leaveDialog" title="Discard unsaved changes?" message="Your configuration changes have not been saved." confirm="Discard changes" @close="decide(false)" @confirm="decide(true)" />
</template>
