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
import {
  NButton,
  NButtonGroup,
  NDropdown,
  NTag,
  NTooltip,
  type DataTableColumns,
  type DropdownOption,
} from 'naive-ui'

import type { PluginDetail, VersionStatus, VersionSummary } from '@/api/types'
import CopyableText from '@/components/common/copyable-text.vue'
import StatusTag from '@/components/common/status-tag.vue'
import ScanDetailModal from '@/components/version/scan-detail-modal.vue'
import { canActivateVersion, getVersionBlockers } from '@/composables/use-plugin-actions'
import { getScanAggregateMeta } from '@/composables/use-status-meta'
import { formatDateTime } from '@/utils/datetime'
import { formatFileSize } from '@/utils/file-size'
import { providerLabel, scanProviderEntries, scanResultMeta } from '@/utils/scans'

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
}>()

const rowKey = (row: VersionSummary) => row.id
const scanDetailVisible = ref(false)
const scanDetailVersion = ref<VersionSummary | null>(null)
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
      const entries = scanProviderEntries(row.scan)
      return h('div', { class: 'scan-cell' }, [
        h(NTag, { type: meta.type, size: 'small', round: true }, { default: () => meta.label }),
        ...entries.map(({ provider, result }) =>
          h(
            'button',
            {
              class: 'scan-provider-chip',
              type: 'button',
              title: `查看 ${providerLabel(provider)} 扫描详情`,
              onClick: () => openScanDetail(row),
            },
            [
              h(
                NTag,
                { type: scanResultMeta(result).type, size: 'small', round: true, bordered: false },
                { default: () => providerLabel(provider) },
              ),
            ],
          ),
        ),
        entries.length
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, onClick: () => openScanDetail(row) },
              { default: () => '详情' },
            )
          : null,
      ])
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
      const browseButton = h(
        NButton,
        {
          size: 'small',
          secondary: true,
          disabled: !row.download_url,
          onClick: () => emit('browseArtifact', row),
        },
        { default: () => '浏览文件' },
      )
      const scanDisabled = !row.download_url || row.build_status === 'scanning'
      const scanOptions: DropdownOption[] = [
        { label: '运行启用扫描', key: 'rescan', disabled: scanDisabled },
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
            row.download_url ? browseButton : withTooltip(browseButton, '当前版本还没有可浏览的制品'),
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

function openScanDetail(version: VersionSummary) {
  scanDetailVersion.value = version
  scanDetailVisible.value = true
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

.scan-provider-chip {
  background: transparent;
  border: 0;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}
</style>
