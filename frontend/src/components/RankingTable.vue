<template>
  <el-table :data="items" stripe style="width: 100%"
            :header-cell-style="{ background: '#f7f9fc', color: '#4b5b73', fontWeight: 600 }">
    <el-table-column type="index" label="#" width="60" align="center"
                     :index="i => (page - 1) * pageSize + i + 1" />
    <el-table-column prop="source" label="数据源" width="110">
      <template #default="{ row }">
        <el-tag size="small" effect="plain">{{ row.source }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="diseaseName" label="疾病名称" min-width="140" />
    <el-table-column prop="region" label="地区 / 国家" width="110" />
    <el-table-column prop="date" label="统计日期" width="120" sortable />
    <el-table-column prop="confirmed" label="确诊" sortable align="right" width="130">
      <template #default="{ row }">{{ row.confirmed.toLocaleString() }}</template>
    </el-table-column>
    <el-table-column v-if="hasCured" prop="cured" label="治愈" sortable align="right" width="120">
      <template #default="{ row }">{{ row.cured.toLocaleString() }}</template>
    </el-table-column>
    <el-table-column prop="deaths" label="死亡" sortable align="right" width="120">
      <template #default="{ row }">{{ row.deaths.toLocaleString() }}</template>
    </el-table-column>
  </el-table>

  <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
    <el-pagination
      layout="total, sizes, prev, pager, next"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="p => emit('page-change', p)"
      @size-change="s => emit('size-change', s)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: Array,
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})
const emit = defineEmits(['page-change', 'size-change'])

// 只有存在非零治愈数据时才显示治愈列
const hasCured = computed(() =>
  props.items && props.items.some(r => r.cured > 0)
)
</script>