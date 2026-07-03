<template>
  <page-header title="统计" description="插件源公开数据概览" />
  <api-error-alert :error="query.error.value" />
  <n-grid :cols="4" :x-gap="16" :y-gap="16">
    <n-gi v-for="item in metrics" :key="item.label">
      <div class="metric">
        <div class="muted">{{ item.label }}</div>
        <strong>{{ item.value }}</strong>
      </div>
    </n-gi>
  </n-grid>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import { useRegistryStats } from '@/query/stats'

const query = useRegistryStats()
const metrics = computed(() => [
  { label: '总插件', value: query.data.value?.total_plugins ?? '-' },
  { label: '活跃版本', value: query.data.value?.total_active_versions ?? '-' },
  { label: '下载量', value: query.data.value?.total_downloads ?? '-' },
  { label: '安装量', value: query.data.value?.total_installs ?? '-' },
])
</script>

<style scoped>
.metric {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow-sm);
  padding: 16px;
}

.metric strong {
  display: block;
  font-size: 28px;
  line-height: 36px;
  margin-top: 8px;
}
</style>
