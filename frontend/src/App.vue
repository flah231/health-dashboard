<template>
  <div class="app">
    <header class="app-header">
      <div class="brand">
        <div class="logo">🏥</div>
        <div>
          <h1>医疗疾病信息数据分析看板</h1>
          <p class="sub">Health Disease Analytics Dashboard</p>
        </div>
      </div>
      <div class="actions">
        <span class="ws-status" :class="{ online: wsConnected }">
          <span class="dot"></span>
          {{ wsConnected ? '实时连接' : '连接中…' }}
        </span>
        <div v-if="syncRunning" class="sync-progress">
          <span class="sync-label">
            ⟳ 正在更新
            <span v-if="syncPendingText">{{ syncPendingText }}</span>
          </span>
        </div>
        <span class="update-time">最后更新：{{ lastUpdated }}</span>
        
        <!-- ★ 新增：打开数据目录按钮 -->
        <el-button size="small" @click="openDataDir">📁 数据目录</el-button>
        
        <el-button type="primary" :loading="loading" @click="refreshAndSync">
          刷新数据
        </el-button>
      </div>
    </header>

    <section class="filter-bar">
      <div class="filter-item">
        <label>数据源</label>
        <el-select v-model="filters.source" placeholder="全部" clearable size="large"
                   style="width: 160px" @change="loadAll">
          <el-option v-for="s in options.sources" :key="s" :label="s" :value="s" />
        </el-select>
      </div>
      <div class="filter-item">
        <label>统计年份</label>
        <el-select v-model="filters.year" placeholder="最新" clearable size="large"
                   style="width: 130px" @change="loadAll">
          <el-option v-for="y in options.years" :key="y" :label="y + ' 年'" :value="y" />
        </el-select>
      </div>
      <div class="filter-item">
        <label>疾病（月度趋势）</label>
        <el-select v-model="filters.disease" placeholder="全部病种" clearable
                   filterable size="large" style="width: 200px" @change="loadMonthly">
          <el-option v-for="d in options.diseases" :key="d" :label="d" :value="d" />
        </el-select>
      </div>
      <div class="filter-hint">
        💡 数据源默认使用「最新年份」，避免跨年累加
      </div>
    </section>

    <section class="kpi-row">
      <KpiCard title="累计确诊" :value="overview.confirmed" color="#2f80ed" icon="🦠"
               :subtitle="kpiSubtitle" />
      <KpiCard v-if="overview.cured > 0"
               title="累计治愈" :value="overview.cured" color="#27ae60" icon="💚"
               :subtitle="kpiSubtitle" />
      <KpiCard v-else
               title="报告月份数" :value="overview.monthCount || 0" color="#27ae60" icon="📅"
               :subtitle="kpiSubtitle" />
      <KpiCard title="累计死亡" :value="overview.deaths" color="#eb5757" icon="⚠️"
               :subtitle="kpiSubtitle" />
      <KpiCard title="监测病种" :value="overview.diseaseCount" color="#9b51e0" icon="📋"
               :subtitle="`覆盖 ${overview.regionCount} 个地区`" />
    </section>

    <section class="charts-row">
      <div class="panel panel-lg">
        <div class="panel-title">
          月度确诊 / 死亡趋势（近 24 个月）
          <span v-if="filters.disease" class="panel-subtitle">
            · {{ filters.disease }}
          </span>
        </div>
        <TrendChart :data="monthly" x-field="month" :show-deaths="true" />
      </div>
      <div class="panel panel-sm">
        <div class="panel-title">疾病确诊排行 TOP8</div>
        <RankingChart :data="ranking" />
      </div>
    </section>

    <section class="charts-row">
      <div class="panel panel-half">
        <div class="panel-title">各年度确诊 / 死亡汇总</div>
        <YearlyChart :data="yearly" />
      </div>
      <div class="panel panel-half">
        <div class="panel-title">法定传染病分类占比（甲 / 乙 / 丙）</div>
        <CategoryChart :data="categories" />
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">疾病统计明细（共 {{ detail.total }} 条）</div>
      <RankingTable
        :items="detail.items"
        :total="detail.total"
        :page="detail.page"
        :page-size="detail.pageSize"
        @page-change="onPageChange"
        @size-change="onSizeChange"
      />
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import KpiCard from './components/KpiCard.vue'
import TrendChart from './components/TrendChart.vue'
import RankingChart from './components/RankingChart.vue'
import YearlyChart from './components/YearlyChart.vue'
import CategoryChart from './components/CategoryChart.vue'
import RankingTable from './components/RankingTable.vue'
import {
  getFilters, getOverview, getMonthly, getYearly,
  getRanking, getCategories, getDetail,
  getSyncStatus, triggerSync,
} from './api'
import { useWebSocket } from './composables/useWebSocket'

