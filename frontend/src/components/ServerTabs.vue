<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const props = defineProps<{ serverId: string }>()
const route = useRoute(), router = useRouter()
const selected = computed(() => String(route.path.split('/').at(-1)))
const tabs = [{ path: 'console', label: 'Console', icon: 'terminal' }, { path: 'settings', label: 'Configuration', icon: 'tune' }, { path: 'maps', label: 'Maps', icon: 'map' }, { path: 'mods', label: 'Mods', icon: 'extension' }]
function select(event: CustomEvent<{ value: string }>) {
  event.preventDefault()
  void router.push(`/servers/${props.serverId}/${event.detail.value}`)
}
</script>
<template><div class="server-tabs"><m3e-tabs label="Server navigation" variant="secondary" icon-position="leading" :scrollable.prop="true" :selected.prop="selected" @selection-change="select($event)"><m3e-tab v-for="tab in tabs" :key="tab.path" :value="tab.path" :icon="tab.icon">{{ tab.label }}</m3e-tab><m3e-tab-panel :value="selected"><slot /></m3e-tab-panel></m3e-tabs></div></template>
