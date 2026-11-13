<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useNotices, useSession } from '../stores'
import type { Session } from '../types'
import UiButton from '../components/UiButton.vue'
import UiField from '../components/UiField.vue'
import UiCheck from '../components/UiCheck.vue'
const session = useSession(), notices = useNotices(), router = useRouter()
const current = ref(''), password = ref(''), confirmation = ref(''), reveal = ref(false), busy = ref(false), error = ref('')
async function change() {
  error.value = ''
  if (password.value !== confirmation.value) { error.value = 'Passwords do not match.'; return }
  busy.value = true
  try {
    session.apply(await api<Session>('/auth/password', 'POST', { current_password: current.value, new_password: password.value }))
    notices.show('Password changed. Sign in again; all previous sessions have been signed out.')
    await router.replace('/login')
  } catch (err) { error.value = (err as Error).message }
  finally { busy.value = false; current.value = ''; password.value = ''; confirmation.value = '' }
}
async function logoutAll() {
  busy.value = true; error.value = ''
  try { session.apply(await api<Session>('/auth/logout-all', 'POST', {})); await router.replace('/login') }
  catch (err) { error.value = (err as Error).message }
  finally { busy.value = false }
}
</script>
<template>
  <div class="page-heading"><div><h1>My account</h1><p class="muted">{{ session.user?.username }} · {{ session.user?.is_admin ? 'Administrator' : 'Member' }}</p></div></div>
  <p v-if="session.user?.must_change_password" class="info-banner m3e-surface m3e-surface--container-high m3e-surface--shape-large">Choose your own password before managing servers. Use your temporary password as the current password.</p>
  <section class="m3e-card account-card"><h2>Change password</h2><p class="muted">Changing your password signs out every session, including this browser.</p>
    <form @submit.prevent="change"><UiField label="Current password" v-model="current" :type="reveal ? 'text' : 'password'" autocomplete="current-password" required maxlength="1024" :disabled="busy" /><UiField label="New password" v-model="password" :type="reveal ? 'text' : 'password'" autocomplete="new-password" required minlength="8" maxlength="1024" hint="Use at least 8 characters." :disabled="busy" /><UiField label="Confirm new password" v-model="confirmation" :type="reveal ? 'text' : 'password'" autocomplete="new-password" required minlength="8" maxlength="1024" :disabled="busy" /><UiCheck v-model="reveal" label="Show passwords" :disabled="busy" /><p v-if="error" class="inline-error" role="alert">{{ error }}</p><UiButton type="submit" :busy="busy">Change password</UiButton></form>
  </section>
  <section class="m3e-card account-card"><h2>Sessions</h2><p class="muted">Sign out this browser and any other devices using your account.</p><UiButton variant="outlined" :disabled="busy" @click="logoutAll">Sign out all devices</UiButton></section>
</template>
