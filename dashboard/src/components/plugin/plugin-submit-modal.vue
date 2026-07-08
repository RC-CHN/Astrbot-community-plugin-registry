<template>
  <n-modal
    :show="show"
    preset="card"
    title="提交插件"
    class="submit-modal"
    :bordered="false"
    :style="{ width: 'min(920px, calc(100vw - 32px))' }"
    @update:show="emit('update:show', $event)"
  >
    <n-tabs v-model:value="mode" type="line" animated>
      <n-tab-pane name="repo" tab="Git 仓库">
        <api-error-alert :error="error" />

        <section class="submit-section">
          <div class="section-head">
            <div>
              <h3>仓库</h3>
              <p>目前仅支持 GitHub 仓库。</p>
            </div>
            <n-tag v-if="inspection" size="small" round>{{ inspection.provider }}</n-tag>
          </div>

          <n-form :model="repoForm" label-placement="top" class="submit-form">
            <n-form-item label="仓库地址">
              <n-input
                v-model:value="repoForm.repo_url"
                class="repo-url-input"
                placeholder="https://github.com/owner/repo"
                :input-props="{
                  autocomplete: 'off',
                  autocapitalize: 'off',
                  spellcheck: 'false',
                }"
                @keydown.enter.prevent="inspectDefault"
              />
            </n-form-item>
            <n-form-item label="访问 Token">
              <n-input
                v-model:value="repoForm.temporary_token"
                type="password"
                show-password-on="click"
                placeholder="可选，本次检测和构建使用；不会保存"
              />
            </n-form-item>
            <div class="form-actions">
              <n-button type="primary" secondary :loading="detectingRepo" @click="inspectDefault">
                检测仓库
              </n-button>
              <n-button v-if="inspection" quaternary :loading="refreshingRef" @click="refreshCurrentRef">
                刷新当前 Ref
              </n-button>
            </div>
          </n-form>
        </section>

        <section v-if="inspection" class="submit-section">
          <div class="repo-summary">
            <div>
              <span>仓库</span>
              <strong>{{ inspection.owner }}/{{ inspection.repo }}</strong>
              <small>{{ inspection.private ? '私有仓库' : '公开仓库' }} · {{ formatSizeKb(inspection.size_kb) }}</small>
            </div>
            <div>
              <span>默认分支</span>
              <strong>{{ inspection.default_branch }}</strong>
              <small>{{ inspection.host }}</small>
            </div>
            <div>
              <span>最终 Commit</span>
              <strong>{{ shortSha(inspection.selected_commit.sha) }}</strong>
              <small>{{ inspection.selected_commit.message || '无提交信息' }}</small>
            </div>
            <div>
              <span>metadata 版本</span>
              <strong>{{ inspection.metadata.version }}</strong>
              <small>{{ inspection.metadata.plugin_key }}</small>
            </div>
          </div>

          <n-alert v-if="inspection.private" type="warning" :bordered="false">
            私有仓库源码会被打包成插件制品；发布后公开插件源会返回该制品下载地址。
          </n-alert>
          <n-alert v-if="inspection.match.status === 'duplicate_commit'" type="warning" :bordered="false">
            这个 commit 已经存在，通常不需要重复提交。
          </n-alert>
          <n-alert
            v-else-if="inspection.match.duplicate_version_count > 0"
            type="info"
            :bordered="false"
          >
            已存在 {{ inspection.match.duplicate_version_count }} 个相同 metadata 版本；本次会按 commit 单独保存。
          </n-alert>
        </section>

        <section v-if="inspection" class="submit-section">
          <div class="section-head">
            <div>
              <h3>选择 Ref</h3>
              <p>选择分支或 Tag 后会解析到具体 commit。默认固定到 commit，保证构建结果可复现。</p>
            </div>
            <n-tag size="small" round :type="lockToCommit ? 'success' : 'warning'">
              {{ lockToCommit ? '固定 commit' : '跟随 Ref' }}
            </n-tag>
          </div>

          <div class="ref-selector">
            <div class="ref-kind-list">
              <button
                v-for="option in refModeOptions"
                :key="option.value"
                type="button"
                class="ref-kind"
                :class="{ active: refMode === option.value }"
                @click="handleRefModeChange(option.value)"
              >
                <strong>{{ option.label }}</strong>
                <span>{{ option.description }}</span>
              </button>
            </div>

            <div class="ref-panel">
              <div class="ref-control">
                <label>{{ refControlLabel }}</label>
                <n-select
                  v-if="refMode === 'branch'"
                  v-model:value="selectedBranch"
                  filterable
                  :loading="resolvingRef"
                  :disabled="detectingRepo"
                  :options="branchOptions"
                  placeholder="选择分支"
                  @update:value="resolveCurrentRef"
                />
                <p v-if="refMode === 'branch' && !branchOptions.length" class="ref-warning">
                  这个仓库没有可选分支。
                </p>
                <n-select
                  v-else-if="refMode === 'tag'"
                  v-model:value="selectedTag"
                  filterable
                  :loading="resolvingRef"
                  :disabled="detectingRepo"
                  :options="tagOptions"
                  placeholder="选择 Tag"
                  @update:value="resolveCurrentRef"
                />
                <p v-if="refMode === 'tag' && !tagOptions.length" class="ref-warning">
                  这个仓库没有 Tag。
                </p>
                <n-input-group v-else-if="refMode === 'commit'">
                  <n-input
                    v-model:value="commitInput"
                    :disabled="detectingRepo"
                    placeholder="输入 commit SHA"
                  />
                  <n-button :loading="resolvingCommit" @click="resolveCommitRef">解析</n-button>
                </n-input-group>
                <div v-else class="default-ref">
                  <code>{{ inspection.default_branch }}</code>
                  <n-button text type="primary" :loading="resolvingRef" @click="resolveCurrentRef">
                    重新解析
                  </n-button>
                </div>
                <p v-if="commitNeedsResolve" class="ref-warning">Commit 已变更，提交前需要先解析。</p>
              </div>

              <div class="resolved-commit" :class="{ loading: refBusy }">
                <div class="resolved-head">
                  <span>已解析 Commit</span>
                  <n-tag v-if="refBusy" size="small" round>解析中</n-tag>
                </div>
                <strong>{{ shortSha(inspection.selected_commit.sha) }}</strong>
                <p>{{ inspection.selected_commit.message || '无提交信息' }}</p>
              </div>

              <div class="ref-submit-mode">
                <div>
                  <strong>提交构建使用</strong>
                  <p>{{ lockToCommit ? '使用已解析 commit SHA，构建结果可复现。' : '使用当前 Ref 名称，后续提交可能影响构建内容。' }}</p>
                </div>
                <n-switch v-model:value="lockToCommit">
                  <template #checked>固定</template>
                  <template #unchecked>跟随</template>
                </n-switch>
              </div>

              <div class="final-ref">
                <span>{{ lockToCommit ? 'Commit SHA' : 'Ref' }}</span>
                <code>{{ finalRef || '-' }}</code>
              </div>
            </div>
          </div>
        </section>

        <section v-if="inspection" class="submit-section">
          <div class="section-head">
            <div>
              <h3>构建信息</h3>
              <p>留空使用 metadata.yaml；填写后会改写构建包内 metadata.yaml 的 version 字段。</p>
            </div>
          </div>
          <n-form :model="repoForm" label-placement="top" class="submit-form">
            <n-form-item label="覆盖 metadata 版本">
              <n-input v-model:value="repoForm.version" placeholder="留空保持仓库 metadata.yaml 版本" />
            </n-form-item>
            <n-form-item label="Changelog">
              <n-input v-model:value="repoForm.changelog" type="textarea" :rows="3" placeholder="写入当前版本记录" />
            </n-form-item>
          </n-form>
        </section>
      </n-tab-pane>

      <n-tab-pane name="zip" tab="ZIP 上传">
        <api-error-alert :error="error" />
        <n-upload :max="1" accept=".zip" :default-upload="false" @change="handleFileChange">
          <n-upload-dragger>
            <div class="upload-text">选择或拖入插件 ZIP</div>
            <div class="muted">上传前会检查 metadata.yaml</div>
          </n-upload-dragger>
        </n-upload>
      </n-tab-pane>
    </n-tabs>

    <n-alert v-if="result" type="success" :bordered="false" class="result">
      <div>已提交：{{ resultId }}</div>
      <div v-if="'version' in result && result.version">版本：{{ result.version }}</div>
      <div v-if="'status' in result && result.status">状态：{{ result.status }}</div>
    </n-alert>

    <template #footer>
      <div class="modal-footer">
        <n-button @click="emit('update:show', false)">关闭</n-button>
        <n-button v-if="result" @click="reset">继续提交</n-button>
        <n-button type="primary" :loading="loading" :disabled="submitDisabled" @click="submit">
          提交构建
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import type {
  RepoInspectResponse,
  RepoResolveResponse,
  RepoRefType,
  SubmitPluginResponse,
  VersionSubmitResponse,
} from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import { usePluginMutations } from '@/query/plugins'

defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean] }>()

const mode = ref<'repo' | 'zip'>('repo')
const loading = ref(false)
const inspectAction = ref<'detect' | 'refresh' | 'ref' | 'commit' | null>(null)
const error = ref<unknown>(null)
const result = ref<SubmitPluginResponse | VersionSubmitResponse | null>(null)
const inspection = ref<RepoInspectResponse | null>(null)
const resolvedRefCache = new Map<string, RepoResolveResponse>()
const activeResolveKey = ref('')
const refMode = ref<RepoRefType>('default')
const selectedBranch = ref('')
const selectedTag = ref('')
const commitInput = ref('')
const lockToCommit = ref(true)
const file = ref<File | null>(null)
const mutations = usePluginMutations()
const repoForm = reactive({
  repo_url: '',
  temporary_token: '',
  version: '',
  changelog: '',
})

const resultId = computed(() => {
  if (!result.value) return ''
  if ('plugin_id' in result.value && result.value.plugin_id) return result.value.plugin_id
  if ('version_id' in result.value && result.value.version_id) return result.value.version_id
  return '-'
})

const inspecting = computed(() => inspectAction.value !== null)
const detectingRepo = computed(() => inspectAction.value === 'detect')
const refreshingRef = computed(() => inspectAction.value === 'refresh')
const resolvingRef = computed(() => inspectAction.value === 'ref')
const resolvingCommit = computed(() => inspectAction.value === 'commit')
const refBusy = computed(() => refreshingRef.value || resolvingRef.value || resolvingCommit.value)

