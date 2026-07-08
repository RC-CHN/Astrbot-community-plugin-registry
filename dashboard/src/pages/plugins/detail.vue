<template>
  <page-header
    :title="plugin?.display_name || plugin?.plugin_key || '插件详情'"
    :description="plugin?.plugin_key"
  >
    <template v-if="plugin" #status>
      <n-space size="small">
        <status-tag kind="plugin" :value="plugin.status" />
        <n-tag size="small" round>{{ reviewStatusLabel(plugin.review_status) }}</n-tag>
      </n-space>
    </template>
    <template #actions>
      <n-button @click="router.back()">返回</n-button>
      <n-button v-if="plugin?.status === 'pending'" type="primary" @click="approvePluginOnly">
        标记人工审核通过
      </n-button>
      <n-button
        v-if="plugin?.status === 'pending' && latestCandidate"
        type="primary"
        :disabled="publishCandidateBlockers.length > 0"
        @click="openPublishConfirm"
      >
        发布当前版本
      </n-button>
      <n-button v-if="plugin?.status === 'active'" secondary @click="setPluginStatus('disabled')">
        禁用
      </n-button>
      <n-popconfirm
        v-if="plugin && plugin.status !== 'deleted'"
        positive-text="确认删除"
        negative-text="取消"
        @positive-click="deletePlugin"
      >
        <template #trigger>
          <n-button type="error" secondary>删除</n-button>
        </template>
        删除后插件、所有版本记录和对应构建制品都会被删除，确认继续？
      </n-popconfirm>
    </template>
  </page-header>

  <api-error-alert :error="query.error.value || actionError" />
  <n-spin :show="query.isLoading.value">
    <template v-if="plugin">
      <section class="detail-grid">
        <div class="panel">
          <h2>基本信息</h2>
          <dl>
            <dt>作者</dt>
            <dd>{{ plugin.author }}</dd>
            <dt>描述</dt>
            <dd>{{ plugin.description }}</dd>
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
              <span v-else>-</span>
            </dd>
            <dt>标签</dt>
            <dd>
              <n-space>
                <n-tag v-for="tag in plugin.tags" :key="tag" size="small">{{ tag }}</n-tag>
                <span v-if="!plugin.tags.length">-</span>
              </n-space>
            </dd>
          </dl>
        </div>
        <div class="panel">
          <h2>发布阻断</h2>
          <div class="concept-list">
            <div>
              <strong>审核通过</strong>
              <span>只确认插件进入可管理状态，不会自动公开任何版本。</span>
            </div>
            <div>
              <strong>发布</strong>
              <span>要求候选版本构建成功且扫描无阻断；成功后会启用插件，并把该版本设为插件源当前版本。</span>
            </div>
            <div>
              <strong>跳过人工审核</strong>
              <span>只跳过人工判断，不跳过构建和安全扫描。</span>
            </div>
          </div>
          <publish-blocker-alert :blockers="publishCandidateBlockers" />
          <n-empty v-if="!publishCandidateBlockers.length" description="当前候选版本可以公开" />
        </div>
      </section>

      <n-tabs type="line" animated class="tabs">
        <n-tab-pane name="versions" tab="版本">
          <version-table
            :plugin="plugin"
            :versions="plugin.versions"
            @set-version-status="setVersionStatus"
            @set-latest="setLatest"
            @rescan="rescanVersion"
            @run-scan-provider="runScanProvider"
            @skip-scan-provider="skipScanProvider"
            @browse-artifact="openArtifactBrowser"
            @delete-version="deleteVersion"
          />
        </n-tab-pane>
        <n-tab-pane name="metadata" tab="元数据">
          <pre class="metadata">{{ plugin }}</pre>
        </n-tab-pane>
      </n-tabs>
      <artifact-browser-modal
        v-model:show="artifactBrowserVisible"
        :plugin-id="plugin.id"
        :version="artifactBrowserVersion"
      />
    </template>
  </n-spin>

  <n-modal v-model:show="publishConfirmVisible" preset="card" title="发布当前版本" class="publish-confirm-modal">
    <div class="publish-confirm">
      <p>此操作将把当前版本设为 AstrBot 插件源返回的版本。</p>
      <ul>
        <li>标记插件为可公开</li>
        <li>标记当前版本为发布候选</li>
        <li>将当前版本设为插件源当前版本</li>
      </ul>
      <n-radio-group v-model:value="publishReviewStatus" class="publish-review-options">
        <n-radio value="approved">标记人工审核通过并发布</n-radio>
        <n-radio value="skipped">跳过人工审核并发布</n-radio>
      </n-radio-group>
      <p class="publish-confirm-note">跳过人工审核不会跳过构建和安全扫描；后端仍会校验所有发布阻断。</p>
    </div>
    <template #footer>
      <div class="publish-confirm-footer">
        <n-button @click="publishConfirmVisible = false">取消</n-button>
        <n-button type="primary" :disabled="publishCandidateBlockers.length > 0" @click="confirmPublishCurrent">
          确认发布
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import type { VersionStatus, VersionSummary } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import StatusTag from '@/components/common/status-tag.vue'
import PublishBlockerAlert from '@/components/review/publish-blocker-alert.vue'
import ArtifactBrowserModal from '@/components/version/artifact-browser-modal.vue'
import VersionTable from '@/components/version/version-table.vue'
import { getVersionBlockers } from '@/composables/use-plugin-actions'
import { usePluginDetail, usePluginMutations } from '@/query/plugins'
import { reviewStatusLabel } from '@/utils/review'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const pluginId = computed(() => String(route.params.id || ''))
const query = usePluginDetail(pluginId)
const mutations = usePluginMutations()
const actionError = ref<unknown>(null)
const plugin = computed(() => query.data.value)
const latestCandidate = computed(() => plugin.value?.versions.find((item) => item.is_latest) || plugin.value?.versions[0])
const artifactBrowserVisible = ref(false)
const artifactBrowserVersion = ref<VersionSummary | null>(null)
const publishConfirmVisible = ref(false)
const publishReviewStatus = ref<'approved' | 'skipped'>('approved')
const publishCandidateBlockers = computed(() => {
  if (!plugin.value) return []
  if (!latestCandidate.value) return ['暂无版本']
  return getVersionBlockers(plugin.value, latestCandidate.value, {
    includePluginStatus: false,
    includeVersionStatus: false,
  })
})

