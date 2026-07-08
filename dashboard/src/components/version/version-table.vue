<template>
  <div>
    <n-data-table
      :columns="columns"
      :data="versions"
      :pagination="false"
      :row-key="rowKey"
      :scroll-x="1240"
      size="small"
    />
    <scan-detail-modal v-model:show="scanDetailVisible" :version="scanDetailVersion" />
  </div>
</template>

<script setup lang="ts">
import { computed, h, ref, type VNodeChild } from 'vue'
import { NTag, NTooltip, type DataTableColumns } from 'naive-ui'

import type { PluginDetail, VersionStatus, VersionSummary } from '@/api/types'
import CopyableText from '@/components/common/copyable-text.vue'
import StatusTag from '@/components/common/status-tag.vue'
import ScanDetailModal from '@/components/version/scan-detail-modal.vue'
import VersionActionMenu from '@/components/version/version-action-menu.vue'
import VersionScanSummary from '@/components/version/version-scan-summary.vue'
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
  rescan: [version: VersionSummary]
  runScanProvider: [version: VersionSummary, provider: string]
  skipScanProvider: [version: VersionSummary, provider: string]
  browseArtifact: [version: VersionSummary]
  deleteVersion: [version: VersionSummary]
}>()

const rowKey = (row: VersionSummary) => row.id
const scanDetailVisible = ref(false)
const scanDetailVersion = ref<VersionSummary | null>(null)

const columns = computed<DataTableColumns<VersionSummary>>(() => [
  {
    title: '版本号',
    key: 'version',
    render(row) {
      return h('div', { class: 'version-cell' }, [
        h('div', { class: 'version-name-group' }, [
          h('div', { class: 'version-name' }, row.version),
          h('div', { class: 'version-note' }, '来自 metadata.yaml，可重复'),
        ]),
        row.is_latest
          ? h(NTag, { type: 'success', size: 'small', round: true }, { default: () => '插件源当前版本' })
          : null,
      ])
    },
  },
  {
    title: '来源',
    key: 'source_type',
    width: 150,
    render(row) {
      return h('div', { class: 'source-cell' }, [
        h('strong', row.source_type),
        row.source_ref ? h('span', { class: 'source-ref' }, `构建 ref: ${row.source_ref}`) : null,
      ])
    },
  },
  {
    title: '制品 Commit',
    key: 'commit_sha',
    width: 170,
    render: (row) => h(CopyableText, { value: row.commit_sha }),
  },
  {
    title: '构建',
    key: 'build_status',
    width: 110,
    render(row) {
      const node = h(StatusTag, { kind: 'build', value: row.build_status })
      return row.build_log ? withTooltip(node, row.build_log) : node
    },
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
    width: 220,
    render(row) {
      return h(VersionScanSummary, {
        scan: row.scan,
        compact: true,
        onShowDetail: () => openScanDetail(row),
      })
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
    width: 250,
    render(row) {
      return h(VersionActionMenu, {
        plugin: props.plugin,
        version: row,
        onSetVersionStatus: (version: VersionSummary, status: VersionStatus) =>
          emit('setVersionStatus', version, status),
        onSetLatest: (version: VersionSummary) => emit('setLatest', version),
        onBrowseArtifact: (version: VersionSummary) => emit('browseArtifact', version),
        onRescan: (version: VersionSummary) => emit('rescan', version),
        onRunScanProvider: (version: VersionSummary, provider: string) =>
          emit('runScanProvider', version, provider),
        onSkipScanProvider: (version: VersionSummary, provider: string) =>
          emit('skipScanProvider', version, provider),
        onDeleteVersion: (version: VersionSummary) => emit('deleteVersion', version),
      })
    },
  },
])

function withTooltip(node: ReturnType<typeof h>, content: VNodeChild) {
  return h(NTooltip, null, { trigger: () => node, default: () => content })
}

function openScanDetail(version: VersionSummary) {
  scanDetailVersion.value = version
  scanDetailVisible.value = true
}
</script>

<style>
.version-cell {
  align-items: flex-start;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.version-name {
  font-weight: 600;
}

.version-name-group,
.source-cell {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.version-note,
.source-ref {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-cell strong {
  color: var(--text-main);
  font-size: 13px;
}
</style>