const filters = reactive({ source: '', year: null, disease: '' })
const options = reactive({ sources: [], years: [], diseases: [] })

const overview = ref({ confirmed: 0, cured: 0, deaths: 0, diseaseCount: 0, regionCount: 0, year: null, monthCount: 0 })
const monthly = ref([])
const yearly = ref([])
const ranking = ref([])
const categories = ref([])
const detail = ref({ items: [], total: 0, page: 1, pageSize: 20 })

const loading = ref(false)
const lastUpdated = ref('—')

// 同步状态
const syncRunning = ref(false)
const syncDoneSources = ref([])      // 已完成的源
const syncPendingSources = ref([])   // 还在跑的源

// applySyncStatus 里新用到的三个响应式变量
const syncCurrent = ref('')
const syncIndex = ref(0)
const syncTotalSources = ref(0)

const syncPendingText = computed(() => {
  if (!syncPendingSources.value.length) return ''
  return syncPendingSources.value.join(', ')
})

const kpiSubtitle = computed(() => {
  const y = overview.value.year ? `${overview.value.year} 年` : '全部年份'
  return filters.source ? `${y} · ${filters.source}` : y
})

function commonParams() {
  const p = {}
  if (filters.source) p.source_key = filters.source
  if (filters.year) p.year = filters.year
  return p
}

async function loadMonthly() {
  try {
    const p = { months: 24, source_key: filters.source || undefined }
    if (filters.disease) p.disease_name = filters.disease
    monthly.value = await getMonthly(p)
  } catch (e) {
    ElMessage.error('月度趋势加载失败：' + e.message)
  }
}

