<template>
  <page-header
    :title="plugin?.display_name || plugin?.plugin_key || '插件详情'"
    :description="plugin?.plugin_key"
  >
    <template v-if="plugin" #status>
      <status-tag kind="plugin" :value="plugin.status" />
    </template>
    <template #actions>
      <n-button @click="router.back()">返回</n-button>
      <n-button v-if="plugin?.status === 'pending'" type="primary" @click="setPluginStatus('active')">
        通过插件
      </n-button>
      <n-popconfirm
        v-if="plugin?.status === 'pending' && latestCandidate"
        positive-text="确认跳过"
        negative-text="取消"
        @positive-click="skipReviewAndPublish"
      >
        <template #trigger>
          <n-button type="warning" secondary>跳过审核并发布</n-button>
        </template>
        跳过人工审核会直接公开当前版本，请确认这个插件来源可信。
      </n-popconfirm>
      <n-button v-if="plugin?.status === 'active'" secondary @click="setPluginStatus('disabled')">
        禁用
      </n-button>
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
              <a v-if="plugin.repo_url" :href="plugin.repo_url" target="_blank">{{ plugin.repo_url }}</a>
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
          <publish-blocker-alert :blockers="latestCandidateBlockers" />
          <n-empty v-if="!latestCandidateBlockers.length" description="当前 latest 版本可公开访问" />
        </div>
      </section>

      <n-tabs type="line" animated class="tabs">
        <n-tab-pane name="versions" tab="版本">
          <version-table
            :plugin="plugin"
            :versions="plugin.versions"
            @set-version-status="setVersionStatus"
            @set-latest="setLatest"
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
const latestCandidateBlockers = computed(() =>
  plugin.value && latestCandidate.value ? getVersionBlockers(plugin.value, latestCandidate.value) : [],
)

async function setPluginStatus(status: 'active' | 'disabled') {
  if (!plugin.value) return
  await runAction(() => mutations.updatePluginStatus.mutateAsync({ pluginId: plugin.value!.id, status }))
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

async function skipReviewAndPublish() {
  if (!plugin.value || !latestCandidate.value) return
  await runAction(async () => {
    await mutations.updatePluginStatus.mutateAsync({ pluginId: plugin.value!.id, status: 'active' })
    await mutations.updateVersionStatus.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: latestCandidate.value!.id,
      status: 'active',
    })
    await mutations.setLatest.mutateAsync({
      pluginId: plugin.value!.id,
      versionId: latestCandidate.value!.id,
    })
    await mutations.refreshCache.mutateAsync()
  })
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
  border: 1px solid var(--divider);
  border-radius: 8px;
  padding: 16px;
}

h2 {
  font-size: 16px;
  margin: 0 0 12px;
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
  border: 1px solid var(--divider);
  border-radius: 8px;
  margin-top: 16px;
  padding: 12px;
}

.metadata {
  margin: 0;
  max-height: 420px;
  overflow: auto;
}
</style>
