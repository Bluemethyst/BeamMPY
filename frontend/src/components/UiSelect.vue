<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import AppIcon from './AppIcon.vue'
export interface SelectOption { value: string; label: string; disabled?: boolean; group?: string }
const props = defineProps<{ label: string; modelValue: string; options: SelectOption[]; disabled?: boolean; compact?: boolean; hint?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const id = useId(), button = ref<HTMLButtonElement>()
const selected = computed(() => props.options.find(option => option.value === props.modelValue)?.label || props.modelValue || 'Choose an option')
const groups = computed(() => [...new Set(props.options.map(option => option.group || ''))])
function select(event: CustomEvent<{ value: string }>) {
  if (!button.value?.matches(':disabled')) emit('update:modelValue', event.detail.value)
}
</script>
<template><div :class="['select-field', { compact }]">
  <label :for="id" :class="{ 'sr-only': compact }" class="field-label">{{ label }}</label>
  <button ref="button" :id="id" type="button" :class="compact ? 'm3e-icon-button m3e-icon-button--tonal' : 'm3e-button m3e-button--tonal select-trigger'" :disabled="disabled" :aria-label="label" :title="compact ? selected : undefined"><AppIcon v-if="compact" :name="modelValue === 'dark' ? 'dark_mode' : modelValue === 'light' ? 'light_mode' : 'contrast'" /><template v-else><span>{{ selected }}</span><AppIcon name="expand" /></template></button>
  <m3e-menu :anchor="id" :label="`${label} options`" variant="vibrant" @action="select($event)"><m3e-menu-group v-for="group in groups" :key="group" :label="group || undefined"><m3e-menu-item v-for="option in options.filter(item => (item.group || '') === group)" :key="option.value" :value="option.value" type="radio" :checked.prop="option.value === modelValue" :disabled="option.disabled">{{ option.label }}</m3e-menu-item></m3e-menu-group></m3e-menu>
  <span v-if="hint" class="field-hint">{{ hint }}</span>
</div></template>
