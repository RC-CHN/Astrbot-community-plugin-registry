<template>
  <div class="submission-page">
    <page-header title="我的提交" description="提交插件收录请求，管理员接受后才会进入构建和扫描队列" />
    <api-error-alert :error="error" />

    <section class="submission-layout">
      <div class="panel form-panel">
      <h2>创建请求</h2>
      <n-form :model="form" label-placement="top" class="request-form">
        <n-form-item label="GitHub 仓库地址">
          <n-input v-model:value="form.repo_url" placeholder="https://github.com/owner/repo" />
        </n-form-item>
        <div class="ref-section">
          <div class="ref-section-head">
            <div>
              <h3>选择 Ref</h3>
              <p>默认使用仓库默认分支；也可以指定分支、Tag 或 Commit。</p>
            </div>
            <n-tag size="small" round>{{ refModeLabel }}</n-tag>
          </div>

          <div class="ref-type-grid" role="radiogroup" aria-label="Ref 类型">
            <button
              v-for="option in refTypeOptions"
              :key="option.value"
              type="button"
              class="ref-type-option"
              :class="{ active: form.ref_type === option.value }"
              :aria-checked="form.ref_type === option.value"
              role="radio"
              @click="form.ref_type = option.value"
            >
              <strong>{{ option.label }}</strong>
              <span>{{ option.description }}</span>
            </button>
          </div>

          <n-form-item v-if="form.ref_type !== 'default'" :label="refInputLabel" class="ref-input-item">
            <n-input v-model:value="form.ref" :placeholder="refInputPlaceholder" />
          </n-form-item>
          <div v-else class="default-ref-note">
            管理员接受请求时会按仓库默认分支拉取最新提交。
          </div>
        </div>
        <n-form-item label="说明">
          <n-input
            v-model:value="form.user_message"
            type="textarea"
            :rows="4"
            placeholder="简单说明插件用途或希望收录的原因"
          />
        </n-form-item>
        <div class="form-actions">
          <n-button type="primary" :loading="createMutation.isPending.value" @click="submitRequest">
            提交请求
          </n-button>
        </div>
      </n-form>
      </div>

      <div class="panel queue-panel">
      <header class="queue-head">
        <div>
          <h2>请求列表</h2>
          <p>管理员处理后会在这里显示结果和说明。</p>
        </div>
        <span class="queue-count">{{ items.length }}</span>
      </header>
      <div v-if="query.isLoading.value" class="request-list">
        <div v-for="index in 6" :key="index" class="request-item skeleton-item" />
      </div>
      <div v-else-if="items.length" class="request-list">
        <article v-for="item in items" :key="item.id" class="request-item">
          <div class="request-main">
            <div class="request-title">
              <a class="repo-link" :href="item.repo_url" target="_blank" rel="noreferrer" :title="item.repo_url">
                {{ item.repo_url }}
              </a>
              <span class="request-ref">{{ refLabel(item) }}</span>
            </div>
            <span class="status-pill" :class="statusClass(item.status)">
              {{ statusLabel(item.status) }}
            </span>
          </div>

          <div class="request-meta">
            <span>{{ item.provider }}</span>
            <span>创建 {{ formatDateTime(item.created_at) }}</span>
            <span>更新 {{ formatDateTime(item.updated_at) }}</span>
          </div>

          <div v-if="item.admin_message" class="admin-message">
            <p>{{ item.admin_message }}</p>
          </div>
        </article>
      </div>
      <n-empty v-else description="暂无提交请求" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { createSubmission, listMySubmissions } from '@/api/submissions'
import type { SubmissionRefType, SubmissionRequest, SubmissionStatus } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import { formatDateTime } from '@/utils/datetime'

const queryClient = useQueryClient()
const error = ref<unknown>(null)
const form = reactive({
  repo_url: '',
  ref_type: 'default' as SubmissionRefType,
  ref: '',
  user_message: '',
})

const refTypeOptions: Array<{ label: string; value: SubmissionRefType; description: string }> = [
  { label: '默认分支', value: 'default', description: '使用仓库默认分支' },
  { label: '分支', value: 'branch', description: '填写分支名' },
  { label: 'Tag', value: 'tag', description: '填写标签名' },
  { label: 'Commit', value: 'commit', description: '填写提交 SHA' },
]

watch(
  () => form.ref_type,
  (value) => {
    if (value === 'default') form.ref = ''
  },
)

const query = useQuery({
  queryKey: ['my-submissions'],
  queryFn: listMySubmissions,
  refetchInterval: 5000,
})

const createMutation = useMutation({
  mutationFn: createSubmission,
  onSuccess: () => {
    form.repo_url = ''
    form.ref_type = 'default'
    form.ref = ''
    form.user_message = ''
    return queryClient.invalidateQueries({ queryKey: ['my-submissions'] })
  },
  onError: (err) => {
    error.value = err
  },
})

const items = computed(() => query.data.value?.items || [])
const refModeLabel = computed(() => refTypeOptions.find((item) => item.value === form.ref_type)?.label || '默认分支')
const refInputLabel = computed(() => {
  if (form.ref_type === 'branch') return '分支名'
  if (form.ref_type === 'tag') return 'Tag 名称'
  return 'Commit SHA'
})
const refInputPlaceholder = computed(() => {
  if (form.ref_type === 'branch') return '例如 main、master、dev'
  if (form.ref_type === 'tag') return '例如 v1.0.0'
  return '例如完整或短 commit SHA'
})

