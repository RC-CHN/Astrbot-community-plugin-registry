<template>
  <div class="review-page">
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
            <p class="section-note">
              版本号来自 metadata.yaml；commit 是制品身份，同一 commit 不重复构建。版本先完成构建和扫描，再标记为发布候选；只有设为插件源当前版本后，AstrBot 插件源才会返回这个版本。
            </p>
            <div v-if="plugin.versions.length" class="review-version-list">
              <version-summary-card
                v-for="version in plugin.versions"
                :key="version.id"
                :plugin="plugin"
                :version="version"
                :review-status="plugin.review_status"
                @show-scan-detail="openScanDetail"
                @set-version-status="setVersionStatus"
                @set-latest="setLatest"
                @browse-artifact="openArtifactBrowser"
                @rescan="rescanVersion"
                @run-scan-provider="runScanProvider"
                @skip-scan-provider="skipScanProvider"
              />
            </div>
            <empty-state v-else description="暂无版本" />
          </section>

          <scan-detail-modal v-model:show="scanDetailVisible" :version="scanDetailVersion" />
          <artifact-browser-modal
            v-model:show="artifactBrowserVisible"
            :plugin-id="plugin.id"
            :version="artifactBrowserVersion"
          />

          <section class="action-section">
            <h3 class="section-title">审核操作</h3>
            <div class="concept-grid" aria-label="审核与发布说明">
              <div class="concept-item">
                <strong>扫描引擎</strong>
                <span>ClamAV、VirusTotal、LLM 等机器 provider 可按需启用；只有启用中的 provider 会阻断发布。</span>
              </div>
              <div class="concept-item">
                <strong>人工审核</strong>
                <span>人工是机器扫描之后的最终门禁；若配置为需要人工审核，扫描全绿后仍需管理员发布。</span>
              </div>
              <div class="concept-item">
                <strong>自动发布</strong>
                <span>关闭人工门禁且启用自动发布时，构建成功并且所有启用 provider 通过后会自动公开当前版本。</span>
              </div>
            </div>
            <div class="action-bar">
              <div class="action-toolbar">
                <n-button class="action-button" @click="router.push(`/plugins/${plugin.id}`)">打开详情</n-button>
                <div class="action-groups">
                  <div class="action-group">
                    <n-button class="action-button" @click="approvePluginOnly">
                      标记人工审核通过
                    </n-button>
                    <n-button
                      class="action-button"
                      type="primary"
                      :disabled="publishBlockers.length > 0"
                      @click="openPublishConfirm"
                    >
                      发布当前版本
                    </n-button>
                  </div>

                  <div class="action-group danger">
                    <n-button class="action-button compact" type="error" secondary @click="disablePlugin">禁用</n-button>
                    <n-popconfirm
                      positive-text="确认删除"
                      negative-text="取消"
                      @positive-click="deletePlugin"
                    >
                      <template #trigger>
                        <n-button class="action-button compact" type="error" secondary>删除</n-button>
                      </template>
                      删除后插件和版本会从公开索引移除，确认继续？
                    </n-popconfirm>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </template>
        <empty-state v-else description="请选择一个待审核插件" />
      </main>
    </div>

    <n-modal
      v-model:show="publishConfirmVisible"
      preset="card"
      title="发布当前版本"
      class="publish-confirm-modal"
      :style="publishConfirmModalStyle"
    >
      <div class="publish-confirm">
        <p>此操作将把当前版本设为 AstrBot 插件源返回的版本。</p>
        <ul>
          <li>标记插件为可公开</li>
          <li>标记当前版本为发布候选</li>
          <li>将当前版本设为插件源当前版本</li>
        </ul>
        <template v-if="needsPublishReviewChoice">
          <n-radio-group v-model:value="publishReviewStatus" class="publish-review-options">
            <n-radio value="approved">标记人工审核通过并发布</n-radio>
            <n-radio value="skipped">跳过人工审核并发布</n-radio>
          </n-radio-group>
          <p class="publish-confirm-note">跳过人工审核不会跳过构建和安全扫描；后端仍会校验所有发布阻断。</p>
        </template>
        <p v-else class="publish-confirm-note">
          已记录{{ reviewStatusLabel(plugin?.review_status || '') }}，本次发布会沿用当前人工审核状态。
        </p>
      </div>
      <template #footer>
        <div class="publish-confirm-footer">
          <n-button @click="publishConfirmVisible = false">取消</n-button>
          <n-button type="primary" :disabled="publishBlockers.length > 0" @click="confirmPublishCurrent">
            确认发布
          </n-button>
        </div>
      </template>
    </n-modal>
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
import ArtifactBrowserModal from '@/components/version/artifact-browser-modal.vue'
import ScanDetailModal from '@/components/version/scan-detail-modal.vue'
import VersionSummaryCard from '@/components/version/version-summary-card.vue'
import { getVersionBlockers } from '@/composables/use-plugin-actions'
import { usePendingPlugins, usePluginDetail, usePluginMutations } from '@/query/plugins'
import { reviewStatusLabel } from '@/utils/review'

