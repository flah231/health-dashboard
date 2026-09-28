<template>
  <div ref="el" style="height: 320px;"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ data: Array })
const el = ref(null)
let chart = null

const COUNTRY_MAP = {
  CHN: '中国', USA: '美国', IND: '印度', BRA: '巴西', RUS: '俄罗斯',
  JPN: '日本', DEU: '德国', GBR: '英国', FRA: '法国', ZAF: '南非',
  NGA: '尼日利亚', IDN: '印度尼西亚',
}

function render() {
  if (!chart) return
  // 倒序，让值最大的显示在最上面
  const items = [...props.data].reverse()
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 90, right: 40, top: 20, bottom: 20 },
    xAxis: { type: 'value',
             splitLine: { lineStyle: { color: '#eef2f7' } },
             axisLabel: { color: '#7a8699',
                          formatter: v => v >= 1e8 ? (v/1e8).toFixed(0)+'亿'
                                       : v >= 1e4 ? (v/1e4).toFixed(0)+'万' : v } },
    yAxis: { type: 'category',
             data: items.map(d => COUNTRY_MAP[d.region] || d.region),
             axisLine: { lineStyle: { color: '#dfe6ef' } },
             axisLabel: { color: '#4b5b73' } },
    series: [{
      type: 'bar', barWidth: 18,
      data: items.map(d => d.confirmed),
      label: { show: true, position: 'right', color: '#4b5b73',
               formatter: p => p.value.toLocaleString() },
      itemStyle: { borderRadius: [0, 6, 6, 0],
                   color: { type: 'linear', x:0, y:0, x2:1, y2:0,
                            colorStops: [
                              { offset: 0, color: '#8bb9ff' },
                              { offset: 1, color: '#2f80ed' }] } },
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