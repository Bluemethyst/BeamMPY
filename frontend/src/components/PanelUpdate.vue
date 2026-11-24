<script setup lang="ts">
import { onMounted, onUnmounted, ref, useId } from 'vue'
import { api } from '../api'
import AppIcon from './AppIcon.vue'
import UiButton from './UiButton.vue'
import UiIconButton from './UiIconButton.vue'

interface UpdateInfo {
  installed_version: string; available_version: string | null; update_available: boolean
  status: string; host_os: 'windows' | 'linux' | 'unsupported'; command: string | null
}
const id = useId(), info = ref<UpdateInfo>(), open = ref(false), copyStatus = ref('')
const commandText = ref<HTMLElement>()
let active = true, timer: ReturnType<typeof setTimeout> | undefined
async function refresh() {
  try {
    if (!document.hidden && !open.value) {
      const result = await api<UpdateInfo>('/panel/update')
      if (!active) return
      info.value = result
    }
  } catch { if (active) info.value = undefined }
  if (active) timer = setTimeout(() => { void refresh() }, info.value?.status === 'checking' ? 1000 : 5 * 60 * 1000)
}
function show() { copyStatus.value = ''; open.value = true }
async function copy() {
  if (!info.value?.command) return
  try {
    // Clipboard API requires HTTPS/loopback. LAN HTTP uses the browser's native
    // copy command with a temporary selection, keeping the visible text usable.
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(info.value.command)
    else {
      const selection = window.getSelection(), range = document.createRange()
      range.selectNodeContents(commandText.value!)
      selection?.removeAllRanges(); selection?.addRange(range)
      const copied = document.execCommand('copy')
      selection?.removeAllRanges()
      if (!copied) throw new Error('Copy unavailable')
    }
    copyStatus.value = 'Update command copied.'
  } catch { copyStatus.value = 'Select the command and copy it manually.' }
}
onMounted(() => { void refresh() })
onUnmounted(() => { active = false; if (timer) clearTimeout(timer) })
</script>
<template>
  <template v-if="info?.update_available">
    <UiIconButton :id="id" label="Update available" aria-haspopup="dialog" :aria-expanded="open" @click="show"><AppIcon name="system_update_alt" /></UiIconButton>
    <m3e-tooltip :anchor="id">Update available</m3e-tooltip>
    <Teleport to="body">
      <m3e-dialog headline="BeamMPY update available" :open.prop="open" @open-change="open = $event.detail.open">
        <div class="panel-update-content">
          <p>A newer version of the BeamMPY panel is available.</p>
          <dl class="panel-update-versions"><div><dt>Installed version</dt><dd>v{{ info.installed_version }}</dd></div><div><dt>Available version</dt><dd>v{{ info.available_version }}</dd></div></dl>
          <p>Stop BeamMPY and its servers, then back up the complete data directory and any imported server folders.</p>
          <template v-if="info.command">
            <p>Run this command in {{ info.host_os === 'windows' ? 'PowerShell on the Windows panel host' : 'a terminal on the Ubuntu panel host' }}. Choose the <strong>same installation folder</strong> to keep your accounts, data and settings.</p>
            <pre class="panel-update-command" tabindex="0" aria-label="Manual update command"><code ref="commandText">{{ info.command }}</code></pre>
            <p>{{ info.host_os === 'windows' ? 'After the installer finishes, open Start BeamMPY.bat again.' : 'The installer restarts the unprivileged systemd service afterward.' }} No Node.js is needed.</p>
          </template>
          <p v-else>Use the manual installation guide for this host; the one-line installers support Windows and Ubuntu.</p>
          <p class="muted">These are manual instructions. Nothing is installed or restarted from this dialog. For an explicit wheel installation, follow the <a href="https://github.com/Bluemethyst/BeamMPY/blob/main/docs/INSTALLATION.md#explicit-wheels--existing-manual-installations" target="_blank" rel="noopener noreferrer">installation guide</a>.</p>
          <p class="muted" role="status">{{ copyStatus }}</p>
        </div>
        <div slot="actions" class="panel-update-actions"><UiButton v-if="info.command" variant="tonal" @click="copy"><AppIcon name="content_copy" />Copy command</UiButton><UiButton variant="text" @click="open = false">Close</UiButton></div>
      </m3e-dialog>
    </Teleport>
  </template>
</template>
