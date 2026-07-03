<template>
  <n-tag :type="meta.type" size="small" round>
    {{ meta.label }}
  </n-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { BuildStatus, PluginStatus, VersionStatus } from '@/api/types'
import {
  getBuildStatusMeta,
  getPluginStatusMeta,
  getVersionStatusMeta,
} from '@/composables/use-status-meta'
import { scanStatusMeta } from '@/constants/status'

const props = defineProps<{
  kind: 'plugin' | 'version' | 'build' | 'scan'
  value: PluginStatus | VersionStatus | BuildStatus | boolean | null | undefined
}>()

const meta = computed(() => {
  if (props.kind === 'plugin') return getPluginStatusMeta(props.value as PluginStatus)
  if (props.kind === 'version') return getVersionStatusMeta(props.value as VersionStatus)
  if (props.kind === 'build') return getBuildStatusMeta(props.value as BuildStatus)
  return scanStatusMeta(props.value as boolean | null | undefined)
})
</script>
