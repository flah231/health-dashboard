<template>
  <div ref="el" style="height: 320px;"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ data: Array })
const el = ref(null)
let chart = null

function render() {
  if (!chart) return
  const years = props.data.map(d => d.year + '年')
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['确诊', '死亡'], right: 0, top: 0 },
    grid: { left: 50, right: 20, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: years,
             axisLine: { lineStyle: { color: '#dfe6ef' } },
             axisLabel: { color: '#7a8699' } },
    yAxis: { type: 'value',
             splitLine: { lineStyle: { color: '#eef2f7' } },
             axisLabel: { color: '#7a8699',
                          formatter: v => v >= 1e8 ? (v/1e8).toFixed(1)+'亿'
                                       : v >= 1e4 ? (v/1e4).toFixed(0)+'万' : v } },
    series: [
      { name: '确诊', type: 'bar', barWidth: 24, data: props.data.map(d => d.confirmed),
        itemStyle: { borderRadius: [6,6,0,0],
                     color: { type: 'linear', x:0, y:0, x2:0, y2:1,
                              colorStops: [
                                { offset: 0, color: '#4a9eff' },
                                { offset: 1, color: '#2f80ed' }] } } },
      { name: '死亡', type: 'bar', barWidth: 24, data: props.data.map(d => d.deaths),
        itemStyle: { borderRadius: [6,6,0,0],
                     color: { type: 'linear', x:0, y:0, x2:0, y2:1,
                              colorStops: [
                                { offset: 0, color: '#ff8a80' },
                                { offset: 1, color: '#eb5757' }] } } },
    ],
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