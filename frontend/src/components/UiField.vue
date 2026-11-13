<script setup lang="ts">
import { computed, nextTick, onMounted, onUpdated, ref, useAttrs } from 'vue'
import type { M3eTextField } from '@kyralabs/m3e-elements/text-field.js'
defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{ label: string; hint?: string; modelValue?: string | number; type?: string; multiline?: boolean }>(), { type: 'text' })
const emit = defineEmits<{ 'update:modelValue': [value: string | number] }>()
const field = ref<M3eTextField>()
const attrs = useAttrs()
function fieldAttrs() {
  const forwarded: Record<string, unknown> = { ...attrs, class: undefined }
  for (const name of ['required', 'disabled', 'readonly']) {
    if (name in forwarded) forwarded[name] = attrs[name] === '' || !!attrs[name]
  }
  if ('maxlength' in attrs) forwarded.maxlength = Number(attrs.maxlength)
  return forwarded
}
const value = computed(() => String(props.modelValue ?? ''))
let focused = false
async function constraints() {
  await nextTick()
  const input = field.value?.input
  if (!input) return
  // M3E supplies aria-required; retain the browser's form-validation contract too.
  input.required = attrs.required === '' || !!attrs.required
  for (const name of ['min', 'max', 'minlength', 'rows', 'spellcheck', 'autofocus']) {
    const value = attrs[name]
    if (value === undefined || value === false || value === null) input.removeAttribute(name)
    else input.setAttribute(name, String(value))
  }
  if ('autofocus' in attrs && !focused) { input.focus({ preventScroll: true }); focused = true }
}
onMounted(constraints)
onUpdated(constraints)
function input(event: Event, type: string) {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', type === 'number' && value !== '' ? Number(value) : value)
}
</script>
<template>
  <div class="field" :class="$attrs.class"><m3e-text-field ref="field" variant="filled" v-bind="fieldAttrs()" :label="label" :value.prop="value" :type="type" :multiline="multiline" :supporting-text="hint || ''" @input="input($event, type)" /></div>
</template>
