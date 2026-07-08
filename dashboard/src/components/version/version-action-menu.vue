<template>
  <div class="version-actions" :class="{ compact }">
    <n-button-group class="version-action-group">
      <n-button
        size="small"
        :disabled="!activeCheck.ok || version.version_status === 'active'"
        :title="activeCheck.ok ? undefined : activeCheck.reason"
        @click="$emit('set-version-status', version, 'active')"
      >
        标记为发布候选
      </n-button>
      <n-button
        size="small"
        :type="version.is_latest ? 'primary' : 'default'"
        :secondary="!version.is_latest"
        :disabled="latestBlockers.length > 0 || version.is_latest"
        :title="latestBlockers.join('；') || undefined"
        @click="$emit('set-latest', version)"
      >
        设为插件源当前版本
      </n-button>
      <n-button
        size="small"
        secondary
        :disabled="!version.download_url"
        :title="version.download_url ? undefined : '当前版本还没有可浏览的制品'"
        @click="$emit('browse-artifact', version)"
      >
        浏览文件
      </n-button>
    </n-button-group>

    <n-dropdown
      trigger="click"
      placement="bottom-end"
      :options="scanOptions"
      @select="handleScanAction"
    >
      <n-button size="small" secondary>扫描操作</n-button>
    </n-dropdown>

    <n-popconfirm
      positive-text="删除版本"
      negative-text="取消"
      @positive-click="$emit('delete-version', version)"
    >
      <template #trigger>
        <n-button size="small" type="error" secondary>删除版本</n-button>
      </template>
      将删除这个版本记录和对应构建制品；不会删除插件本身。
    </n-popconfirm>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NButtonGroup, NDropdown, NPopconfirm, type DropdownOption } from 'naive-ui'

import type { PluginDetail, VersionStatus, VersionSummary } from '@/api/types'
import { canActivateVersion, getVersionBlockers } from '@/composables/use-plugin-actions'
import { enabledScanActionProviders } from '@/utils/scans'

const props = withDefaults(
  defineProps<{
    plugin: PluginDetail
    version: VersionSummary
    compact?: boolean
  }>(),
  {
    compact: false,
  },
)

const emit = defineEmits<{
  (event: 'set-version-status', version: VersionSummary, status: VersionStatus): void
  (event: 'set-latest', version: VersionSummary): void
  (event: 'browse-artifact', version: VersionSummary): void
  (event: 'rescan', version: VersionSummary): void
  (event: 'run-scan-provider', version: VersionSummary, provider: string): void
  (event: 'skip-scan-provider', version: VersionSummary, provider: string): void
  (event: 'delete-version', version: VersionSummary): void
}>()

const activeCheck = computed(() => canActivateVersion(props.version))
const latestBlockers = computed(() => getVersionBlockers(props.plugin, props.version))
const scanOptions = computed<DropdownOption[]>(() => {
  const scanDisabled = !props.version.download_url || props.version.build_status === 'scanning'
  return [
    { label: '运行所有扫描', key: 'rescan', disabled: scanDisabled },
    { type: 'divider', key: 'scan-divider' },
    ...enabledScanActionProviders(props.version.scan).flatMap(({ provider, label }) => [
      { label: `${label} 扫描`, key: `${provider}:run`, disabled: scanDisabled },
      { label: `${label} 跳过`, key: `${provider}:skip` },
    ]),
  ]
})

function handleScanAction(key: string) {
  if (key === 'rescan') {
    emit('rescan', props.version)
    return
  }
  const [provider, action] = key.split(':', 2)
  if (provider && action === 'run') emit('run-scan-provider', props.version, provider)
  if (provider && action === 'skip') emit('skip-scan-provider', props.version, provider)
}
</script>

<style scoped>
.version-actions {
  align-items: flex-end;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.version-actions.compact {
  align-items: center;
  border-top: 1px solid var(--divider);
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 12px;
}

.version-action-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  row-gap: 4px;
}

.version-actions :deep(.n-button) {
  flex: 0 1 auto;
  max-width: 100%;
}

.version-actions :deep(.n-button__content) {
  min-width: 0;
  white-space: normal;
}
</style>
