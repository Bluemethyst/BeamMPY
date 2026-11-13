<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { M3eSnackbarHost } from '@kyralabs/m3e-elements/snackbar-host.js'
import { useNotices } from '../stores'
const notices = useNotices(), host = ref<M3eSnackbarHost>()
const queued = new Set<number>()
let stop: (() => void) | undefined
onMounted(() => {
  stop = watch(() => notices.items.slice(), items => {
    for (const item of items) {
      if (queued.has(item.id) || !host.value) continue
      queued.add(item.id)
      void host.value.showSnackbar({ message: item.message, duration: item.error ? 'long' : 'short', withDismissAction: true }).then(() => { queued.delete(item.id); notices.dismiss(item.id) })
    }
  }, { immediate: true })
})
onUnmounted(() => stop?.())
</script>
<template><m3e-snackbar-host ref="host" dismiss-label="Dismiss notification" /></template>
