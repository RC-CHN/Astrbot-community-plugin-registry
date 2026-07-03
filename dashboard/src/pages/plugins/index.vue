<template>
  <page-header title="插件" description="管理插件提交、构建状态与发布状态">
    <template #actions>
      <n-button :loading="mutations.refreshCache.isPending.value" @click="mutations.refreshCache.mutate()">
        刷新缓存
      </n-button>
      <n-button type="primary" @click="showSubmit = true">提交插件</n-button>
    </template>
  </page-header>

  <page-toolbar>
    <n-input v-model:value="filters.q" clearable placeholder="搜索插件 / 作者" style="max-width: 320px" />
    <n-select
      v-model:value="filters.status"
      clearable
      placeholder="状态"
      :options="statusOptions"
      style="width: 180px"
    />
  </page-toolbar>

  <api-error-alert :error="query.error.value" />
  <n-data-table
    :columns="columns"
    :data="query.data.value?.items || []"
    :loading="query.isLoading.value"
    :pagination="pagination"
    :row-key="rowKey"
    remote
    @update:page="filters.page = $event"
  />
  <plugin-submit-modal v-model:show="showSubmit" />
</template>

<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NPopconfirm, type DataTableColumns } from 'naive-ui'

import type { PluginListParams, PluginSummary, PluginStatus } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import PageToolbar from '@/components/common/page-toolbar.vue'
import StatusTag from '@/components/common/status-tag.vue'
import PluginSubmitModal from '@/components/plugin/plugin-submit-modal.vue'
import PluginTitle from '@/components/plugin/plugin-title.vue'
import { usePluginMutations, usePlugins } from '@/query/plugins'
import { formatDateTime } from '@/utils/datetime'

const router = useRouter()
const route = useRoute()
const showSubmit = ref(false)
const filters = reactive<PluginListParams>({
  q: String(route.query.q || ''),
  status: '',
  page: 1,
  page_size: 20,
})
const params = computed(() => ({ ...filters }))
const query = usePlugins(params)
const mutations = usePluginMutations()

watch(
  () => [filters.q, filters.status],
  () => {
    filters.page = 1
  },
)

const statusOptions = [
  { label: '待审核', value: 'pending' },
  { label: '已发布', value: 'active' },
  { label: '已禁用', value: 'disabled' },
  { label: '已删除', value: 'deleted' },
]

const pagination = computed(() => ({
  page: filters.page || 1,
  pageSize: filters.page_size || 20,
  itemCount: query.data.value?.total || 0,
}))

const columns: DataTableColumns<PluginSummary> = [
  {
    title: '插件',
    key: 'plugin_key',
    render: (row) => h(PluginTitle, { plugin: row }),
  },
  { title: '作者', key: 'author', width: 160 },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (row) => h(StatusTag, { kind: 'plugin', value: row.status }),
  },
  { title: '版本数', key: 'version_count', width: 90 },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 140,
    render: (row) => formatDateTime(row.updated_at),
  },
  {
    title: '操作',
    key: 'actions',
    align: 'right',
    width: 280,
    render(row) {
      return [
        h(NButton, { size: 'small', quaternary: true, onClick: () => router.push(`/plugins/${row.id}`) }, { default: () => '查看' }),
        row.status === 'pending'
          ? h(
              NButton,
              {
                size: 'small',
                type: 'primary',
                secondary: true,
                onClick: () =>
                  mutations.updatePluginStatus.mutate({
                    pluginId: row.id,
                    status: 'active' as PluginStatus,
                  }),
              },
              { default: () => '通过' },
            )
          : null,
        row.status !== 'deleted'
          ? h(NPopconfirm, { positiveText: '确认删除', negativeText: '取消', onPositiveClick: () => mutations.deletePlugin.mutate({ pluginId: row.id }) }, {
              trigger: () =>
                h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '删除' }),
              default: () => '删除后插件和版本会从公开索引移除，确认继续？',
            })
          : null,
      ]
    },
  },
]

const rowKey = (row: PluginSummary) => row.id
</script>