const refModeOptions: Array<{
  value: RepoRefType
  label: string
  description: string
}> = [
  { value: 'default', label: '默认分支', description: '使用仓库默认分支最新提交' },
  { value: 'branch', label: '分支', description: '选择一个分支并解析提交' },
  { value: 'tag', label: 'Tag', description: '选择一个发布标签' },
  { value: 'commit', label: 'Commit', description: '指定完整或短 SHA' },
]

const branchOptions = computed(() =>
  (inspection.value?.branches || []).map((item) => ({
    label: `${item.name}  ${shortSha(item.commit_sha)}`,
    value: item.name,
  })),
)

const tagOptions = computed(() =>
  (inspection.value?.tags || []).map((item) => ({
    label: `${item.name}  ${shortSha(item.commit_sha)}`,
    value: item.name,
  })),
)

const selectedRef = computed(() => {
  if (!inspection.value) return ''
  if (refMode.value === 'default') return inspection.value.default_branch
  if (refMode.value === 'branch') return selectedBranch.value
  if (refMode.value === 'tag') return selectedTag.value
  return commitInput.value.trim()
})

const canResolveCurrentRef = computed(() => {
  if (!inspection.value) return false
  if (refMode.value === 'default') return Boolean(inspection.value.default_branch)
  if (refMode.value === 'branch') return Boolean(selectedBranch.value)
  if (refMode.value === 'tag') return Boolean(selectedTag.value)
  return Boolean(commitInput.value.trim())
})

