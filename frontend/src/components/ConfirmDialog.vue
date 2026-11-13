<script setup lang="ts">
import UiButton from './UiButton.vue'
const props = defineProps<{ open: boolean; title: string; message: string; confirm?: string; danger?: boolean; busy?: boolean; disabled?: boolean }>()
const emit = defineEmits<{ close: []; confirm: [] }>()
function change(event: CustomEvent<{ open: boolean }>) {
  if (!event.detail.open) {
    if (props.busy) event.preventDefault()
    else emit('close')
  }
}
</script>
<template>
  <m3e-dialog :headline="title" :open.prop="open" @open-change="change($event)">
    <div><p>{{ message }}</p><div v-if="$slots.default" class="confirmation-fields"><slot /></div></div>
    <div slot="actions" class="dialog-actions"><UiButton variant="text" :disabled="busy" @click="emit('close')">Cancel</UiButton><UiButton :class="{ 'danger-button': danger }" :busy="busy" :disabled="disabled" @click="emit('confirm')">{{ confirm || 'Confirm' }}</UiButton></div>
  </m3e-dialog>
</template>
