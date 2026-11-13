<script setup lang="ts">
import UiField from '../components/UiField.vue'
import UiProgress from '../components/UiProgress.vue'
import UiCheck from '../components/UiCheck.vue'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { io } from 'socket.io-client'
import { useNotices, useServers, useSession } from '../stores'
import type { ConsoleLine, Server } from '../types'
import AppIcon from '../components/AppIcon.vue'
import ServerTabs from '../components/ServerTabs.vue'
import UiButton from '../components/UiButton.vue'
import StateBadge from '../components/StateBadge.vue'
import PowerControls from '../components/PowerControls.vue'
const route = useRoute(), router = useRouter(), store = useServers(), session = useSession(), notices = useNotices()
const id = String(route.params.id)
const server = computed(() => store.servers.find(item => item.id === id))
const lines = ref<ConsoleLine[]>([]), command = ref(''), connected = ref(false), subscribed = ref(false), sending = ref(false)
const follow = ref(true), terminal = ref<HTMLElement>(), connectionError = ref('')
const socket = io({ autoConnect: false, transports: ['polling'], auth: { csrf_token: session.csrf } })
async function scroll() { await nextTick(); if (follow.value && terminal.value) terminal.value.scrollTop = terminal.value.scrollHeight }
socket.on('connect', () => {
  connected.value = true; connectionError.value = ''
  socket.emit('subscribe', { server_id: id }, (reply: { ok: boolean; error?: string }) => { subscribed.value = reply.ok; if (!reply.ok) connectionError.value = reply.error || 'Subscription failed.' })
})
socket.on('connect_error', () => { connected.value = false; subscribed.value = false; connectionError.value = 'Console disconnected. Reconnecting…' })
socket.on('disconnect', async reason => {
  connected.value = false; subscribed.value = false
  if (reason === 'io server disconnect') {
    await session.load()
    if (!session.user) await router.replace('/login')
    else { socket.auth = { csrf_token: session.csrf }; socket.connect() }
  }
})
socket.on('terminal_history', (data: { server_id: string; lines: ConsoleLine[] }) => { if (data.server_id === id) { lines.value = data.lines.slice(-1000); void scroll() } })
socket.on('terminal_output', (data: ConsoleLine & { server_id: string }) => {
  if (data.server_id === id && !lines.value.some(line => line.sequence === data.sequence)) {
    lines.value.push(data); if (lines.value.length > 1000) lines.value.shift(); void scroll()
  }
})
socket.on('server_status', (data: Server & { server_id: string }) => { if (data.server_id === id) store.update(data) })
socket.on('server_removed', (data: { server_id: string }) => { if (data.server_id === id) { notices.show('This server was removed from the panel.'); void router.replace('/servers') } })
async function send() {
  if (!command.value.trim()) return
  sending.value = true
  socket.timeout(5000).emit('command', { server_id: id, text: command.value }, (error: Error | null, reply: { ok: boolean; error?: string }) => {
    sending.value = false
    if (error || !reply?.ok) notices.show(reply?.error || 'Command delivery was not confirmed. Check the console before retrying.', true)
    else command.value = ''
  })
}
onMounted(async () => { await store.refresh(); socket.connect() })
onUnmounted(() => { socket.removeAllListeners(); socket.disconnect() })
</script>
<template>
  <RouterLink to="/servers" class="m3e-button m3e-button--text back-link"><AppIcon name="back" />All servers</RouterLink>
  <div v-if="!server" class="empty-state m3e-card"><h1>{{ store.loading ? 'Loading server…' : 'Server unavailable' }}</h1><p>{{ store.error || 'Return to the overview to select an instance.' }}</p></div>
  <template v-else><div class="page-heading server-heading"><div><span class="eyebrow">SERVER INSTANCE</span><h1>{{ server.name }}</h1><div class="instance-caption"><StateBadge :state="server.state" /><span>Port {{ server.port ?? '—' }}</span><span>{{ server.version || 'Imported installation' }}</span></div></div><PowerControls :server="server" /></div>
  <ServerTabs :server-id="id">
  <div v-if="server.error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert">{{ server.error }}</div><div v-if="store.operations[id]" class="operation-status" role="status"><UiProgress :value="store.operations[id].progress" /><span>{{ store.operations[id].message }}</span></div>
  <section class="console-panel" aria-label="Server console"><header class="console-toolbar"><span><AppIcon name="terminal" />Live console</span><div><span class="console-connection"><span class="status-dot" :class="{ online: connected && subscribed }"></span>{{ connected && subscribed ? 'Connected' : 'Disconnected' }}</span><UiButton variant="text" @click="lines = []">Clear view</UiButton></div></header><div class="terminal" ref="terminal" tabindex="0" aria-label="Console output"><div v-if="!lines.length" class="terminal-empty"><AppIcon name="terminal" /><p>{{ server.running ? 'Waiting for server output…' : 'The road is quiet.' }}</p><span>{{ server.running ? 'New output will appear here.' : 'Start this instance to see its live console.' }}</span></div><div v-for="line in lines" :key="line.sequence" class="terminal-line"><time>{{ new Date(line.time * 1000).toLocaleTimeString([], { hour12: false }) }}</time><span>{{ line.text }}</span></div></div><form class="command-bar" @submit.prevent="send"><UiField class="command-field" label="Console command" v-model="command" placeholder="Enter a BeamMP command…" autocomplete="off" spellcheck="false" maxlength="4096" :disabled="!server.running || !subscribed || !!store.operations[id]" /><UiButton type="submit" variant="tonal" :busy="sending" :disabled="!server.running || !subscribed || !!store.operations[id] || !command.trim()">Send<AppIcon name="arrow" /></UiButton></form></section>
  <div class="console-footnote"><UiCheck v-model="follow" label="Follow output" @change="scroll"  /><span>{{ lines.length }} / 1,000 lines · {{ connectionError || 'Commands run in the BeamMP server console.' }}</span></div><p class="directory-note"><strong>Instance directory</strong><code>{{ server.directory }}</code></p></ServerTabs></template>
</template>