async function loadAll() {
  loading.value = true
  try {
    const params = commonParams()
    const [o, y, r, c, d] = await Promise.all([
      getOverview(params),
      getYearly({ source_key: filters.source || undefined }),
      getRanking({ ...params, limit: 8 }),
      getCategories(params),
      getDetail({ ...params, page: 1, page_size: detail.value.pageSize }),
    ])
    overview.value = o
    yearly.value = y
    ranking.value = r
    categories.value = c
    detail.value = d
    await loadMonthly()
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e) {
    ElMessage.error('数据加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

let refreshing = false
// ★ 修复1：silentRefresh 开头添加 await initOptions()
async function silentRefresh() {
  if (refreshing) return
  refreshing = true
  try {
    // ★ 关键：先刷新筛选项（因为可能有新数据源/年份/疾病）
    await initOptions()

    const params = commonParams()
    const [o, y, r, c, d] = await Promise.all([
      getOverview(params),
      getYearly({ source_key: filters.source || undefined }),
      getRanking({ ...params, limit: 8 }),
      getCategories(params),
      getDetail({ ...params, page: detail.value.page, page_size: detail.value.pageSize }),
    ])
    overview.value = o
    yearly.value = y
    ranking.value = r
    categories.value = c
    detail.value = d
    await loadMonthly()
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e) {
    console.warn('静默刷新失败', e)
  } finally {
    refreshing = false
  }
}

async function onPageChange(p) {
  try {
    detail.value = await getDetail({ ...commonParams(), page: p, page_size: detail.value.pageSize })
  } catch (e) {
    ElMessage.error('翻页失败：' + e.message)
  }
}

async function onSizeChange(s) {
  try {
    detail.value = await getDetail({ ...commonParams(), page: 1, page_size: s })
  } catch (e) {
    ElMessage.error('改变分页大小失败：' + e.message)
  }
}

async function initOptions() {
  try {
    const f = await getFilters()
    options.sources = f.sources
    options.years = f.years
    options.diseases = f.diseases
  } catch (e) {
    console.warn('获取筛选项失败', e)
  }
}

// ---------- 同步状态同步 ----------

// ★ 修复2：applySyncStatus 添加“后端已停，前端强制重置”保险
function applySyncStatus(st) {
  const backendRunning = !!st.running
  // 后端说停了，本地还认为在跑 → 强制重置
  if (!backendRunning && syncRunning.value) {
    console.log('[Sync] 后端已停止，强制重置前端状态')
    syncRunning.value = false
    syncCurrent.value = ''
    syncIndex.value = 0
    syncTotalSources.value = 0
    return
  }
  syncRunning.value = backendRunning
  syncCurrent.value = st.current_source || ''
  syncIndex.value = st.current_index || 0
  syncTotalSources.value = st.total_sources || 0
}

/**
 * 触发同步：
 *   1. 先查后端是否已在跑，如果已经在跑就只同步状态，不触发
 *   2. 只在本次会话里触发一次（sessionStorage 记忆）
 */
async function triggerSmartSync() {
  // 会话级记忆：刚打开页面 5 分钟内不重复触发
  const lastTrigger = sessionStorage.getItem('lastSyncTrigger')
  const now = Date.now()
  if (lastTrigger && now - parseInt(lastTrigger) < 5 * 60 * 1000) {
    console.log('[Sync] 5 分钟内已触发过，跳过')
    return
  }

  // 先查后端状态
  try {
    const st = await getSyncStatus()
    if (st.running) {
      console.log('[Sync] 后端已有任务在跑，只同步状态')
      applySyncStatus(st)
      sessionStorage.setItem('lastSyncTrigger', String(now))
      return
    }
  } catch (e) {
    console.warn('[Sync] 查询状态失败，尝试触发')
  }

  // 后端空闲 → 触发一次
  try {
    const res = await triggerSync()
    if (res.ok) {
      sessionStorage.setItem('lastSyncTrigger', String(now))
      console.log('[Sync] 已触发')
    } else {
      console.warn('[Sync] 未触发：', res.message)
    }
  } catch (e) {
    console.warn('[Sync] 触发失败：', e.message)
  }
}

async function refreshAndSync() {
  await loadAll()
  // 用户主动点刷新：清掉会话记忆，强制触发一次，并要求全量重抓
  sessionStorage.removeItem('lastSyncTrigger')
  try {
    await fetch('/api/sync/smart?skip_hours=0', { method: 'POST' })
    ElMessage.info('已触发全量更新，抓取完成后看板会自动刷新')
  } catch (e) {
    console.warn('触发失败', e)
  }
}

// ---------- 打开数据目录（Electron 专用） ----------

async function openDataDir() {
  try {
    // 只有在 Electron 里才能调
    if (window.electronAPI?.openDataDir) {
      await window.electronAPI.openDataDir()
    } else {
      ElMessage.info('请在桌面应用中使用此功能')
    }
  } catch (e) {
    console.warn('打开数据目录失败', e)
  }
}

// ---------- 状态轮询 ----------

let statusTimer = null
function startStatusPolling() {
  statusTimer = setInterval(async () => {
    try {
      const st = await getSyncStatus()
      applySyncStatus(st)
    } catch (e) {
      // 网络错误忽略
    }
  }, 3000)
}

// ---------- WebSocket ----------

const { connected: wsConnected } = useWebSocket((msg) => {
  console.log('[WS] 收到：', msg)

  if (msg.type === 'data_updated') {
    silentRefresh()
    return
  }

  if (msg.type === 'sync_started') {
    syncRunning.value = true
    syncDoneSources.value = []
    syncPendingSources.value = msg.sources || []
    return
  }

  if (msg.type === 'sync_progress') {
    // 单个源开始抓，pending_sources 由 sync_source_done 更新
    // 这里不做处理
    return
  }

  if (msg.type === 'sync_source_done') {
    // 从 pending 中移除，加入 done
    if (msg.source_key && syncPendingSources.value.includes(msg.source_key)) {
      syncPendingSources.value = syncPendingSources.value.filter(s => s !== msg.source_key)
    }
    if (msg.source_key && !syncDoneSources.value.includes(msg.source_key)) {
      syncDoneSources.value = [...syncDoneSources.value, msg.source_key]
    }
    silentRefresh()
    return
  }

  if (msg.type === 'sync_finished') {
    syncRunning.value = false
    syncDoneSources.value = []
    syncPendingSources.value = []
    lastUpdated.value = new Date().toLocaleTimeString()
    ElMessage.success(`数据同步完成，共 ${msg.total_records} 条`)
    return
  }
})

// ---------- 生命周期 ----------

onMounted(async () => {
  await initOptions()
  await loadAll()

  // 先查一次同步状态
  try {
    const st = await getSyncStatus()
    applySyncStatus(st)
  } catch (e) {
    console.warn('查询同步状态失败', e)
  }

  // 启动轮询（每 3 秒同步一次状态，解决"看板进度落后"）
  startStatusPolling()

  // 触发同步（内部会先查状态，已有任务则跳过）
  triggerSmartSync()
})

onBeforeUnmount(() => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
})
</script>

<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f4f7fb;
  color: #1f2d3d;
}
.app { padding: 0 24px 32px; }

.app-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 28px; margin: 20px -24px 16px;
  background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
  color: #fff; box-shadow: 0 4px 16px rgba(30,60,114,.25);
}
.brand { display: flex; align-items: center; gap: 16px; }
.logo {
  width: 52px; height: 52px; display: grid; place-items: center;
  background: rgba(255,255,255,.15); border-radius: 12px; font-size: 26px;
}
.app-header h1 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: .5px; }
.sub { margin: 4px 0 0; font-size: 12px; opacity: .75; }
.actions { display: flex; align-items: center; gap: 14px; }
.update-time { font-size: 13px; opacity: .85; }

