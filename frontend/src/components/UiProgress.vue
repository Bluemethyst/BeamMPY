<script setup lang="ts">
defineProps<{ value?: number; label?: string }>()
</script>
<template><m3e-linear-progress shape="wavy" :value="value === undefined ? undefined : value / 100" :aria-label="label || 'Operation progress'" /></template>