const finalRef = computed(() => {
  if (!inspection.value) return ''
  if (lockToCommit.value) return inspection.value.selected_commit.sha
  return selectedRef.value
})

const refControlLabel = computed(() => {
  if (refMode.value === 'branch') return '分支'
  if (refMode.value === 'tag') return 'Tag'
  if (refMode.value === 'commit') return 'Commit SHA'
  return '默认分支'
})

const commitNeedsResolve = computed(() => {
  if (!inspection.value || refMode.value !== 'commit') return false
  const value = commitInput.value.trim()
  if (!value) return false
  return value !== inspection.value.selected_ref && value !== inspection.value.selected_commit.sha
})

const submitDisabled = computed(() => {
  if (loading.value) return true
  if (mode.value === 'zip') return !file.value
  return (
    !inspection.value ||
    !finalRef.value ||
    !canResolveCurrentRef.value ||
    refBusy.value ||
    commitNeedsResolve.value ||
    inspection.value.match.status === 'duplicate_commit'
  )
})

function handleFileChange(options: { fileList: Array<{ file?: File | null }> }) {
  file.value = options.fileList[0]?.file || null
}

async function inspectDefault() {
  refMode.value = 'default'
  resolvedRefCache.clear()
  await inspectRepo('default', undefined, 'detect', true)
  void prewarmResolvedRefs()
}

async function refreshCurrentRef() {
  if (!canResolveCurrentRef.value) return
  resolvedRefCache.delete(cacheKey(refMode.value, selectedRef.value))
  await resolveRepoRef(refMode.value, selectedRef.value, 'refresh')
}

async function resolveCurrentRef() {
  if (!canResolveCurrentRef.value) return
  await resolveRepoRef(refMode.value, selectedRef.value, 'ref')
}

async function resolveCommitRef() {
  if (!canResolveCurrentRef.value) return
  resolvedRefCache.delete(cacheKey(refMode.value, selectedRef.value))
  await resolveRepoRef(refMode.value, selectedRef.value, 'commit')
}

async function handleRefModeChange(value: string) {
  const next = value as RepoRefType
  refMode.value = next
  if (next === 'branch' && !selectedBranch.value) {
    selectedBranch.value = branchOptions.value[0]?.value || ''
  }
  if (next === 'tag' && !selectedTag.value) {
    selectedTag.value = tagOptions.value[0]?.value || ''
  }
  if (next === 'commit' && !commitInput.value) {
    commitInput.value = inspection.value?.selected_commit.sha || ''
  }
  if (canResolveCurrentRef.value) {
    await resolveCurrentRef()
  }
}

async function resolveRepoRef(
  nextRefType: RepoRefType,
  nextRef: string | undefined,
  action: 'refresh' | 'ref' | 'commit',
) {
  if (!inspection.value) return
  if (!repoForm.repo_url.trim()) {
    error.value = new Error('请先填写仓库地址')
    return
  }
  const key = cacheKey(nextRefType, nextRef)
  const cached = resolvedRefCache.get(key)
  if (cached && action !== 'refresh' && action !== 'commit') {
    applyResolvedRef(cached)
    return
  }
  activeResolveKey.value = key
  inspectAction.value = action
  error.value = null
  result.value = null
  try {
    const data = await mutations.resolveRepoRef.mutateAsync({
      repo_url: repoForm.repo_url,
      temporary_token: repoForm.temporary_token || undefined,
      ref_type: nextRefType,
      ref: nextRef || undefined,
    })
    resolvedRefCache.set(cacheKey(data.selected_ref_type, data.selected_ref), data)
    if (activeResolveKey.value === key) {
      applyResolvedRef(data)
    }
  } catch (err) {
    if (activeResolveKey.value === key) {
      error.value = err
    }
  } finally {
    if (activeResolveKey.value === key) {
      inspectAction.value = null
      activeResolveKey.value = ''
    }
  }
}

