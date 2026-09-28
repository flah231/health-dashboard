<template>
  <div class="kpi-card" :style="{ '--accent': color }">
    <div class="icon">{{ icon }}</div>
    <div class="info">
      <div class="title">{{ title }}</div>
      <div class="value">{{ display }}</div>
      <div v-if="subtitle" class="subtitle">{{ subtitle }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  title: String,
  value: [Number, String],
  color: { type: String, default: '#2f80ed' },
  icon:  { type: String, default: '📊' },
  subtitle: { type: String, default: '' },
})
const display = computed(() =>
  typeof props.value === 'number' ? props.value.toLocaleString() : props.value
)
</script>

<style scoped>
.kpi-card {
  display: flex; align-items: center; gap: 16px;
  background: #fff; border-radius: 12px; padding: 22px 24px;
  box-shadow: 0 2px 12px rgba(31,45,61,.06);
  border-left: 4px solid var(--accent);
  transition: transform .2s, box-shadow .2s;
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(31,45,61,.12); }
.icon {
  width: 52px; height: 52px; display: grid; place-items: center;
  border-radius: 12px; font-size: 26px;
  background: color-mix(in srgb, var(--accent) 12%, #fff);
}
.info { min-width: 0; }
.title { font-size: 13px; color: #7a8699; margin-bottom: 6px; }
.value { font-size: 24px; font-weight: 700; color: var(--accent); letter-spacing: .5px;
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.subtitle { font-size: 11px; color: #9aa7b8; margin-top: 4px; }
</style>