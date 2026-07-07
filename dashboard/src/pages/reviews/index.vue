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
        <header class="workbench-header">
          <plugin-title :plugin="plugin" />
          <n-space size="small">
            <status-tag kind="plugin" :value="plugin.status" />
            <n-tag size="small" round>{{ reviewStatusLabel(plugin.review_status) }}</n-tag>
          </n-space>
        </header>

        <section class="info-section">
          <h3 class="section-title">插件信息</h3>
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
        </section>

        <publish-blocker-alert :blockers="publishBlockers" />

        <section class="version-section">
          <h3 class="section-title">版本列表</h3>
          <div v-if="plugin.versions.length" class="version-table-wrap">
            <version-table
              :plugin="plugin"
              :versions="plugin.versions"
              @set-version-status="setVersionStatus"
              @set-latest="setLatest"
              @rescan="rescanVersion"
              @run-scan-provider="runScanProvider"
              @skip-scan-provider="skipScanProvider"
            />
          </div>
          <empty-state v-else description="暂无版本" />
        </section>

        <section class="action-section">
          <h3 class="section-title">审核操作</h3>
          <p class="section-note">
            发布当前版本会同时启用插件、标记版本可发布并设为当前公开版本；跳过人工审核不会跳过构建和安全扫描。
          </p>
          <div class="action-bar">
            <n-space align="center" justify="space-between" wrap :size="16">
              <n-button @click="router.push(`/plugins/${plugin.id}`)">打开详情</n-button>
              <n-space align="center" wrap :size="12">
                <n-button-group>
                  <n-button @click="approvePluginOnly">
                    仅标记审核通过
                  </n-button>
                  <n-button type="primary" :disabled="publishBlockers.length > 0" @click="approveAndPublish">
                    审核通过并发布当前版本
                  </n-button>
                </n-button-group>

                <n-divider vertical style="height: 24px" />

                <n-popconfirm
                  positive-text="确认跳过"
                  negative-text="取消"
                  @positive-click="skipReviewAndPublish"
                >
                  <template #trigger>
                    <n-button type="warning" secondary :disabled="publishBlockers.length > 0">
                      跳过人工审核并发布
                    </n-button>
                  </template>
                  这只跳过人工审核，不会跳过构建和安全扫描。确认后会公开当前版本。
                </n-popconfirm>

                <n-divider vertical style="height: 24px" />

                <n-button-group>
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
                </n-button-group>
              </n-space>
            </n-space>
          </div>
        </section>
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
const publishBlockers = computed(() => {
  if (!plugin.value) return []
  if (!candidate.value) return ['暂无版本']
  return getVersionBlockers(plugin.value, candidate.value, {
    includePluginStatus: false,
    includeVersionStatus: false,
  })
})

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
  await runAction(() =>
    mutations.publishVersion.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: candidate.value!.id,
      reviewStatus: 'approved',
    }),
  )
}

async function skipReviewAndPublish() {
  if (!plugin.value || !candidate.value) return
  await runAction(() =>
    mutations.publishVersion.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: candidate.value!.id,
      reviewStatus: 'skipped',
    }),
  )
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
  align-items: start;
  display: grid;
  gap: 24px;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  min-width: 0;
}

.review-list,
.workbench {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  min-height: 600px;
  min-width: 0;
  padding: 24px;
}

.review-list {
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  position: sticky;
  top: 16px;
}

.review-item {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-bottom: 1px solid var(--divider);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 14px;
  text-align: left;
  width: 100%;
}

.review-item.active,
.review-item:hover {
  background: var(--surface-hover);
  border-color: var(--border-muted);
}

.workbench {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.workbench-header {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  min-width: 0;
}

.section-title {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin: 0 0 12px;
}

.section-note {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  margin: -4px 0 12px;
}

.meta {
  background: var(--surface-hover);
  border-radius: 8px;
  display: grid;
  gap: 12px;
  grid-template-columns: 80px minmax(0, 1fr);
  margin: 0;
  padding: 16px;
}

.meta dt {
  color: var(--text-secondary);
}

.meta dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

.version-table-wrap {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
}

.action-bar {
  border-top: 1px solid var(--divider);
  padding-top: 16px;
}

@media (max-width: 1180px) {
  .review-layout {
    grid-template-columns: 1fr;
  }

  .review-list {
    max-height: 360px;
    min-height: auto;
    position: static;
  }
}
</style>
