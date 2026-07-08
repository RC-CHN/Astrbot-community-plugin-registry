<template>
  <article class="version-summary-card">
    <header class="version-head">
      <div class="version-title-group">
        <strong>{{ version.version }}</strong>
        <n-tag v-if="version.is_latest" type="success" size="small" round>插件源当前版本</n-tag>
      </div>
      <n-space size="small">
        <status-tag kind="build" :value="version.build_status" />
        <status-tag kind="version" :value="version.version_status" />
      </n-space>
    </header>

    <div class="version-meta">
      <div>
        <span>来源</span>
        <strong>{{ version.source_type }}</strong>
        <small v-if="version.source_ref">构建 ref: {{ version.source_ref }}</small>
      </div>
      <div>
        <span>制品 Commit</span>
        <copyable-text :value="version.commit_sha" :max="24" />
      </div>
      <div>
        <span>大小</span>
        <strong>{{ formatFileSize(version.file_size) }}</strong>
      </div>
      <div>
        <span>创建时间</span>
        <strong>{{ formatDateTime(version.created_at) }}</strong>
      </div>
    </div>

    <version-scan-summary
      :scan="version.scan"
      :human-review-status="reviewStatus"
      label="扫描"
      @show-detail="emit('show-scan-detail', version)"
    />

    <version-action-menu
      :plugin="plugin"
      :version="version"
      compact
      @set-version-status="emitSetVersionStatus"
      @set-latest="emit('set-latest', $event)"
      @browse-artifact="emit('browse-artifact', $event)"
      @rescan="emit('rescan', $event)"
      @run-scan-provider="emitRunScanProvider"
      @skip-scan-provider="emitSkipScanProvider"
    />
  </article>
</template>

<script setup lang="ts">
import { NSpace, NTag } from 'naive-ui'

import type { PluginDetail, VersionStatus, VersionSummary } from '@/api/types'
import CopyableText from '@/components/common/copyable-text.vue'
import StatusTag from '@/components/common/status-tag.vue'
import VersionActionMenu from '@/components/version/version-action-menu.vue'
import VersionScanSummary from '@/components/version/version-scan-summary.vue'
import { formatDateTime } from '@/utils/datetime'
import { formatFileSize } from '@/utils/file-size'

defineProps<{
  plugin: PluginDetail
  version: VersionSummary
  reviewStatus: string
}>()

const emit = defineEmits<{
  (event: 'show-scan-detail', version: VersionSummary): void
  (event: 'set-version-status', version: VersionSummary, status: VersionStatus): void
  (event: 'set-latest', version: VersionSummary): void
  (event: 'browse-artifact', version: VersionSummary): void
  (event: 'rescan', version: VersionSummary): void
  (event: 'run-scan-provider', version: VersionSummary, provider: string): void
  (event: 'skip-scan-provider', version: VersionSummary, provider: string): void
}>()

function emitSetVersionStatus(version: VersionSummary, status: VersionStatus) {
  emit('set-version-status', version, status)
}

function emitRunScanProvider(version: VersionSummary, provider: string) {
  emit('run-scan-provider', version, provider)
}

function emitSkipScanProvider(version: VersionSummary, provider: string) {
  emit('skip-scan-provider', version, provider)
}
</script>

<style scoped>
.version-summary-card {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  display: grid;
  gap: 14px;
  min-width: 0;
  padding: 14px;
}

.version-head {
  align-items: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
  min-width: 0;
}

.version-title-group {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.version-title-group strong {
  font-size: 16px;
  overflow-wrap: anywhere;
}

.version-meta {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr));
  min-width: 0;
}

.version-meta > div {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
}

.version-meta span {
  color: var(--text-secondary);
  font-size: 12px;
}

.version-meta strong {
  font-size: 13px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.version-meta small {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.35;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
