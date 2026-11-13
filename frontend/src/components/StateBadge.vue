<script setup lang="ts">
import type { ServerState } from '../types'
import UiBadge from './UiBadge.vue'
defineProps<{ state: ServerState }>()
</script>
<template><UiBadge class="state-badge" :tone="state === 'error' ? 'error' : state === 'running' ? 'positive' : 'neutral'">{{ state }}</UiBadge></template>
