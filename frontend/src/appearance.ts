import { computed, onScopeDispose, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { createTheme, type Variant } from '@kyralabs/m3e-tokens/theme'

export const defaultSeed = '#1c88ff'
export const colourPresets = [
  { seed: defaultSeed, label: 'Blue' },
  { seed: '#8255d9', label: 'Purple' },
  { seed: '#008577', label: 'Teal' },
  { seed: '#38883e', label: 'Green' },
  { seed: '#ed8b00', label: 'Amber' },
  { seed: '#d64779', label: 'Rose' },
]
export const themeModes = [
  { value: 'system', label: 'System theme', icon: 'contrast' },
  { value: 'light', label: 'Light theme', icon: 'light_mode' },
  { value: 'dark', label: 'Dark theme', icon: 'dark_mode' },
] as const
export const paletteStyles: { value: Variant; label: string }[] = [
  { value: 'vibrant', label: 'Vibrant' },
  { value: 'tonalSpot', label: 'Tonal spot' },
  { value: 'expressive', label: 'Expressive' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'monochrome', label: 'Monochrome' },
]

export function normaliseColour(value: string): string | null {
  const colour = value.trim().toLowerCase()
  if (/^#[0-9a-f]{6}$/.test(colour)) return colour
  if (/^#[0-9a-f]{3}$/.test(colour)) return '#' + [...colour.slice(1)].map(value => value + value).join('')
  return null
}
function read(key: string) { try { return localStorage.getItem(key) || '' } catch { return '' } }
function save(key: string, value: string) { try { localStorage.setItem(key, value) } catch { /* Appearance still works without storage. */ } }

export const useAppearance = defineStore('appearance', () => {
  const mode = ref(themeModes.find(item => item.value === read('beammpy-theme'))?.value || 'system')
  const seed = ref(normaliseColour(read('beammpy-seed')) || defaultSeed)
  const variant = ref<Variant>(paletteStyles.find(item => item.value === read('beammpy-palette-style'))?.value || 'vibrant')
  const colourName = computed(() => colourPresets.find(item => item.seed === seed.value)?.label || seed.value.toUpperCase())
  const styleName = computed(() => paletteStyles.find(item => item.value === variant.value)!.label)
  const systemTheme = matchMedia('(prefers-color-scheme: dark)')
  let appliedPalette = ''

  function apply() {
    const root = document.documentElement
    root.dataset.theme = mode.value === 'system' ? (systemTheme.matches ? 'dark' : 'light') : mode.value
    const key = seed.value + ':' + variant.value
    if (key !== appliedPalette) {
      let style = document.getElementById('beammpy-palette') as HTMLStyleElement | null
      if (seed.value === defaultSeed && variant.value === 'vibrant') style?.remove()
      else {
        const theme = createTheme({ seed: seed.value, variant: variant.value, mode: 'system', motionScheme: 'expressive' })
        if (!style) { style = document.createElement('style'); style.id = 'beammpy-palette'; document.head.append(style) }
        style.textContent = theme.cssText
      }
      appliedPalette = key
    }
    save('beammpy-theme', mode.value)
    save('beammpy-seed', seed.value)
    save('beammpy-palette-style', variant.value)
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', getComputedStyle(root).getPropertyValue('--m3e-sys-color-primary').trim())
  }
  watch([mode, seed, variant], apply, { immediate: true })
  systemTheme.addEventListener('change', apply)
  onScopeDispose(() => systemTheme.removeEventListener('change', apply))
  function setMode(value: string) { const choice = themeModes.find(item => item.value === value); if (choice) mode.value = choice.value }
  function setSeed(value: string) { const colour = normaliseColour(value); if (colour) seed.value = colour }
  function setStyle(value: string) { const choice = paletteStyles.find(item => item.value === value); if (choice) variant.value = choice.value }
  function reset() { mode.value = 'system'; seed.value = defaultSeed; variant.value = 'vibrant' }
  return { mode, seed, variant, colourName, styleName, setMode, setSeed, setStyle, reset }
})
