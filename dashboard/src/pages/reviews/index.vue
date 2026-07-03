<template>
  <page-header title="待审核" description="快速处理待审核插件并发布最新版本" />

  <api-error-alert :error="pendingQuery.error.value || detailQuery.error.value || actionError" />
  <div class="review-layout">
    <aside class="review-list">
      <n-spin :show="pendingQuery.isLoading.value">
        <button
          v-for="plugin in pendingQuery.data.value || []"
          :key="plugin.id"
          class="review-item"
          :class="{ active: plugin.id === selectedId }"
          @click="selectedId = plugin.id"
        >
          <plugin-title :plugin="plugin" />
          <status-tag kind="plugin" :value="plugin.status" />
        </button>
        <empty-state
          v-if="!pendingQuery.isLoading.value && !(pendingQuery.data.value || []).length"
          description="暂无待审核插件"
        />
      </n-spin>
    </aside>

    <main class="workbench">
      <template v-if="plugin">
        <div class="workbench-header">
          <plugin-title :plugin="plugin" />
          <n-space size="small">
            <status-tag kind="plugin" :value="plugin.status" />
            <n-tag size="small" round>{{ reviewStatusLabel(plugin.review_status) }}</n-tag>
          </n-space>
        </div>
        <dl class="meta">
          <dt>作者</dt>
          <dd>{{ plugin.author }}</dd>
          <dt>Repo</dt>
          <dd>
            <a
              v-if="plugin.repo_url"
              class="text-link"
              :href="plugin.repo_url"
              target="_blank"
              rel="noreferrer"
            >
              {{ plugin.repo_url }}
            </a>
          </dd>
          <dt>描述</dt>
          <dd>{{ plugin.description }}</dd>
        </dl>

        <publish-blocker-alert :blockers="blockers" />
        <version-table
          v-if="plugin.versions.length"
          :plugin="plugin"
          :versions="plugin.versions"
          @set-version-status="setVersionStatus"
          @set-latest="setLatest"
          @rescan="rescanVersion"
          @run-scan-provider="runScanProvider"
          @skip-scan-provider="skipScanProvider"
        />

        <div class="action-bar">
          <n-button @click="router.push(`/plugins/${plugin.id}`)">打开详情</n-button>
          <n-button :disabled="!plugin.versions.length" @click="approvePluginOnly">仅通过插件</n-button>
          <n-button type="primary" :disabled="blockers.length > 0" @click="approveAndPublish">
            通过并发布
          </n-button>
          <n-popconfirm
            positive-text="确认跳过"
            negative-text="取消"
            @positive-click="skipReviewAndPublish"
          >
            <template #trigger>
              <n-button type="warning" secondary :disabled="!plugin.versions.length">
                跳过审核并发布
              </n-button>
            </template>
            跳过人工审核会直接公开当前版本，请确认这个插件来源可信。
          </n-popconfirm>
          <n-button type="error" secondary @click="disablePlugin">禁用</n-button>
          <n-popconfirm
            positive-text="确认删除"
            negative-text="取消"
            @positive-click="deletePlugin"
          >
            <template #trigger>
              <n-button type="error" secondary>删除</n-button>
            </template>
            删除后插件和版本会从公开索引移除，确认继续？
          </n-popconfirm>
        </div>
      </template>
      <empty-state v-else description="请选择一个待审核插件" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import type { VersionStatus, VersionSummary } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import EmptyState from '@/components/common/empty-state.vue'
import PageHeader from '@/components/common/page-header.vue'
import StatusTag from '@/components/common/status-tag.vue'
import PluginTitle from '@/components/plugin/plugin-title.vue'
import PublishBlockerAlert from '@/components/review/publish-blocker-alert.vue'
import VersionTable from '@/components/version/version-table.vue'
import { getVersionBlockers } from '@/composables/use-plugin-actions'
import { usePendingPlugins, usePluginDetail, usePluginMutations } from '@/query/plugins'

const router = useRouter()
const message = useMessage()
const pendingQuery = usePendingPlugins()
const selectedId = ref('')
const detailQuery = usePluginDetail(selectedId)
const mutations = usePluginMutations()
const actionError = ref<unknown>(null)
const plugin = computed(() => detailQuery.data.value)
const candidate = computed(() => plugin.value?.versions[0])
const blockers = computed(() =>
  plugin.value && candidate.value
    ? getVersionBlockers(plugin.value, candidate.value, { includePluginStatus: false })
    : [],
)

