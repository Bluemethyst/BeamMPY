<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'filled' | 'tonal' | 'text' | 'outlined'; busy?: boolean; disabled?: boolean; type?: 'button' | 'submit'; size?: 's' | 'm' }>(),
  { variant: 'filled', type: 'button' })
</script>
<template>
  <button :type="type" :class="['m3e-button', size === 'm' ? 'm3e-button--size-m' : '', 'm3e-button--' + variant]" :disabled="busy || disabled" :aria-busy="busy || undefined">
    <m3e-loading-indicator v-if="busy" class="button-loading" aria-hidden="true" /><slot />
  </button>
</template>
