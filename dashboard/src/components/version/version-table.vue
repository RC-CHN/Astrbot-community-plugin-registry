<template>
  <n-data-table
    :columns="columns"
    :data="versions"
    :pagination="false"
    :row-key="rowKey"
    size="small"
  />
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { NButton, NButtonGroup, NTag, NTooltip, type DataTableColumns } from 'naive-ui'

import type { PluginDetail, VersionStatus, VersionSummary } from '@/api/types'
import CopyableText from '@/components/common/copyable-text.vue'
import StatusTag from '@/components/common/status-tag.vue'
import { canActivateVersion, getVersionBlockers } from '@/composables/use-plugin-actions'
import { getScanAggregateMeta } from '@/composables/use-status-meta'
import { formatDateTime } from '@/utils/datetime'
import { formatFileSize } from '@/utils/file-size'

const props = defineProps<{
  plugin: PluginDetail
  versions: VersionSummary[]
  loading?: boolean
}>()

const emit = defineEmits<{
  setVersionStatus: [version: VersionSummary, status: VersionStatus]
  setLatest: [version: VersionSummary]
}>()

const rowKey = (row: VersionSummary) => row.id

const columns = computed<DataTableColumns<VersionSummary>>(() => [
  {
    title: '版本',
    key: 'version',
    render(row) {
      return h('div', { class: 'version-cell' }, [
        h('div', { class: 'version-name' }, row.version),
        row.is_latest ? h(NTag, { type: 'success', size: 'small', round: true }, { default: () => 'latest' }) : null,
      ])
    },
  },
  { title: '来源', key: 'source_type', width: 110 },
  {
    title: 'Commit',
    key: 'commit_sha',
    width: 170,
    render: (row) => h(CopyableText, { value: row.commit_sha }),
  },
  {
    title: '构建',
    key: 'build_status',
    width: 110,
    render: (row) => h(StatusTag, { kind: 'build', value: row.build_status }),
  },
  {
    title: '版本状态',
    key: 'version_status',
    width: 110,
    render: (row) => h(StatusTag, { kind: 'version', value: row.version_status }),
  },
  {
    title: '扫描',
    key: 'scan',
    width: 100,
    render(row) {
      const meta = getScanAggregateMeta(row.scan)
      return h(NTag, { type: meta.type, size: 'small', round: true }, { default: () => meta.label })
    },
  },
  {
    title: '大小',
    key: 'file_size',
    width: 100,
    render: (row) => formatFileSize(row.file_size),
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 130,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '操作',
    key: 'actions',
    align: 'right',
    width: 210,
    render(row) {
      const activeCheck = canActivateVersion(row)
      const latestBlockers = getVersionBlockers(props.plugin, row)
      const activeButton = h(
        NButton,
        {
          size: 'small',
          disabled: !activeCheck.ok || row.version_status === 'active',
          onClick: () => emit('setVersionStatus', row, 'active'),
        },
        { default: () => '设为可用' },
      )
      const latestButton = h(
        NButton,
        {
          size: 'small',
          type: row.is_latest ? 'primary' : 'default',
          disabled: latestBlockers.length > 0 || row.is_latest,
          onClick: () => emit('setLatest', row),
        },
        { default: () => '设为 latest' },
      )
      return h(NButtonGroup, null, {
        default: () => [
          activeCheck.ok ? activeButton : withTooltip(activeButton, activeCheck.reason),
          latestBlockers.length ? withTooltip(latestButton, latestBlockers.join('；')) : latestButton,
        ],
      })
    },
  },
])

function withTooltip(node: ReturnType<typeof h>, text: string) {
  return h(NTooltip, null, { trigger: () => node, default: () => text })
}
</script>

<style>
.version-cell {
  align-items: center;
  display: flex;
  gap: 8px;
}

.version-name {
  font-weight: 600;
}
</style>
