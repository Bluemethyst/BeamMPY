<script setup lang="ts">
import { ref } from 'vue'
const props = defineProps<{ title: string; busy?: boolean }>()
const open = ref(false)
function change(event: CustomEvent<{ open: boolean }>) {
  if (!event.detail.open && props.busy) event.preventDefault()
  else open.value = event.detail.open
}
defineExpose({ showModal: () => { open.value = true }, close: () => { open.value = false } })
</script>
<template><m3e-dialog variant="full-screen" :headline="title" :open.prop="open" @open-change="change($event)"><div class="dialog-form-content"><slot /></div></m3e-dialog></template>
