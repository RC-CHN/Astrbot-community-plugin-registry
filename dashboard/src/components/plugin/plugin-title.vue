<template>
  <div class="plugin-title">
    <div class="name">{{ plugin.display_name || plugin.plugin_key }}</div>
    <div class="key">{{ plugin.plugin_key }}</div>
  </div>
</template>

<script setup lang="ts">
import type { PluginSummary } from '@/api/types'

defineProps<{
  plugin: Pick<PluginSummary, 'display_name' | 'plugin_key'>
}>()
</script>

<style scoped>
.plugin-title {
  min-width: 0;
}

.name {
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.key {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
