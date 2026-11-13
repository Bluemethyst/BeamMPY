<script setup lang="ts">
import { computed, ref } from 'vue'
import { useNotices, useServers, useSession } from '../stores'
import type { Server } from '../types'
import AppIcon from './AppIcon.vue'
import UiButton from './UiButton.vue'
import ConfirmDialog from './ConfirmDialog.vue'
const props = defineProps<{ server: Server }>()
const store = useServers(), session = useSession()
const sending = ref(false)
const confirm = ref('')
const busy = computed(() => sending.value || !!store.operations[props.server.id] || ['starting', 'stopping', 'installing'].includes(props.server.state))
async function perform(action: string) {
  confirm.value = ''; sending.value = true
  try { await store.operate(props.server.id, action) }
  catch (err) { useNotices().show((err as Error).message, true) }
  finally { sending.value = false }
}
</script>
<template>
  <div v-if="session.can('power', server.id)" class="power-controls">
    <UiButton v-if="!server.executable_exists && session.user?.is_admin" variant="tonal" :busy="busy" @click="perform('install')"><AppIcon name="import" />Retry installation</UiButton>
    <UiButton v-else-if="server.executable_exists" :variant="server.running ? 'tonal' : 'filled'" :busy="busy" @click="server.running ? confirm = 'stop' : perform('start')"><AppIcon name="power" />{{ server.running ? 'Stop' : 'Start' }}</UiButton>
    <UiButton v-if="server.executable_exists" variant="outlined" :disabled="!server.running || busy" @click="confirm = 'restart'"><AppIcon name="refresh" />Restart</UiButton>
  </div>
  <ConfirmDialog :open="!!confirm" :title="confirm === 'stop' ? 'Stop this server?' : 'Restart this server?'" :message="`Players connected to ${server.name} will be disconnected.`" :confirm="confirm === 'stop' ? 'Stop server' : 'Restart server'" @close="confirm = ''" @confirm="perform(confirm)" />
</template>