function submitRequest() {
  error.value = null
  const validationError = validateForm()
  if (validationError) {
    error.value = { status: 400, message: validationError }
    return
  }
  createMutation.mutate({
    repo_url: form.repo_url.trim(),
    ref_type: form.ref_type,
    ref: form.ref_type === 'default' ? null : form.ref.trim(),
    user_message: form.user_message.trim() || null,
  })
}

function validateForm() {
  if (!form.repo_url.trim()) return 'GitHub 仓库地址不能为空。'
  if (form.ref_type !== 'default' && !form.ref.trim()) {
    return `${refInputLabel.value}不能为空。`
  }
  return ''
}

function statusLabel(status: SubmissionStatus) {
  if (status === 'pending_review') return '待处理'
  if (status === 'accepted') return '已接受'
  if (status === 'rejected') return '已拒绝'
  return '重复'
}

function statusClass(status: SubmissionStatus) {
  if (status === 'accepted') return 'success'
  if (status === 'pending_review') return 'warning'
  if (status === 'rejected') return 'error'
  return 'neutral'
}

function refLabel(item: SubmissionRequest) {
  if (item.ref_type === 'default') return '默认分支'
  const labels: Record<SubmissionRefType, string> = {
    default: '默认分支',
    branch: '分支',
    tag: 'Tag',
    commit: 'Commit',
  }
  return `${labels[item.ref_type]}：${item.ref || '-'}`
}
</script>

<style scoped>
.submission-layout {
  align-items: stretch;
  display: grid;
  flex: 1;
  gap: 24px;
  grid-template-columns: minmax(340px, 440px) minmax(0, 1fr);
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.submission-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 104px);
  min-height: 0;
  overflow: hidden;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  min-width: 0;
  padding: 24px;
}

.panel h2 {
  font-size: 18px;
  line-height: 24px;
  margin: 0;
}

.form-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  overflow: auto;
}

.request-form {
  display: grid;
  gap: 16px;
}

.request-form :deep(.n-form-item) {
  margin-bottom: 0;
}

.ref-section {
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 14px;
}

.ref-section-head {
  align-items: flex-start;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
  min-width: 0;
}

.ref-section-head h3 {
  font-size: 15px;
  line-height: 22px;
  margin: 0;
}

.ref-section-head p,
.default-ref-note {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  margin: 2px 0 0;
}

.ref-type-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.ref-type-option {
  appearance: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  display: grid;
  gap: 3px;
  min-height: 64px;
  min-width: 0;
  padding: 10px 12px;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.ref-type-option:hover {
  border-color: var(--accent);
}

.ref-type-option strong {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 18px;
}

.ref-type-option span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 17px;
}

.ref-type-option.active {
  background: var(--info-bg);
  border-color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent);
}

.ref-input-item {
  margin-bottom: 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.queue-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
  overflow: hidden;
}

.queue-head {
  align-items: flex-start;
  border-bottom: 1px solid var(--divider);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin: -4px 0 0;
  padding-bottom: 14px;
}

.queue-head p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 20px;
  margin: 4px 0 0;
}

.queue-count {
  background: var(--info-bg);
  border-radius: 999px;
  color: var(--info-fg);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  min-width: 28px;
  padding: 2px 8px;
  text-align: center;
}

.request-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-top: 4px;
}

.request-item {
  background: transparent;
  border: 1px solid transparent;
  border-bottom-color: var(--divider);
  border-radius: 6px;
  display: block;
  min-width: 0;
  padding: 14px;
}

.request-item:hover {
  background: var(--surface-hover);
  border-color: var(--border-muted);
}

.request-main {
  align-items: flex-start;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
}

.request-title {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.repo-link {
  color: var(--text-link);
  font-size: 14px;
  font-weight: 600;
  line-height: 20px;
  min-width: 0;
  overflow: hidden;
  text-decoration: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.repo-link:hover {
  text-decoration: underline;
}

.request-ref {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  padding: 2px 9px;
  white-space: nowrap;
}

.status-pill.success {
  background: var(--success-bg);
  color: var(--success-fg);
}

.status-pill.warning {
  background: var(--warning-bg);
  color: var(--warning-fg);
}

.status-pill.error {
  background: var(--error-bg);
  color: var(--error-fg);
}

.status-pill.neutral {
  background: var(--neutral-bg);
  color: var(--text-secondary);
}

.request-meta {
  color: var(--text-tertiary);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 10px;
  line-height: 18px;
  margin-top: 8px;
}

.admin-message {
  background: var(--hover-bg);
  border-radius: 6px;
  margin-top: 10px;
  padding: 8px 10px;
}

.admin-message p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-word;
}

.skeleton-item {
  background: linear-gradient(90deg, var(--surface) 0%, var(--hover-bg) 50%, var(--surface) 100%);
  border-bottom: 1px solid var(--divider);
  height: 82px;
}

@media (max-width: 1180px) {
  .submission-page {
    height: auto;
    min-height: calc(100vh - 104px);
    overflow: visible;
  }

  .submission-layout {
    grid-template-columns: 1fr;
    overflow: visible;
  }

  .queue-panel {
    max-height: 520px;
  }
}

@media (max-width: 520px) {
  .ref-section-head {
    grid-template-columns: 1fr;
  }

  .ref-type-grid {
    grid-template-columns: 1fr;
  }

  .request-main {
    grid-template-columns: 1fr;
  }

  .repo-link,
  .request-ref,
  .admin-message p {
    white-space: normal;
    word-break: break-word;
  }
}
</style>
