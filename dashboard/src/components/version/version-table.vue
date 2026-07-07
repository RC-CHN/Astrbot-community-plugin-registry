<template>
  <n-data-table
    :columns="columns"
    :data="versions"
    :pagination="false"
    :row-key="rowKey"
    :scroll-x="1240"
    size="small"
  />
</template>

<script setup lang="ts">
import { computed, h, type VNodeChild } from 'vue'
import {
  NButton,
  NButtonGroup,
  NDropdown,
  NTag,
  NTooltip,
  type DataTableColumns,
  type DropdownOption,
} from 'naive-ui'

import type { PluginDetail, ScanProviderResult, VersionStatus, VersionSummary } from '@/api/types'
import CopyableText from '@/components/common/copyable-text.vue'
import StatusTag from '@/components/common/status-tag.vue'
import { canActivateVersion, getVersionBlockers } from '@/composables/use-plugin-actions'
import { getScanAggregateMeta } from '@/composables/use-status-meta'
import { formatDateTime } from '@/utils/datetime'
import { formatFileSize } from '@/utils/file-size'
import { providerLabel, scanProviderEntries } from '@/utils/scans'

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
}>()

const rowKey = (row: VersionSummary) => row.id
const SCAN_ACTION_PROVIDERS = [
  { provider: 'clamav', label: 'ClamAV' },
  { provider: 'virustotal', label: 'VirusTotal' },
  { provider: 'llm_agent', label: 'LLM' },
]

const columns = computed<DataTableColumns<VersionSummary>>(() => [
  {
    title: '版本',
    key: 'version',
    render(row) {
      return h('div', { class: 'version-cell' }, [
        h('div', { class: 'version-name' }, row.version),
        row.is_latest
          ? h(NTag, { type: 'success', size: 'small', round: true }, { default: () => '当前公开版本' })
          : null,
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
    width: 220,
    render(row) {
      const meta = getScanAggregateMeta(row.scan)
      return withTooltip(
        h('div', { class: 'scan-cell' }, [
          h(NTag, { type: meta.type, size: 'small', round: true }, { default: () => meta.label }),
          ...scanProviderEntries(row.scan).map(({ provider, result }) =>
            h(
              NTag,
              { type: scanResultMeta(result).type, size: 'small', round: true, bordered: false },
              { default: () => providerLabel(provider) },
            ),
          ),
        ]),
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
    width: 250,
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
        { default: () => '标记可发布' },
      )
      const latestButton = h(
        NButton,
        {
          size: 'small',
          type: row.is_latest ? 'primary' : 'default',
          disabled: latestBlockers.length > 0 || row.is_latest,
          onClick: () => emit('setLatest', row),
        },
        { default: () => '设为公开版本' },
      )
      const scanDisabled = !row.download_url || row.build_status === 'scanning'
      const scanOptions: DropdownOption[] = [
        { label: '全量扫描', key: 'rescan', disabled: scanDisabled },
        { type: 'divider', key: 'scan-divider' },
        ...SCAN_ACTION_PROVIDERS.flatMap(({ provider, label }) => [
          { label: `${label} 扫描`, key: `${provider}:run`, disabled: scanDisabled },
          { label: `${label} 跳过`, key: `${provider}:skip` },
        ]),
      ]
      return h('div', { class: 'version-actions' }, [
        h(NButtonGroup, { class: 'version-action-group' }, {
          default: () => [
            activeCheck.ok ? activeButton : withTooltip(activeButton, activeCheck.reason),
            latestBlockers.length ? withTooltip(latestButton, latestBlockers.join('；')) : latestButton,
          ],
        }),
        h(
          NDropdown,
          {
            options: scanOptions,
            trigger: 'click',
            placement: 'bottom-end',
            onSelect: (key: string) => {
              if (key === 'rescan') {
                emit('rescan', row)
                return
              }
              const [provider, action] = key.split(':', 2)
              if (provider && action === 'run') emit('runScanProvider', row, provider)
              if (provider && action === 'skip') emit('skipScanProvider', row, provider)
            },
          },
          { default: () => h(NButton, { size: 'small', secondary: true }, { default: () => '扫描操作' }) },
        ),
      ])
    },
  },
])

function withTooltip(node: ReturnType<typeof h>, content: VNodeChild) {
  return h(NTooltip, null, { trigger: () => node, default: () => content })
}

function scanTooltip(row: VersionSummary) {
  const entries = scanProviderEntries(row.scan)
  if (!entries.length) return '尚未扫描'
  return h('div', { class: 'scan-tooltip' }, entries.map(({ provider, result }) => {
    const meta = scanResultMeta(result)
    return h('div', { class: 'scan-tooltip-row' }, [
      h('div', { class: 'scan-tooltip-heading' }, [
        h('strong', null, providerLabel(provider)),
        h(NTag, { type: meta.type, size: 'small', round: true }, { default: () => meta.label }),
      ]),
      h('div', { class: 'scan-tooltip-meta' }, [
        h('span', null, modeLabel(result.mode)),
        h('span', null, passLabel(result.pass, result.mode)),
      ]),
      result.msg ? h('div', { class: 'scan-tooltip-msg' }, formatScanMessage(result.msg)) : null,
    ])
  }))
}

function scanResultMeta(result: ScanProviderResult) {
  if (result.mode === 'pending') return { label: '扫描中', type: 'info' as const }
  if (result.mode === 'skipped') return { label: '已略过', type: 'warning' as const }
  if (result.mode === 'error' || result.pass === false) return { label: '未通过', type: 'error' as const }
  if (result.pass === true) return { label: '通过', type: 'success' as const }
  return { label: '无结果', type: 'default' as const }
}

function formatScanMessage(message: string): string | VNodeChild[] {
  const parsed = parseJsonMessage(message)
  if (!parsed) return message

  const rows: VNodeChild[] = []
  if (typeof parsed.summary === 'string' && parsed.summary) rows.push(h('div', null, parsed.summary))
  if (typeof parsed.risk_level === 'string' && parsed.risk_level) {
    rows.push(h('div', null, `risk_level: ${parsed.risk_level}`))
  }
  if (typeof parsed.context_truncated === 'boolean') {
    rows.push(h('div', null, `context_truncated: ${parsed.context_truncated}`))
  }
  if (Array.isArray(parsed.findings) && parsed.findings.length) {
    rows.push(
      h('ul', { class: 'scan-tooltip-findings' }, parsed.findings.slice(0, 5).map((finding: unknown) =>
        h('li', null, typeof finding === 'string' ? finding : JSON.stringify(finding)),
      )),
    )
  }
  return rows.length ? rows : JSON.stringify(parsed)
}

function parseJsonMessage(message: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(message)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
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

function passLabel(value: boolean | null, mode: string) {
  if (mode === 'pending') return '等待结果'
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
  min-width: 0;
}

.version-action-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  row-gap: 4px;
}

.scan-cell {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-width: 210px;
}

.scan-tooltip {
  display: grid;
  gap: 10px;
  max-width: 640px;
  white-space: normal;
}

.scan-tooltip-row {
  display: grid;
  gap: 5px;
}

.scan-tooltip-heading {
  align-items: center;
  display: flex;
  gap: 8px;
}

.scan-tooltip-meta {
  color: #64748b;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
}

.scan-tooltip-msg {
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.scan-tooltip-findings {
  margin: 4px 0 0;
  padding-left: 18px;
}
</style>
