<template>
  <div ref="el" style="height: 320px;"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ data: Array })
const el = ref(null)
let chart = null

const COLOR = { '甲': '#eb5757', '乙': '#2f80ed', '丙': '#27ae60', '未分类': '#9aa7b8' }

function render() {
  if (!chart) return
  // 按甲乙丙顺序排列
  const order = ['甲', '乙', '丙', '未分类']
  const items = order
    .map(c => props.data.find(d => d.category === c))
    .filter(Boolean)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: p => {
        const d = items[p[0].dataIndex]
        return `<b>${d.category}类</b><br/>` +
               `覆盖病种：${d.diseaseCount} 种<br/>` +
               `确诊：${d.confirmed.toLocaleString()}<br/>` +
               `死亡：${d.deaths.toLocaleString()}`
      },
    },
    grid: { left: 70, right: 110, top: 20, bottom: 20 },
    xAxis: { type: 'value',
             splitLine: { lineStyle: { color: '#eef2f7' } },
             axisLabel: { color: '#7a8699',
                          formatter: v => v >= 1e8 ? (v/1e8).toFixed(0)+'亿'
                                       : v >= 1e4 ? (v/1e4).toFixed(0)+'万' : v } },
    yAxis: { type: 'category',
             data: items.map(d => d.category + '类'),
             axisLine: { lineStyle: { color: '#dfe6ef' } },
             axisLabel: { color: '#4b5b73', fontWeight: 600 } },
    series: [{
      type: 'bar', barWidth: 26,
      data: items.map(d => ({
        value: d.confirmed,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: { type: 'linear', x:0, y:0, x2:1, y2:0,
                   colorStops: [
                     { offset: 0, color: COLOR[d.category] + '88' },
                     { offset: 1, color: COLOR[d.category] }] },
        },
      })),
      label: { show: true, position: 'right', color: '#4b5b73',
               formatter: p => p.value.toLocaleString() },
    }],
  })
}

onMounted(() => { chart = echarts.init(el.value); render() })
watch(() => props.data, render, { deep: true })
const onResize = () => chart && chart.resize()
window.addEventListener('resize', onResize)
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
})
</script>