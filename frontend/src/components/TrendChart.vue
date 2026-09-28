<template>
  <div ref="el" style="height: 320px;"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: Array,
  xField: { type: String, default: 'date' },
  showDeaths: { type: Boolean, default: false },
})

const el = ref(null)
let chart = null

// 把渐变生成逻辑抽出来，避免深层嵌套
function makeGradient(c1, c2) {
  return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: c1 },
    { offset: 1, color: c2 },
  ])
}

function buildSeries() {
  const x = props.data.map(d => d[props.xField] || d.date || d.month)
  const confirmed = props.data.map(d => d.confirmed)
  const deaths = props.data.map(d => d.deaths || 0)

  const list = [
    {
      name: '确诊',
      type: 'line',
      smooth: true,
      data: confirmed,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 3, color: '#2f80ed' },
      itemStyle: { color: '#2f80ed' },
      areaStyle: { color: makeGradient('rgba(47,128,237,.35)', 'rgba(47,128,237,0)') },
    },
  ]

  if (props.showDeaths) {
    list.push({
      name: '死亡',
      type: 'line',
      smooth: true,
      data: deaths,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 3, color: '#eb5757' },
      itemStyle: { color: '#eb5757' },
      areaStyle: { color: makeGradient('rgba(235,87,87,.30)', 'rgba(235,87,87,0)') },
    })
  }

  return { x, list }
}

function render() {
  if (!chart) return
  const { x, list } = buildSeries()

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: list.map(s => s.name), right: 0, top: 0 },
    grid: { left: 55, right: 20, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: x,
      axisLine: { lineStyle: { color: '#dfe6ef' } },
      axisLabel: { color: '#7a8699', rotate: x.length > 14 ? 30 : 0 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#eef2f7' } },
      axisLabel: {
        color: '#7a8699',
        formatter: v => v >= 1e8 ? (v / 1e8).toFixed(1) + '亿'
                    : v >= 1e4 ? (v / 1e4).toFixed(0) + '万'
                    : v,
      },
    },
    series: list,
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
