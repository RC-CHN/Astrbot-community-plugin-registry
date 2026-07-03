<template>
  <page-header title="构建" description="排查构建状态和失败版本" />
  <page-toolbar>
    <n-input v-model:value="filters.q" clearable placeholder="搜索插件" style="max-width: 320px" />
  </page-toolbar>
  <api-error-alert :error="query.error.value" />
  <n-data-table :columns="columns" :data="rows" :loading="query.isLoading.value" :pagination="{ pageSize: 20 }" />
</template>

<script setup lang="ts">
import { computed, h, reactive } from 'vue'
import { NButton, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'

import type { PluginListParams, PluginSummary } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import PageToolbar from '@/components/common/page-toolbar.vue'
import PluginTitle from '@/components/plugin/plugin-title.vue'
import { usePlugins } from '@/query/plugins'
import { formatDateTime } from '@/utils/datetime'

const router = useRouter()
const filters = reactive<PluginListParams>({ q: '', page: 1, page_size: 100 })
const query = usePlugins(computed(() => ({ ...filters })))
const rows = computed(() => query.data.value?.items || [])

const columns: DataTableColumns<PluginSummary> = [
  { title: '插件', key: 'plugin', render: (row) => h(PluginTitle, { plugin: row }) },
  { title: '状态', key: 'status', width: 120 },
  { title: '版本数', key: 'version_count', width: 100 },
  { title: '更新时间', key: 'updated_at', width: 150, render: (row) => formatDateTime(row.updated_at) },
  {
    title: '操作',
    key: 'actions',
    align: 'right',
    width: 120,
    render: (row) => h(NButton, { size: 'small', onClick: () => router.push(`/plugins/${row.id}`) }, { default: () => '查看详情' }),
  },
]
</script>