watch(
  () => pendingQuery.data.value,
  (items) => {
    if (!selectedId.value && items?.length) selectedId.value = items[0].id
  },
  { immediate: true },
)

async function approvePluginOnly() {
  if (!plugin.value) return
  await runAction(() => mutations.updatePluginStatus.mutateAsync({ pluginId: plugin.value!.id, status: 'active' }))
}

async function approveAndPublish() {
  if (!plugin.value || !candidate.value) return
  await runAction(async () => {
    await mutations.updatePluginReviewStatus.mutateAsync({
      pluginId: plugin.value!.id,
      status: 'active',
      reviewStatus: 'approved',
    })
    await mutations.updateVersionStatus.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: candidate.value!.id,
      status: 'active',
    })
    await mutations.setLatest.mutateAsync({ pluginId: plugin.value!.id, versionId: candidate.value!.id })
    await mutations.refreshCache.mutateAsync()
  })
}

async function skipReviewAndPublish() {
  if (!plugin.value || !candidate.value) return
  await runAction(async () => {
    await mutations.updatePluginReviewStatus.mutateAsync({
      pluginId: plugin.value!.id,
      status: 'active',
      reviewStatus: 'skipped',
    })
    await mutations.updateVersionStatus.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: candidate.value!.id,
      status: 'active',
    })
    await mutations.setLatest.mutateAsync({ pluginId: plugin.value!.id, versionId: candidate.value!.id })
    await mutations.refreshCache.mutateAsync()
  })
}

async function disablePlugin() {
  if (!plugin.value) return
  await runAction(() => mutations.updatePluginStatus.mutateAsync({ pluginId: plugin.value!.id, status: 'disabled' }))
}

async function deletePlugin() {
  if (!plugin.value) return
  await runAction(() => mutations.deletePlugin.mutateAsync({ pluginId: plugin.value!.id }))
  selectedId.value = ''
}

async function setVersionStatus(version: VersionSummary, status: VersionStatus) {
  if (!plugin.value) return
  await runAction(() =>
    mutations.updateVersionStatus.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id, status }),
  )
}

async function setLatest(version: VersionSummary) {
  if (!plugin.value) return
  await runAction(() => mutations.setLatest.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id }))
}

async function rescanVersion(version: VersionSummary) {
  if (!plugin.value) return
  await runAction(() => mutations.triggerScan.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id }))
}

async function runScanProvider(version: VersionSummary, provider: 'virustotal' | 'llm_agent') {
  if (!plugin.value) return
  await runAction(() =>
    mutations.runScanProvider.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id, provider }),
  )
}

async function skipScanProvider(version: VersionSummary, provider: 'virustotal' | 'llm_agent') {
  if (!plugin.value) return
  await runAction(() =>
    mutations.skipScanProvider.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id, provider }),
  )
}

async function runAction(action: () => Promise<unknown>) {
  actionError.value = null
  try {
    await action()
    await pendingQuery.refetch()
    await detailQuery.refetch()
    message.success('已更新')
  } catch (err) {
    actionError.value = err
  }
}

function reviewStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '人工审核待处理',
    approved: '人工审核通过',
    skipped: '人工审核跳过',
    rejected: '人工审核拒绝',
  }
  return labels[status] || status
}
</script>

<style scoped>
.review-layout {
  display: grid;
  gap: 16px;
  grid-template-columns: 360px minmax(0, 1fr);
}

.review-list,
.workbench {
  background: var(--surface);
  border: 1px solid var(--divider);
  border-radius: 8px;
  min-height: 560px;
  padding: 12px;
}

.review-item {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  padding: 10px;
  text-align: left;
  width: 100%;
}

.review-item.active,
.review-item:hover {
  background: #f8fafc;
  border-color: var(--divider);
}

.workbench {
  display: grid;
  gap: 14px;
}

.workbench-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.meta {
  display: grid;
  gap: 8px;
  grid-template-columns: 80px minmax(0, 1fr);
  margin: 0;
}

.meta dt {
  color: var(--text-secondary);
}

.meta dd {
  margin: 0;
}

.action-bar {
  align-items: center;
  border-top: 1px solid var(--divider);
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 12px;
}
</style>
