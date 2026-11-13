<script setup lang="ts">
defineProps<{ label: string; modelValue: string; value: string; name: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<template><label class="m3e-radio-button"><input class="m3e-radio-button__input" type="radio" :name="name" :value="value" :checked="modelValue === value" :disabled="disabled" @change="emit('update:modelValue', value)" /><span class="m3e-radio-button__icon"></span><span class="m3e-radio-button__state"></span><span class="m3e-radio-button__label">{{ label }}</span></label></template>
