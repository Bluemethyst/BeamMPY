<script setup lang="ts">
withDefaults(defineProps<{ label: string; modelValue: boolean; disabled?: boolean; kind?: 'checkbox' | 'switch'; hint?: string }>(), { kind: 'checkbox' })
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; change: [] }>()
function change(event: Event) { emit('update:modelValue', (event.target as HTMLInputElement).checked); emit('change') }
</script>
<template>
  <m3e-checkbox v-if="kind === 'checkbox'" :label="label" :checked.prop="modelValue" :disabled="disabled" @change="change">{{ label }}</m3e-checkbox>
  <div v-else class="setting-toggle"><div><strong>{{ label }}</strong><p v-if="hint" class="muted">{{ hint }}</p></div><label class="m3e-switch"><input class="m3e-switch__input" type="checkbox" role="switch" :aria-label="label" :checked="modelValue" :disabled="disabled" @change="change" /><span class="m3e-switch__track"><span class="m3e-switch__handle"><span class="m3e-switch__state"></span><span class="m3e-switch__icon m3e-switch__icon--checked m3e-icon" aria-hidden="true">check</span></span></span></label></div>
</template>
