<template>
  <div class="version-scan-summary" :class="{ compact }">
    <span v-if="label" class="scan-label">{{ label }}</span>
    <div class="scan-tags">
      <n-tag :type="aggregateMeta.type" size="small" round>
        {{ aggregateMeta.label }}
      </n-tag>
      <button
        v-for="entry in entries"
        :key="entry.provider"
        class="scan-chip-button"
        type="button"
        :title="`查看 ${providerLabel(entry.provider)} 扫描详情`"
        @click="$emit('show-detail')"
      >
        <n-tag :type="scanResultMeta(entry.result).type" size="small" round bordered>
          {{ providerLabel(entry.provider) }}
        </n-tag>
      </button>
      <n-tag v-if="humanReviewStatus" :type="humanMeta.type" size="small" round bordered>
        人工 {{ humanMeta.label }}
      </n-tag>
      <n-button v-if="entries.length" size="tiny" secondary @click="$emit('show-detail')">
        详情
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NTag } from 'naive-ui'

import type { ScanSummary } from '@/api/types'
import { getScanAggregateMeta } from '@/composables/use-status-meta'
import { humanReviewMeta } from '@/utils/review'
import { providerLabel, scanProviderEntries, scanResultMeta } from '@/utils/scans'

const props = withDefaults(
  defineProps<{
    scan: ScanSummary | null
    humanReviewStatus?: string
    label?: string
    compact?: boolean
  }>(),
  {
    humanReviewStatus: '',
    label: '',
    compact: false,
  },
)

defineEmits<{
  (event: 'show-detail'): void
}>()

const aggregateMeta = computed(() => getScanAggregateMeta(props.scan))
const entries = computed(() => scanProviderEntries(props.scan))
const humanMeta = computed(() => humanReviewMeta(props.humanReviewStatus))
</script>

<style scoped>
.version-scan-summary {
  align-items: flex-start;
  display: grid;
  gap: 8px;
  grid-template-columns: 42px minmax(0, 1fr);
  min-width: 0;
}

.version-scan-summary.compact {
  display: block;
}

.scan-label {
  color: var(--text-secondary);
  font-size: 12px;
}

.scan-tags {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.version-scan-summary.compact .scan-tags {
  gap: 4px;
}

.scan-chip-button {
  background: transparent;
  border: 0;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}
</style>
