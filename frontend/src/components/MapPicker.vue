<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import type { MapChoice } from '../types'
import UiSelect from './UiSelect.vue'
const props = defineProps<{ serverId: string; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const maps = ref<MapChoice[]>([]), error = ref(''), loading = ref(true)
const options = computed(() => {
  const items = maps.value.map(map => ({ value: map.path, label: map.name + (map.enabled ? '' : ' — mod unavailable or disabled'), disabled: !map.enabled, group: map.kind === 'stock' ? 'Stock maps' : 'Custom maps' }))
  if (!items.some(item => item.value === props.modelValue)) items.unshift({ value: props.modelValue, label: props.modelValue, disabled: false, group: 'Current map' })
  return items
})
onMounted(async () => {
  try { maps.value = (await api<{ maps: MapChoice[] }>(`/servers/${props.serverId}/maps`)).maps }
  catch (err) { error.value = (err as Error).message }
  finally { loading.value = false }
})
</script>
<template><div class="field"><UiSelect label="Map" :options="options" :model-value="modelValue" :disabled="loading" hint="Stock maps and maps found in your mods. Changes apply on the next start." @update:model-value="emit('update:modelValue', $event)" /><span v-if="error" class="inline-error" role="alert">{{ error }}</span></div></template>