async function setPluginStatus(status: 'active' | 'disabled') {
  if (!plugin.value) return
  await runAction(() => mutations.updatePluginStatus.mutateAsync({ pluginId: plugin.value!.id, status }))
}

async function approvePluginOnly() {
  if (!plugin.value) return
  await runAction(() =>
    mutations.updatePluginReviewStatus.mutateAsync({
      pluginId: plugin.value!.id,
      status: 'active',
      reviewStatus: 'approved',
    }),
  )
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

async function deletePlugin() {
  if (!plugin.value) return
  await runAction(() => mutations.deletePlugin.mutateAsync({ pluginId: plugin.value!.id }))
  router.push('/plugins')
}

async function deleteVersion(version: VersionSummary) {
  if (!plugin.value) return
  await runAction(() =>
    mutations.deleteVersion.mutateAsync({ pluginId: plugin.value!.id, versionId: version.id }),
  )
}

function openPublishConfirm() {
  publishReviewStatus.value = 'approved'
  publishConfirmVisible.value = true
}

async function confirmPublishCurrent() {
  if (!plugin.value || !latestCandidate.value) return
  await runAction(() =>
    mutations.publishVersion.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: latestCandidate.value!.id,
      reviewStatus: publishReviewStatus.value,
    }),
  )
  publishConfirmVisible.value = false
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

function openArtifactBrowser(version: VersionSummary) {
  artifactBrowserVersion.value = version
  artifactBrowserVisible.value = true
}

async function runAction(action: () => Promise<unknown>) {
  actionError.value = null
  try {
    await action()
    await query.refetch()
    message.success('已更新')
  } catch (err) {
    actionError.value = err
  }
}

</script>

<style scoped>
.detail-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow-sm);
  padding: 16px;
}

h2 {
  font-size: 16px;
  margin: 0 0 12px;
}

.panel-note {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  margin: -4px 0 12px;
}

.concept-list {
  display: grid;
  gap: 8px;
  margin: -2px 0 12px;
}

.concept-list div {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 3px;
  min-width: 0;
  padding: 9px 10px;
}

.concept-list strong {
  color: var(--text-primary);
  font-size: 13px;
}

.concept-list span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

dl {
  display: grid;
  gap: 10px;
  grid-template-columns: 88px minmax(0, 1fr);
  margin: 0;
}

dt {
  color: var(--text-secondary);
}

dd {
  margin: 0;
  min-width: 0;
}

.tabs {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow-sm);
  margin-top: 16px;
  padding: 12px;
}

.metadata {
  margin: 0;
  max-height: 420px;
  overflow: auto;
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
</style>
