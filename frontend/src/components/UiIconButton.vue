<script setup lang="ts">
import { ref } from 'vue'
withDefaults(defineProps<{ label: string; disabled?: boolean; variant?: 'standard' | 'tonal' | 'filled' }>(), { variant: 'standard' })
const button = ref<HTMLButtonElement>()
defineExpose({ focus: () => button.value?.focus() })
</script>
<template><button ref="button" type="button" :aria-label="label" :disabled="disabled" :class="['m3e-icon-button', variant === 'standard' ? '' : 'm3e-icon-button--' + variant]"><slot /></button></template>
