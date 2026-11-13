<script setup lang="ts">
defineProps<{ tone?: 'neutral' | 'positive' | 'error' }>()
</script>
<template><span class="m3e-badge m3e-badge--large info-badge" :class="tone"><slot /></span></template>
