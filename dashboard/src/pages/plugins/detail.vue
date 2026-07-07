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
        仅标记审核通过
      </n-button>
      <n-popconfirm
        v-if="plugin?.status === 'pending' && latestCandidate"
        positive-text="确认跳过"
        negative-text="取消"
        @positive-click="skipReviewAndPublish"
      >
        <template #trigger>
          <n-button type="warning" secondary :disabled="publishCandidateBlockers.length > 0">
            跳过人工审核并发布
          </n-button>
        </template>
        这只跳过人工审核，不会跳过构建和安全扫描。确认后会公开当前版本。
      </n-popconfirm>
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
        删除后插件和版本会从公开索引移除，确认继续？
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
          <p class="panel-note">发布操作会同时启用插件、标记版本可发布并设为当前公开版本。</p>
          <publish-blocker-alert :blockers="publishCandidateBlockers" />
          <n-empty v-if="!publishCandidateBlockers.length" description="当前候选版本可以发布" />
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
          />
        </n-tab-pane>
        <n-tab-pane name="metadata" tab="元数据">
          <pre class="metadata">{{ plugin }}</pre>
        </n-tab-pane>
      </n-tabs>
    </template>
  </n-spin>
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
import VersionTable from '@/components/version/version-table.vue'
import { getVersionBlockers } from '@/composables/use-plugin-actions'
import { usePluginDetail, usePluginMutations } from '@/query/plugins'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const pluginId = computed(() => String(route.params.id || ''))
const query = usePluginDetail(pluginId)
const mutations = usePluginMutations()
const actionError = ref<unknown>(null)
const plugin = computed(() => query.data.value)
const latestCandidate = computed(() => plugin.value?.versions.find((item) => item.is_latest) || plugin.value?.versions[0])
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

async function skipReviewAndPublish() {
  if (!plugin.value || !latestCandidate.value) return
  await runAction(() =>
    mutations.publishVersion.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: latestCandidate.value!.id,
      reviewStatus: 'skipped',
    }),
  )
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
    await query.refetch()
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
</style>
