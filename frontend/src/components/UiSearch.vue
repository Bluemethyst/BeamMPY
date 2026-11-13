<script setup lang="ts">
import UiField from './UiField.vue'
defineProps<{ label: string; modelValue: string; placeholder?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<template><UiField class="search-field" :label="label" :model-value="modelValue" :placeholder="placeholder" type="search" leading-icon="search" @update:model-value="emit('update:modelValue', String($event))" /></template>
