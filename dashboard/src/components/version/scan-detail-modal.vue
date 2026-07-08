<template>
  <n-modal
    :show="show"
    preset="card"
    title="扫描详情"
    class="scan-detail-modal"
    :bordered="false"
    :style="{ width: 'min(1120px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="version">
      <div class="scan-detail-page">
        <header class="scan-detail-header">
          <div>
            <div class="scan-detail-title">版本 {{ version.version }}</div>
            <div class="scan-detail-subtitle">
              <span>{{ version.source_type }}</span>
              <span v-if="version.source_ref">ref: {{ version.source_ref }}</span>
              <span v-if="version.commit_sha">{{ version.commit_sha.slice(0, 12) }}</span>
              <span v-if="version.scan?.scanned_at">更新于 {{ formatDateTime(version.scan.scanned_at) }}</span>
            </div>
          </div>
          <n-tag :type="aggregateMeta.type" round>{{ aggregateMeta.label }}</n-tag>
        </header>

        <empty-state v-if="!entries.length" description="当前版本还没有扫描结果" />

        <div v-else class="scan-detail-layout">
          <aside class="scan-provider-nav" aria-label="扫描提供方">
            <button
              v-for="entry in entries"
              :key="entry.provider"
              type="button"
              class="scan-provider-nav-item"
              :class="{ active: entry.provider === activeProvider }"
              @click="activeProvider = entry.provider"
            >
              <span class="scan-provider-nav-head">
                <strong>{{ providerLabel(entry.provider) }}</strong>
                <n-tag :type="scanResultMeta(entry.result).type" size="small" round>
                  {{ scanResultMeta(entry.result).label }}
                </n-tag>
              </span>
              <span class="scan-provider-nav-meta">
                {{ modeLabel(entry.result.mode) }} · {{ passLabel(entry.result.pass, entry.result.mode) }}
              </span>
              <span class="scan-provider-nav-preview">{{ scanMessagePreview(entry.result) }}</span>
            </button>
          </aside>

          <section v-if="activeEntry" class="scan-provider-panel">
            <header class="scan-provider-panel-head">
              <div>
                <h3>{{ providerLabel(activeEntry.provider) }}</h3>
                <p>{{ modeLabel(activeEntry.result.mode) }} · {{ passLabel(activeEntry.result.pass, activeEntry.result.mode) }}</p>
              </div>
              <n-tag :type="scanResultMeta(activeEntry.result).type" round>
                {{ scanResultMeta(activeEntry.result).label }}
              </n-tag>
            </header>

            <div v-if="parsedMessage?.kind === 'json'" class="scan-report">
              <n-alert v-if="parsedMessage.summary" type="default" :bordered="false">
                {{ parsedMessage.summary }}
              </n-alert>
              <dl class="scan-report-meta">
                <div v-if="parsedMessage.riskLevel">
                  <dt>风险级别</dt>
                  <dd>{{ parsedMessage.riskLevel }}</dd>
                </div>
                <div v-if="parsedMessage.contextTruncated !== null">
                  <dt>上下文截断</dt>
                  <dd>{{ parsedMessage.contextTruncated ? '是' : '否' }}</dd>
                </div>
              </dl>

              <section v-if="parsedMessage.findings.length" class="scan-findings">
                <h4>发现项</h4>
                <article
                  v-for="(finding, index) in parsedMessage.findings"
                  :key="index"
                  class="scan-finding"
                >
                  <header>
                    <n-tag v-if="finding.severity" size="small" round>{{ finding.severity }}</n-tag>
                    <n-tag v-if="finding.category" size="small" round>{{ finding.category }}</n-tag>
                    <span v-if="finding.file" class="scan-finding-file">{{ finding.file }}</span>
                  </header>
                  <p v-if="finding.reason">{{ finding.reason }}</p>
                  <p v-if="finding.recommendation" class="scan-recommendation">
                    建议：{{ finding.recommendation }}
                  </p>
                  <pre v-if="!finding.reason && !finding.recommendation">{{ JSON.stringify(finding.raw, null, 2) }}</pre>
                </article>
              </section>
            </div>

            <div v-else-if="parsedMessage?.kind === 'metrics'" class="scan-report">
              <n-alert type="default" :bordered="false">{{ parsedMessage.title }}</n-alert>
              <div class="scan-metrics">
                <div v-for="metric in parsedMessage.metrics" :key="metric.label" class="scan-metric">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.value }}</strong>
                </div>
              </div>
            </div>

            <n-alert v-else-if="parsedMessage?.kind === 'text'" type="default" :bordered="false">
              {{ parsedMessage.text }}
            </n-alert>

            <n-alert v-else type="default" :bordered="false">该 provider 没有返回详细消息。</n-alert>

            <n-collapse v-if="activeEntry.result.msg" class="scan-raw-collapse">
              <n-collapse-item title="原始消息" name="raw">
                <pre class="scan-raw-message">{{ formatRawScanMessage(activeEntry.result.msg) }}</pre>
              </n-collapse-item>
            </n-collapse>
          </section>
        </div>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { VersionSummary } from '@/api/types'
