<script setup lang="ts">
defineProps<{ name: string }>()
const icons: Record<string, string> = {
  servers: 'dns', terminal: 'terminal', settings: 'tune', plus: 'add', map: 'map', mods: 'extension',
  arrow: 'arrow_forward', power: 'power_settings_new', refresh: 'restart_alt', import: 'upload_file',
  back: 'arrow_back', logout: 'logout', check: 'check', close: 'close', menu: 'menu', expand: 'expand_more',
}
</script>
<template><m3e-icon :name="icons[name] || name" aria-hidden="true" /></template>
