<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { colourPresets, normaliseColour, paletteStyles, themeModes, useAppearance } from '../appearance'
import AppIcon from './AppIcon.vue'
import UiButton from './UiButton.vue'
import UiField from './UiField.vue'
import UiDialog from './UiDialog.vue'

const appearance = useAppearance(), id = useId()
const dialog = ref<InstanceType<typeof UiDialog>>(), picker = ref<HTMLInputElement>()
const customColour = ref(''), error = ref('')
const customSelected = computed(() => !colourPresets.some(item => item.seed === appearance.seed))
function action(event: CustomEvent<{ value: string }>) {
  const value = event.detail.value
  if (value.startsWith('mode:')) appearance.setMode(value.slice(5))
  else if (value.startsWith('seed:')) appearance.setSeed(value.slice(5))
  else if (value.startsWith('style:')) appearance.setStyle(value.slice(6))
  else if (value === 'reset') appearance.reset()
  else if (value === 'custom') { customColour.value = appearance.seed; error.value = ''; dialog.value?.showModal() }
}
function applyCustom() {
  const colour = normaliseColour(customColour.value)
  if (!colour) { error.value = 'Enter a hex colour such as #3776AB or #38B.'; return }
  appearance.setSeed(colour)
  dialog.value?.close()
}
</script>
<template>
  <button :id="id" type="button" class="m3e-icon-button m3e-icon-button--tonal" aria-label="Appearance" title="Appearance"><AppIcon name="palette" /></button>
  <m3e-menu :anchor="id" label="Appearance options" variant="vibrant" @action="action($event)">
    <m3e-menu-group label="Appearance">
      <m3e-menu-item v-for="item in themeModes" :key="item.value" type="radio" :value="`mode:${item.value}`" :icon="item.icon" :checked.prop="appearance.mode === item.value">{{ item.label }}</m3e-menu-item>
    </m3e-menu-group>
    <m3e-menu-group label="Personalise">
      <m3e-menu-item :submenu="`${id}-colours`" icon="palette" :trailing-text="appearance.colourName">Colour scheme</m3e-menu-item>
      <m3e-menu-item :submenu="`${id}-styles`" icon="auto_awesome" :trailing-text="appearance.styleName">Palette style</m3e-menu-item>
      <m3e-menu-item value="reset" icon="restart_alt">Reset appearance</m3e-menu-item>
    </m3e-menu-group>
  </m3e-menu>
  <m3e-menu :id="`${id}-colours`" label="Colour schemes" variant="vibrant" @action="action($event)">
    <m3e-menu-group label="Colour scheme">
      <m3e-menu-item v-for="item in colourPresets" :key="item.seed" type="radio" :value="`seed:${item.seed}`" :checked.prop="appearance.seed === item.seed">{{ item.label }}</m3e-menu-item>
      <m3e-menu-item value="custom" icon="colorize" :trailing-text="customSelected ? appearance.seed.toUpperCase() : undefined">Custom colour…</m3e-menu-item>
    </m3e-menu-group>
  </m3e-menu>
  <m3e-menu :id="`${id}-styles`" label="Palette styles" variant="vibrant" @action="action($event)">
    <m3e-menu-group label="Palette style">
      <m3e-menu-item v-for="item in paletteStyles" :key="item.value" type="radio" :value="`style:${item.value}`" :checked.prop="appearance.variant === item.value">{{ item.label }}</m3e-menu-item>
    </m3e-menu-group>
  </m3e-menu>
  <UiDialog ref="dialog" title="Custom colour">
    <p class="muted">Choose a seed colour. M3E generates a matching palette for the whole panel in light and dark themes.</p>
    <form @submit.prevent="applyCustom">
      <UiField label="Hex colour" v-model="customColour" required maxlength="7" placeholder="#3776AB" autocomplete="off" />
      <UiButton variant="tonal" @click="picker?.click()"><AppIcon name="colorize" />Pick a colour</UiButton>
      <input ref="picker" hidden type="color" aria-label="Custom colour picker" :value="normaliseColour(customColour) || appearance.seed" @input="customColour = ($event.target as HTMLInputElement).value" />
      <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
      <div class="modal-actions"><UiButton variant="text" @click="dialog?.close()">Cancel</UiButton><UiButton type="submit">Apply colour</UiButton></div>
    </form>
  </UiDialog>
</template>