import EmptyState from '@/components/common/empty-state.vue'
import { getScanAggregateMeta } from '@/composables/use-status-meta'
import { formatDateTime } from '@/utils/datetime'
import {
  formatRawScanMessage,
  modeLabel,
  parseScanMessage,
  passLabel,
  providerLabel,
  scanMessagePreview,
  scanProviderEntries,
  scanResultMeta,
} from '@/utils/scans'

const props = defineProps<{
  show: boolean
  version: VersionSummary | null
}>()

const emit = defineEmits<{ 'update:show': [value: boolean] }>()

const entries = computed(() => scanProviderEntries(props.version?.scan || null))
const aggregateMeta = computed(() => getScanAggregateMeta(props.version?.scan || null))
const activeProvider = ref('')
const activeEntry = computed(() => entries.value.find((entry) => entry.provider === activeProvider.value) || entries.value[0])
const parsedMessage = computed(() => parseScanMessage(activeEntry.value?.result.msg || null))

watch(
  entries,
  (next) => {
    if (!next.length) {
      activeProvider.value = ''
      return
    }
    if (!next.some((entry) => entry.provider === activeProvider.value)) {
      activeProvider.value = next[0].provider
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.scan-detail-page {
  display: grid;
  gap: 18px;
}

.scan-detail-header {
  align-items: flex-start;
  border-bottom: 1px solid var(--divider);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding-bottom: 14px;
}

.scan-detail-title {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
}

.scan-detail-subtitle {
  color: var(--text-secondary);
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 5px;
}

.scan-detail-layout {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  min-height: 0;
}

.scan-provider-nav {
  border-right: 1px solid var(--divider);
  display: grid;
  gap: 8px;
  max-height: min(66vh, 720px);
  overflow-y: auto;
  padding-right: 14px;
}

.scan-provider-nav-item {
  background: transparent;
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  color: var(--text-primary);
  cursor: pointer;
  display: grid;
  gap: 6px;
  padding: 12px;
  text-align: left;
}

.scan-provider-nav-item.active,
.scan-provider-nav-item:hover {
  background: var(--surface-hover);
  border-color: var(--border);
}

.scan-provider-nav-head {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.scan-provider-nav-meta,
.scan-provider-nav-preview {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.scan-provider-nav-preview {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.scan-provider-panel {
  display: grid;
  gap: 16px;
  max-height: min(66vh, 720px);
  min-width: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.scan-provider-panel-head {
  align-items: flex-start;
  display: flex;
  gap: 16px;
  justify-content: space-between;
}

.scan-provider-panel-head h3 {
  font-size: 18px;
  margin: 0;
}

.scan-provider-panel-head p {
  color: var(--text-secondary);
  margin: 4px 0 0;
}

.scan-report {
  display: grid;
  gap: 14px;
}

.scan-report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0;
}

.scan-report-meta div,
.scan-metric {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  min-width: 140px;
  padding: 10px 12px;
}

.scan-report-meta dt,
.scan-metric span {
  color: var(--text-secondary);
  font-size: 12px;
}

.scan-report-meta dd,
.scan-metric strong {
  color: var(--text-primary);
  display: block;
  font-size: 15px;
  font-weight: 600;
  margin: 3px 0 0;
}

.scan-metrics {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}

.scan-findings {
  display: grid;
  gap: 10px;
}

.scan-findings h4 {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0;
}

.scan-finding {
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  padding: 12px;
}

.scan-finding header {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.scan-finding p {
  line-height: 1.55;
  margin: 0;
  overflow-wrap: anywhere;
}

.scan-finding pre,
.scan-raw-message {
  background: #0f172a;
  border-radius: 8px;
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
  max-height: 360px;
  overflow: auto;
  padding: 12px;
  white-space: pre-wrap;
}

.scan-finding-file,
.scan-recommendation {
  color: var(--text-secondary);
}

.scan-raw-collapse {
  border-top: 1px solid var(--divider);
  padding-top: 4px;
}

@media (max-width: 860px) {
  .scan-detail-layout {
    grid-template-columns: 1fr;
  }

  .scan-provider-nav {
    border-right: 0;
    border-bottom: 1px solid var(--divider);
    max-height: 220px;
    padding: 0 0 14px;
  }
}
</style>