.ws-status {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; opacity: .85; padding: 4px 10px;
  background: rgba(255,255,255,.1); border-radius: 12px;
}
.ws-status .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #f2c94c;
  box-shadow: 0 0 6px #f2c94c;
}
.ws-status.online .dot {
  background: #27ae60;
  box-shadow: 0 0 6px #27ae60;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .4; }
}

.sync-progress {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; opacity: .9; padding: 4px 10px;
  background: rgba(255,255,255,.12); border-radius: 12px;
}
.sync-label {
  animation: syncPulse 1.5s ease-in-out infinite;
}
@keyframes syncPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .55; }
}

.filter-bar {
  display: flex; align-items: flex-end; gap: 20px; flex-wrap: wrap;
  background: #fff; padding: 16px 24px; border-radius: 12px;
  margin-bottom: 20px; box-shadow: 0 2px 12px rgba(31,45,61,.06);
}
.filter-item { display: flex; flex-direction: column; gap: 6px; }
.filter-item label { font-size: 12px; color: #7a8699; padding-left: 4px; }
.filter-hint { font-size: 12px; color: #9aa7b8; margin-left: auto; padding-bottom: 10px; }

.kpi-row {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 20px; margin-bottom: 20px;
}
.charts-row {
  display: grid; grid-template-columns: 2fr 1fr;
  gap: 20px; margin-bottom: 20px;
}
.panel {
  background: #fff; border-radius: 12px; padding: 20px 24px;
  box-shadow: 0 2px 12px rgba(31,45,61,.06);
  margin-bottom: 20px;
}
.charts-row .panel { margin-bottom: 0; }
.panel-title {
  font-size: 15px; font-weight: 600; color: #1f2d3d;
  padding-left: 10px; border-left: 4px solid #2f80ed;
  margin-bottom: 16px;
}
.panel-subtitle { font-weight: 400; color: #7a8699; font-size: 13px; margin-left: 6px; }

@media (max-width: 1100px) {
  .kpi-row    { grid-template-columns: repeat(2, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
  .filter-hint { display: none; }
}
</style>