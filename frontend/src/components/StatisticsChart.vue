<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { StatisticsPoint } from '../types'
import UiButton from './UiButton.vue'
const props = defineProps<{ title: string; metric: 'cpu' | 'memory' | 'players'; unit: string; points: StatisticsPoint[]; bucketSeconds: number }>()
const selected = ref<number | null>(null), showTable = ref(false)
const container = ref<HTMLElement>(), width = ref(700)
let resize: ResizeObserver | undefined
onMounted(() => {
  resize = new ResizeObserver(entries => { width.value = Math.max(240, entries[0].contentRect.width) })
  if (container.value) resize.observe(container.value)
})
onUnmounted(() => resize?.disconnect())
watch(() => props.points.length, () => { selected.value = null })
const observed = computed(() => props.points.filter(p => p[props.metric] !== null))
const maximum = computed(() => {
  const largest = Math.max(1,
  ...props.points.map(p => p[props.metric] ?? 0),
  ...props.points.map(p => props.metric === 'players' ? 0 : p[props.metric === 'cpu' ? 'cpu_peak' : 'memory_peak'] ?? 0))
  return props.metric === 'players' ? Math.ceil(largest) : largest * 1.1
})
const ticks = computed(() => [...new Set([0, props.metric === 'players' ? Math.round(maximum.value / 2) : maximum.value / 2, maximum.value])])
const plotWidth = computed(() => width.value - 80)
const x = (index: number) => 58 + (index + .5) / Math.max(1, props.points.length) * plotWidth.value
const y = (value: number) => 180 - value / maximum.value * 160
function path(peak = false) {
  let open = false
  return props.points.map((p, index) => {
    const value = peak ? p[props.metric === 'cpu' ? 'cpu_peak' : 'memory_peak'] : p[props.metric]
    if (value === null) { open = false; return '' }
    const command = `${open ? 'L' : 'M'}${x(index)},${y(value)}`
    open = true; return command
  }).join(' ')
}
function format(value: number | null) { return value === null ? 'No data' : `${value.toLocaleString(undefined, { maximumFractionDigits: props.metric === 'players' ? 0 : 1 })}${props.unit ? ' ' + props.unit : ''}` }
function date(time: number) { return new Date(time * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', ...(props.bucketSeconds < 60 ? { second: '2-digit' as const } : {}) }) }
const intervalLabel = computed(() => props.bucketSeconds < 60 ? `${props.bucketSeconds} sec` : `${props.bucketSeconds / 60} min`)
function axisDate(time: number) {
  if (width.value >= 500) return date(time)
  const value = new Date(time * 1000)
  const span = props.points.length > 1 ? props.points[props.points.length - 1].time - props.points[0].time : 0
  return span < 86400 ? value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : value.toLocaleDateString([], { month: 'short', day: 'numeric' })
}
const inspected = computed(() => selected.value === null ? null : props.points[selected.value])
const peakKey = computed(() => props.metric === 'cpu' ? 'cpu_peak' : 'memory_peak')
function step(direction: number) { selected.value = Math.max(0, Math.min(props.points.length - 1, (selected.value ?? props.points.length - 1) + direction)) }
const summary = computed(() => observed.value.length ? `${observed.value.length} observed ${observed.value.length === 1 ? 'interval' : 'intervals'}. Peak ${format(Math.max(...observed.value.map(p => props.metric === 'players' ? p.players! : p[peakKey.value] ?? p[props.metric]!)))}.` : 'No observations in this period.')
</script>
<template>
  <article ref="container" class="statistics-chart m3e-card m3e-card--outlined" :aria-label="title">
    <div class="statistics-chart-heading"><h3>{{ title }}</h3><span class="muted">{{ unit || 'Players' }}</span></div>
    <p class="muted">{{ summary }} {{ metric === 'players' ? 'Bars show peak concurrent players.' : 'Solid: average · dashed: peak.' }}</p>
    <div v-if="!observed.length" class="statistics-empty">No data yet. Observations will appear here while this server runs.</div>
    <svg v-else class="statistics-svg" :viewBox="`0 0 ${width} 230`" role="img" :aria-label="`${title}. ${summary} Use arrow keys to inspect intervals, or show the data table.`" tabindex="0" @keydown.left.prevent="step(-1)" @keydown.right.prevent="step(1)" @pointerleave="selected = null">
      <title>{{ title }}</title><desc>{{ summary }} Missing observations are gaps.</desc>
      <g v-for="tick in ticks" :key="tick" class="chart-axis">
        <line x1="58" :x2="width - 22" :y1="y(tick)" :y2="y(tick)" />
        <text x="48" :y="y(tick) + 4" text-anchor="end">{{ tick.toLocaleString(undefined, { maximumFractionDigits: metric === 'players' ? 0 : 1 }) }}</text>
      </g>
      <template v-if="metric === 'players'">
        <rect v-for="(point, index) in points" :key="point.time" :x="x(index) - plotWidth * .42 / points.length" :y="y(point.players ?? 0)" :width="plotWidth * .84 / points.length" :height="point.players === null ? 0 : Math.max(1, 180 - y(point.players))" class="chart-bar"><title>{{ date(point.time) }}: {{ format(point.players) }}</title></rect>
      </template>
      <template v-else><path :d="path(true)" class="chart-line chart-peak" /><path :d="path()" class="chart-line" /><circle v-for="(point, index) in points.filter(p => p[metric] !== null)" :key="point.time" :cx="x(points.indexOf(point))" :cy="y(point[metric]!)" r="2" class="chart-point" /></template>
      <rect v-for="(point, index) in points" :key="`hit-${point.time}`" :x="58 + index * plotWidth / points.length" y="16" :width="plotWidth / points.length" height="166" fill="transparent" @pointerenter="selected = index"><title>{{ date(point.time) }}: {{ format(point[metric]) }}</title></rect>
      <line v-if="selected !== null" :x1="x(selected)" :x2="x(selected)" y1="16" y2="182" class="chart-cursor" />
      <text x="58" y="211" class="chart-label">{{ points.length ? axisDate(points[0].time) : '' }}</text>
      <text :x="width - 22" y="211" text-anchor="end" class="chart-label">{{ points.length ? axisDate(points[points.length - 1].time) : '' }}</text>
    </svg>
    <p class="chart-tooltip muted" aria-live="polite">{{ inspected ? `${date(inspected.time)} · ${format(inspected[metric])}${metric === 'players' ? '' : ' · peak ' + format(inspected[peakKey])}` : `Intervals: ${intervalLabel} · gaps indicate missing observations.` }}</p>
    <UiButton variant="text" :aria-expanded="showTable" @click="showTable = !showTable">{{ showTable ? 'Hide' : 'Show' }} {{ title.toLowerCase() }} data table</UiButton>
    <div v-if="showTable" class="statistics-table-wrap" tabindex="0" :aria-label="`${title} data`"><table class="statistics-table"><caption>{{ title }} · {{ unit || 'players' }}</caption><thead><tr><th scope="col">Time</th><th scope="col">{{ metric === 'players' ? 'Peak' : 'Average' }}</th><th v-if="metric !== 'players'" scope="col">Peak</th></tr></thead><tbody><tr v-for="point in points" :key="point.time"><th scope="row">{{ date(point.time) }}</th><td>{{ format(point[metric]) }}</td><td v-if="metric !== 'players'">{{ format(point[peakKey]) }}</td></tr></tbody></table></div>
  </article>
</template>
