<script setup lang="ts">
import UiCheck from '../components/UiCheck.vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from '../stores'
import UiButton from '../components/UiButton.vue'
import UiField from '../components/UiField.vue'
import AppIcon from '../components/AppIcon.vue'
const route = useRoute(), router = useRouter(), session = useSession()
const setup = computed(() => route.path === '/setup')
const username = ref(''), password = ref(''), confirmation = ref(''), error = ref(''), busy = ref(false), reveal = ref(false)
async function submit() {
  error.value = ''
  if (setup.value && password.value !== confirmation.value) { error.value = 'Passwords do not match.'; return }
  busy.value = true
  try { await session.authenticate(setup.value ? 'setup' : 'login', username.value, password.value); await router.replace('/servers') }
  catch (err) { error.value = (err as Error).message }
  finally { busy.value = false; password.value = ''; confirmation.value = '' }
}
</script>
<template>
  <div class="auth-intro"><span class="brand-mark large"><AppIcon name="servers" /></span><span class="eyebrow">BEAMMPY / SERVER CONTROLLER</span><h1>Your servers.<br />Your open road.</h1><p>A clear view of every instance.<br />Everything you need to keep things running.</p><div class="auth-detail"><span class="status-dot online"></span>Self-hosted. Built for BeamMP.</div></div>
  <section class="auth-card m3e-card"><span class="eyebrow">{{ setup ? 'WELCOME ABOARD' : 'WELCOME BACK' }}</span><h2>{{ setup ? 'Set up your workspace' : 'Sign in to BeamMPY' }}</h2><p class="muted">{{ setup ? 'Create the administrator account for this panel.' : 'Manage your servers from one place.' }}</p><form @submit.prevent="submit">
    <UiField label="Username" v-model="username" autocomplete="username" required maxlength="80" autofocus />
    <UiField label="Password" v-model="password" :type="reveal ? 'text' : 'password'" :autocomplete="setup ? 'new-password' : 'current-password'" required :minlength="setup ? 12 : 1" maxlength="1024" :hint="setup ? 'Use at least 12 characters.' : undefined" />
    <UiField v-if="setup" label="Confirm password" v-model="confirmation" :type="reveal ? 'text' : 'password'" autocomplete="new-password" required minlength="12" />
    <UiCheck v-model="reveal" label="Show password"  />
    <p v-if="error" class="inline-error" role="alert">{{ error }}</p><UiButton type="submit" :busy="busy" class="full-width">{{ setup ? 'Create administrator' : 'Sign in' }}<AppIcon name="arrow" /></UiButton>
  </form><p class="auth-footnote">{{ setup ? 'Registration closes after setup is complete.' : 'Forgot your password? Reset it using the local panel CLI.' }}</p></section>
</template>