const router = useRouter()
const message = useMessage()
const pendingQuery = usePendingPlugins()
const selectedId = ref('')
const detailQuery = usePluginDetail(selectedId)
const mutations = usePluginMutations()
const actionError = ref<unknown>(null)
const plugin = computed(() => detailQuery.data.value)
const candidate = computed(() => plugin.value?.versions[0])
const scanDetailVisible = ref(false)
const scanDetailVersion = ref<VersionSummary | null>(null)
const artifactBrowserVisible = ref(false)
const artifactBrowserVersion = ref<VersionSummary | null>(null)
const publishConfirmVisible = ref(false)
const publishReviewStatus = ref<'approved' | 'skipped'>('approved')
const publishConfirmModalStyle = {
  maxWidth: 'calc(100vw - 32px)',
  width: '520px',
}
const needsPublishReviewChoice = computed(() => {
  const status = plugin.value?.review_status
  return status !== 'approved' && status !== 'skipped'
})
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
  await runAction(() =>
    mutations.updatePluginReviewStatus.mutateAsync({
      pluginId: plugin.value!.id,
      status: plugin.value!.status,
      reviewStatus: 'approved',
    }),
  )
}

function openPublishConfirm() {
  publishReviewStatus.value = 'approved'
  publishConfirmVisible.value = true
}

async function confirmPublishCurrent() {
  if (!plugin.value || !candidate.value) return
  const reviewStatus =
    plugin.value.review_status === 'approved' || plugin.value.review_status === 'skipped'
      ? plugin.value.review_status
      : publishReviewStatus.value
  await runAction(() =>
    mutations.publishVersion.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: candidate.value!.id,
      reviewStatus,
    }),
  )
  publishConfirmVisible.value = false
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

async function runScanProvider(version: VersionSummary, provider: string) {
  if (!plugin.value) return
  await runAction(() =>
    mutations.runScanProvider.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id, provider }),
  )
}

async function skipScanProvider(version: VersionSummary, provider: string) {
  if (!plugin.value) return
  await runAction(() =>
    mutations.skipScanProvider.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id, provider }),
  )
}

function openScanDetail(version: VersionSummary) {
  scanDetailVersion.value = version
  scanDetailVisible.value = true
}

function openArtifactBrowser(version: VersionSummary) {
  artifactBrowserVersion.value = version
  artifactBrowserVisible.value = true
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
</script>

<style scoped>
.review-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 104px);
  min-height: 0;
  overflow: hidden;
}

.review-layout {
  align-items: stretch;
  display: grid;
  flex: 1;
  gap: 24px;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.review-list,
.workbench {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  height: 100%;
  min-height: 0;
  min-width: 0;
  padding: 24px;
}

.review-list {
  overflow-y: auto;
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
  overflow: auto;
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

.concept-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  margin: -4px 0 16px;
  min-width: 0;
}

.concept-item {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
}

.concept-item strong {
  color: var(--text-primary);
  font-size: 13px;
}

.concept-item span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
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

.review-version-list {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.action-bar {
  border-top: 1px solid var(--divider);
  padding-top: 16px;
}

.action-toolbar {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  max-width: 100%;
  min-width: 0;
}

.action-groups {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  min-width: 0;
}

.action-group {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.action-button {
  flex: 0 1 auto;
  max-width: 100%;
}

.action-button.compact {
  min-width: 60px;
}

.action-section :deep(.n-button__content) {
  min-width: 0;
  white-space: normal;
}

.publish-confirm {
  color: var(--text-secondary);
  display: grid;
  gap: 12px;
  min-width: 0;
}

.publish-confirm p {
  line-height: 1.6;
  margin: 0;
}

.publish-confirm ul {
  margin: 0;
  padding-left: 18px;
}

.publish-confirm li {
  line-height: 1.7;
}

.publish-review-options {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 10px;
  padding: 12px;
}

.publish-confirm-note {
  font-size: 12px;
}

.publish-confirm-footer {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

:deep(.publish-confirm-modal) {
  width: min(520px, calc(100vw - 32px));
}

@media (max-width: 1180px) {
  .review-layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(160px, 32%) minmax(0, 1fr);
  }

  .review-list {
    min-height: 0;
  }
}

@media (max-width: 760px) {
  .action-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .action-groups {
    justify-content: flex-start;
  }
}
</style>
