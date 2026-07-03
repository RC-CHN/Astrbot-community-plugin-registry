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
import { computed, h, type VNodeChild } from 'vue'
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
  rescan: [version: VersionSummary]
  runScanProvider: [version: VersionSummary, provider: 'virustotal' | 'llm_agent']
  skipScanProvider: [version: VersionSummary, provider: 'virustotal' | 'llm_agent']
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
    width: 110,
    render(row) {
      const meta = getScanAggregateMeta(row.scan)
      return withTooltip(
        h(NTag, { type: meta.type, size: 'small', round: true }, { default: () => meta.label }),
        scanTooltip(row),
      )
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
    width: 360,
    render(row) {
      const activeCheck = canActivateVersion(row)
      const latestBlockers = getVersionBlockers(props.plugin, row)
      const scanButton = h(
        NButton,
        {
          size: 'small',
          disabled: !row.download_url || row.build_status === 'scanning',
          onClick: () => emit('rescan', row),
        },
        { default: () => '全量扫描' },
      )
      const vtScanButton = h(
        NButton,
        {
          size: 'small',
          disabled: !row.download_url || row.build_status === 'scanning',
          onClick: () => emit('runScanProvider', row, 'virustotal'),
        },
        { default: () => 'VT扫描' },
      )
      const vtSkipButton = h(
        NButton,
        {
          size: 'small',
          secondary: true,
          onClick: () => emit('skipScanProvider', row, 'virustotal'),
        },
        { default: () => 'VT跳过' },
      )
      const llmScanButton = h(
        NButton,
        {
          size: 'small',
          disabled: !row.download_url || row.build_status === 'scanning',
          onClick: () => emit('runScanProvider', row, 'llm_agent'),
        },
        { default: () => 'LLM扫描' },
      )
      const llmSkipButton = h(
        NButton,
        {
          size: 'small',
          secondary: true,
          onClick: () => emit('skipScanProvider', row, 'llm_agent'),
        },
        { default: () => 'LLM跳过' },
      )
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
      return h('div', { class: 'version-actions' }, [
        h(NButtonGroup, null, {
          default: () => [
            activeCheck.ok ? activeButton : withTooltip(activeButton, activeCheck.reason),
            latestBlockers.length ? withTooltip(latestButton, latestBlockers.join('；')) : latestButton,
          ],
        }),
        h(NButtonGroup, null, {
          default: () => [
            !row.download_url ? withTooltip(scanButton, '没有可扫描的构建产物') : scanButton,
            !row.download_url ? withTooltip(vtScanButton, '没有可扫描的构建产物') : vtScanButton,
            vtSkipButton,
            !row.download_url ? withTooltip(llmScanButton, '没有可扫描的构建产物') : llmScanButton,
            llmSkipButton,
          ],
        }),
      ])
    },
  },
])

function withTooltip(node: ReturnType<typeof h>, content: VNodeChild) {
  return h(NTooltip, null, { trigger: () => node, default: () => content })
}

function scanTooltip(row: VersionSummary) {
  if (!row.scan) return '尚未扫描'
  const vt = row.scan.virustotal
  const llm = row.scan.llm_agent
  return h('div', { class: 'scan-tooltip' }, [
    h('div', { class: 'scan-tooltip-row' }, [
      h('strong', null, 'VirusTotal'),
      h('span', null, `${modeLabel(vt.mode)} / ${passLabel(vt.pass)}`),
      vt.msg ? h('span', { class: 'scan-tooltip-msg' }, vt.msg) : null,
    ]),
    h('div', { class: 'scan-tooltip-row' }, [
      h('strong', null, 'LLM Agent'),
      h('span', null, `${modeLabel(llm.mode)} / ${passLabel(llm.pass)}`),
      llm.msg ? h('span', { class: 'scan-tooltip-msg' }, llm.msg) : null,
    ]),
  ])
}

function modeLabel(mode: string) {
  const labels: Record<string, string> = {
    pending: '等待中',
    real: '真实扫描',
    skipped: '已略过',
    error: '扫描错误',
  }
  return labels[mode] || mode
}

function passLabel(value: boolean | null) {
  if (value === true) return '通过'
  if (value === false) return '未通过'
  return '无结果'
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

.version-actions {
  align-items: flex-end;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scan-tooltip {
  display: grid;
  gap: 8px;
  max-width: 520px;
  white-space: normal;
}

.scan-tooltip-row {
  display: grid;
  gap: 3px;
}

.scan-tooltip-msg {
  line-height: 1.45;
  overflow-wrap: anywhere;
}
</style>