async function inspectRepo(
  nextRefType: RepoRefType,
  nextRef: string | undefined,
  action: 'detect' | 'refresh' | 'ref' | 'commit',
  includeRefs: boolean,
) {
  if (!repoForm.repo_url.trim()) {
    error.value = new Error('请先填写仓库地址')
    return
  }
  inspectAction.value = action
  error.value = null
  result.value = null
  try {
    const data = await mutations.inspectRepo.mutateAsync({
      repo_url: repoForm.repo_url,
      temporary_token: repoForm.temporary_token || undefined,
      ref_type: nextRefType,
      ref: nextRef || undefined,
      include_refs: includeRefs,
    })
    applyInspection(data)
    resolvedRefCache.set(cacheKey(data.selected_ref_type, data.selected_ref), {
      selected_ref_type: data.selected_ref_type,
      selected_ref: data.selected_ref,
      selected_commit: data.selected_commit,
      metadata: data.metadata,
      match: data.match,
    })
  } catch (err) {
    error.value = err
  } finally {
    inspectAction.value = null
  }
}

function applyInspection(data: RepoInspectResponse) {
  const previous = inspection.value
  inspection.value = {
    ...data,
    branches: data.branches.length ? data.branches : previous?.branches || [],
    tags: data.tags.length ? data.tags : previous?.tags || [],
  }
  repoForm.repo_url = data.repo_url
  refMode.value = data.selected_ref_type
  if (data.selected_ref_type === 'branch') selectedBranch.value = data.selected_ref
  if (data.selected_ref_type === 'tag') selectedTag.value = data.selected_ref
  if (data.selected_ref_type === 'commit') commitInput.value = data.selected_ref
  if (!selectedBranch.value) selectedBranch.value = data.default_branch
  if (!selectedTag.value) selectedTag.value = data.tags[0]?.name || ''
  if (!commitInput.value) commitInput.value = data.selected_commit.sha
}

async function prewarmResolvedRefs() {
  if (!inspection.value) return
  const refs: Array<{ type: RepoRefType; ref: string }> = [
    { type: 'default', ref: inspection.value.default_branch },
  ]
  if (selectedBranch.value && selectedBranch.value !== inspection.value.default_branch) {
    refs.push({ type: 'branch', ref: selectedBranch.value })
  }
  if (selectedTag.value) {
    refs.push({ type: 'tag', ref: selectedTag.value })
  }
  await Promise.allSettled(
    refs.map(async (item) => {
      const key = cacheKey(item.type, item.ref)
      if (resolvedRefCache.has(key)) return
      const data = await mutations.resolveRepoRef.mutateAsync({
        repo_url: repoForm.repo_url,
        temporary_token: repoForm.temporary_token || undefined,
        ref_type: item.type,
        ref: item.ref,
      })
      resolvedRefCache.set(key, data)
    }),
  )
}

function applyResolvedRef(data: RepoResolveResponse) {
  if (!inspection.value) return
  inspection.value = {
    ...inspection.value,
    selected_ref_type: data.selected_ref_type,
    selected_ref: data.selected_ref,
    selected_commit: data.selected_commit,
    metadata: data.metadata,
    match: data.match,
  }
  refMode.value = data.selected_ref_type
  if (data.selected_ref_type === 'branch') selectedBranch.value = data.selected_ref
  if (data.selected_ref_type === 'tag') selectedTag.value = data.selected_ref
  if (data.selected_ref_type === 'commit') commitInput.value = data.selected_ref
}

function cacheKey(type: RepoRefType, ref: string | undefined) {
  return `${repoForm.repo_url.trim()}::${type}::${(ref || '').trim()}`
}

async function submit() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    if (mode.value === 'repo') {
      if (!inspection.value) throw new Error('请先检测仓库')
      result.value = await mutations.submit.mutateAsync({
        repo_url: inspection.value.repo_url,
        ref: finalRef.value,
        version: repoForm.version || undefined,
        changelog: repoForm.changelog || undefined,
        temporary_token: repoForm.temporary_token || undefined,
      })
    } else if (file.value) {
      if (!file.value.name.endsWith('.zip')) throw new Error('请选择 .zip 文件')
      result.value = await mutations.upload.mutateAsync(file.value)
    }
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

