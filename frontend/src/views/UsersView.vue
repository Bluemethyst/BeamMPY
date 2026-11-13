<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { api } from '../api'
import { useNotices, useServers } from '../stores'
import type { Account, Permission } from '../types'
import UiButton from '../components/UiButton.vue'
import UiField from '../components/UiField.vue'
import UiCheck from '../components/UiCheck.vue'
import UiDialog from '../components/UiDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
const store = useServers(), notices = useNotices()
const users = ref<Account[]>([]), error = ref(''), formError = ref(''), busy = ref(false), loading = ref(true)
const editing = ref<Account>(), username = ref(''), password = ref(''), enabled = ref(true), createServers = ref(false)
const grants = ref<Record<string, Permission[]>>({}), resetOnly = ref(false), dialog = ref<InstanceType<typeof UiDialog>>()
const temporary = ref(true), deleting = ref(false), deleteError = ref(''), deleteTarget = ref<Account>()
const choices: { key: Permission; label: string }[] = [
  { key: 'power', label: 'Start, stop and restart' }, { key: 'maps', label: 'Change map' },
  { key: 'mods_toggle', label: 'Enable and disable mods' }, { key: 'mods_upload', label: 'Upload maps and mods' },
  { key: 'configure', label: 'Edit configuration' }, { key: 'console_view', label: 'View console' },
  { key: 'console_command', label: 'Send console commands (can stop the server)' },
]
async function load() {
  loading.value = true; error.value = ''
  try { await store.refresh(); users.value = (await api<{ users: Account[] }>('/users')).users }
  catch (err) { error.value = (err as Error).message }
  finally { loading.value = false }
}
async function open(user?: Account, reset = false) {
  editing.value = user; resetOnly.value = reset; username.value = user?.username || ''; password.value = ''; enabled.value = user?.enabled ?? true
  temporary.value = true
  createServers.value = user?.can_create_servers || false; grants.value = structuredClone(user ? JSON.parse(JSON.stringify(user.permissions)) : {})
  formError.value = ''; await nextTick(); dialog.value?.showModal()
}
function assign(id: string, value: boolean) { if (value) grants.value[id] = []; else delete grants.value[id] }
function permit(id: string, key: Permission, value: boolean) {
  grants.value[id] = value ? [...grants.value[id], key] : grants.value[id].filter(item => item !== key)
  if (key === 'console_command' && value && !grants.value[id].includes('console_view')) grants.value[id].push('console_view')
  if (key === 'console_view' && !value) grants.value[id] = grants.value[id].filter(item => item !== 'console_command')
}
async function save() {
  busy.value = true; formError.value = ''
  try {
    if (resetOnly.value && editing.value) await api(`/users/${editing.value.id}/password`, 'POST', { password: password.value, temporary: temporary.value })
    else await api(editing.value ? `/users/${editing.value.id}` : '/users', editing.value ? 'PUT' : 'POST', {
      username: username.value, enabled: enabled.value, can_create_servers: createServers.value, permissions: grants.value,
      ...(!editing.value ? { password: password.value, temporary: temporary.value } : {}),
    })
    password.value = ''; dialog.value?.close(); await load()
    notices.show(resetOnly.value ? `${temporary.value ? 'Temporary password' : 'Password'} set. Existing sessions were signed out.` : 'Account saved. The member must sign in again after access changes.')
  } catch (err) { formError.value = (err as Error).message }
  finally { busy.value = false }
}
async function remove() {
  if (!deleteTarget.value) return
  deleting.value = true; deleteError.value = ''
  try {
    await api(`/users/${deleteTarget.value.id}`, 'DELETE', { confirmation: deleteTarget.value.username })
    deleteTarget.value = undefined; await load()
    notices.show('User deleted and sessions signed out. Servers and files were kept.')
  } catch (err) { deleteError.value = (err as Error).message }
  finally { deleting.value = false }
}
onMounted(load)
</script>
<template>
  <div class="page-heading"><div><h1>Users</h1><p class="muted">Assign access to individual servers. Only the administrator manages accounts.</p></div><UiButton @click="open()">Create user</UiButton></div>
  <div v-if="error" class="error-banner m3e-surface m3e-surface--shape-large" role="alert">{{ error }}<UiButton variant="text" @click="load">Retry</UiButton></div>
  <div v-if="loading" role="status"><m3e-loading-indicator aria-label="Loading users" /></div>
  <div v-else class="user-list"><article v-for="user in users" :key="user.id" class="m3e-card user-card" :aria-label="user.username"><div class="user-card-content"><div class="user-details"><h2>{{ user.username }}</h2><p class="muted">{{ user.is_admin ? 'Administrator · full access' : `${user.enabled ? 'Enabled' : 'Disabled'} · ${Object.keys(user.permissions).length} assigned servers${user.must_change_password ? ' · password change required' : ''}` }}</p></div><div v-if="!user.is_admin" class="user-actions"><UiButton variant="outlined" :aria-label="`Edit ${user.username}`" @click="open(user)">Edit access</UiButton><UiButton variant="text" :aria-label="`Reset password for ${user.username}`" @click="open(user, true)">Reset password</UiButton><UiButton class="danger-button" :aria-label="`Delete ${user.username}`" @click="deleteTarget = user; deleteError = ''">Delete user</UiButton></div></div></article></div>
  <UiDialog ref="dialog" :title="resetOnly ? `Reset password for ${editing?.username}` : editing ? `Edit ${editing.username}` : 'Create user'" :busy="busy">
    <form @submit.prevent="save"><UiField v-if="!resetOnly" label="Username" v-model="username" autocomplete="off" required maxlength="80" :disabled="busy" /><template v-if="!editing || resetOnly"><UiField label="Password" v-model="password" type="password" autocomplete="new-password" required minlength="8" maxlength="1024" hint="Use at least 8 characters." :disabled="busy" /><UiCheck label="Temporary password" v-model="temporary" :disabled="busy" /><p class="muted">{{ temporary ? 'The member must change this password at their next sign-in.' : 'The member can sign in with this password without a required change.' }}</p></template>
      <template v-if="!resetOnly"><UiCheck label="Account enabled" v-model="enabled" :disabled="busy" /><UiCheck label="Allow creating servers" v-model="createServers" hint="New servers are assigned to their creator with all member permissions." :disabled="busy" />
        <h2>Server access</h2><p class="muted">Assigned servers are visible. Check the actions this member may perform.</p>
        <section v-for="server in store.servers" :key="server.id" class="permission-group m3e-card m3e-card--outlined"><UiCheck :label="`Access ${server.name}`" :model-value="server.id in grants" :disabled="busy" @update:model-value="assign(server.id, $event)" /><div v-if="server.id in grants"><UiCheck v-for="choice in choices" :key="choice.key" :label="choice.label" :model-value="grants[server.id].includes(choice.key)" :disabled="busy" @update:model-value="permit(server.id, choice.key, $event)" /></div></section><p v-if="!store.servers.length" class="muted">Create a server to assign access here.</p>
      </template><p v-if="formError" class="inline-error" role="alert">{{ formError }}</p><div class="modal-actions"><UiButton variant="text" :disabled="busy" @click="password = ''; dialog?.close()">Cancel</UiButton><UiButton type="submit" :busy="busy">{{ resetOnly ? 'Set password' : 'Save user' }}</UiButton></div>
    </form>
  </UiDialog>
  <ConfirmDialog :open="!!deleteTarget" title="Delete this user?" :message="`Permanently delete ${deleteTarget?.username || 'this user'} and sign out their sessions? Their servers and files will be kept. This cannot be undone.`" confirm="Delete user" danger :busy="deleting" @close="deleteTarget = undefined" @confirm="remove"><p v-if="deleteError" class="inline-error" role="alert">{{ deleteError }}</p></ConfirmDialog>
</template>