function reset() {
  result.value = null
  error.value = null
  inspection.value = null
  repoForm.repo_url = ''
  repoForm.temporary_token = ''
  repoForm.version = ''
  repoForm.changelog = ''
  refMode.value = 'default'
  selectedBranch.value = ''
  selectedTag.value = ''
  commitInput.value = ''
  lockToCommit.value = true
  file.value = null
}

function shortSha(value: string | null | undefined) {
  return value ? value.slice(0, 8) : '-'
}

function formatSizeKb(value: number) {
  if (value >= 1024) return `${(value / 1024).toFixed(1)} MiB`
  return `${value} KiB`
}
</script>

<style scoped>
.submit-section {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  display: grid;
  gap: 14px;
  margin-top: 14px;
  padding: 16px;
}

.section-head {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.section-head h3 {
  font-size: 15px;
  line-height: 22px;
  margin: 0;
}

.section-head p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  margin: 2px 0 0;
}

.submit-form {
  display: grid;
  gap: 2px;
}

.form-actions,
.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.repo-url-input :deep(.n-input__input-el),
.final-ref code {
  font-family: var(--font-mono);
}

.repo-summary {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
}

.repo-summary > div {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
}

.repo-summary span,
.final-ref span {
  color: var(--text-secondary);
  font-size: 12px;
}

.repo-summary strong {
  font-size: 14px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.repo-summary small {
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-selector {
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  min-width: 0;
  overflow: hidden;
}

.ref-kind-list {
  background: var(--surface-hover);
  border-right: 1px solid var(--divider);
  display: grid;
  gap: 0;
  padding: 8px;
}

.ref-kind {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--text-primary);
  cursor: pointer;
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 10px 12px;
  text-align: left;
}

.ref-kind:hover:not(:disabled) {
  background: var(--surface);
  border-color: var(--divider);
}

.ref-kind.active {
  background: var(--surface);
  border-color: rgba(24, 118, 240, 0.32);
  box-shadow: inset 3px 0 0 var(--primary-color);
}

.ref-kind:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.ref-kind strong {
  font-size: 13px;
  line-height: 20px;
}

.ref-kind span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

.ref-panel {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 14px;
}

.ref-control {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.ref-control label {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.default-ref {
  align-items: center;
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  min-height: 34px;
  padding: 6px 10px;
}

.default-ref code,
.resolved-commit strong,
.final-ref code {
  font-family: var(--font-mono);
}

.ref-warning {
  color: var(--warning-color);
  font-size: 12px;
  line-height: 18px;
  margin: 0;
}

.resolved-commit,
.ref-submit-mode,
.final-ref {
  border: 1px solid var(--divider);
  border-radius: 8px;
  min-width: 0;
  padding: 10px 12px;
}

.resolved-commit {
  background: var(--surface-hover);
  display: grid;
  gap: 4px;
  transition: opacity 0.16s ease;
}

.resolved-commit.loading {
  opacity: 0.64;
}

.resolved-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.resolved-head span,
.final-ref span {
  color: var(--text-secondary);
  font-size: 12px;
}

.resolved-commit strong {
  font-size: 14px;
  line-height: 20px;
}

.resolved-commit p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-submit-mode {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.ref-submit-mode strong {
  font-size: 13px;
  line-height: 20px;
}

.ref-submit-mode p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  margin: 2px 0 0;
}

.final-ref {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  min-width: 0;
}

.final-ref code,
.default-ref code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .ref-selector {
    grid-template-columns: 1fr;
  }

  .ref-kind-list {
    border-bottom: 1px solid var(--divider);
    border-right: 0;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ref-submit-mode {
    align-items: flex-start;
  }
}

.upload-text {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.result {
  margin-top: 12px;
}
</style>
