<template>
  <n-modal
    :show="show"
    preset="dialog"
    title="提交插件"
    style="width: 640px"
    @update:show="emit('update:show', $event)"
  >
    <n-tabs v-model:value="mode" type="line" animated>
      <n-tab-pane name="repo" tab="GitHub URL">
        <api-error-alert :error="error" />
        <n-form :model="repoForm" label-placement="top" class="submit-form">
          <n-form-item label="Repo URL">
            <n-input
              v-model:value="repoForm.repo_url"
              class="repo-url-input"
              placeholder="https://github.com/owner/repo"
              :input-props="{
                autocomplete: 'off',
                autocapitalize: 'off',
                spellcheck: 'false',
              }"
            />
          </n-form-item>
          <div v-if="repoForm.repo_url" class="repo-url-preview">{{ repoForm.repo_url }}</div>
          <n-grid :cols="2" :x-gap="12">
            <n-form-item-gi label="Ref">
              <n-input v-model:value="repoForm.ref" placeholder="branch / tag / commit" />
            </n-form-item-gi>
            <n-form-item-gi label="Version">
              <n-input v-model:value="repoForm.version" placeholder="留空读取 metadata" />
            </n-form-item-gi>
          </n-grid>
          <n-form-item label="Changelog">
            <n-input v-model:value="repoForm.changelog" type="textarea" :rows="3" />
          </n-form-item>
        </n-form>
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

    <template #action>
      <n-button @click="emit('update:show', false)">关闭</n-button>
      <n-button v-if="result" @click="reset">继续提交</n-button>
      <n-button type="primary" :loading="loading" @click="submit">提交</n-button>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import type { SubmitPluginResponse, VersionSubmitResponse } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import { usePluginMutations } from '@/query/plugins'

defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean] }>()

const mode = ref<'repo' | 'zip'>('repo')
const loading = ref(false)
const error = ref<unknown>(null)
const result = ref<SubmitPluginResponse | VersionSubmitResponse | null>(null)
const resultId = computed(() => {
  if (!result.value) return ''
  if ('plugin_id' in result.value && result.value.plugin_id) return result.value.plugin_id
  if ('version_id' in result.value && result.value.version_id) return result.value.version_id
  return '-'
})
const file = ref<File | null>(null)
const mutations = usePluginMutations()
const repoForm = reactive({
  repo_url: '',
  ref: '',
  version: '',
  changelog: '',
})

function handleFileChange(options: { fileList: Array<{ file?: File | null }> }) {
  file.value = options.fileList[0]?.file || null
}

async function submit() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    if (mode.value === 'repo') {
      result.value = await mutations.submit.mutateAsync({
        repo_url: repoForm.repo_url,
        ref: repoForm.ref || undefined,
        version: repoForm.version || undefined,
        changelog: repoForm.changelog || undefined,
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
  repoForm.repo_url = ''
  repoForm.ref = ''
  repoForm.version = ''
  repoForm.changelog = ''
  file.value = null
}
</script>

<style scoped>
.submit-form {
  margin-top: 8px;
}

.repo-url-input :deep(.n-input__input-el),
.repo-url-preview {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.repo-url-input :deep(.n-input__input-el) {
  line-height: 1.6;
  padding-bottom: 2px;
}

.repo-url-preview {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
  margin: -12px 0 12px;
  white-space: normal;
  word-break: break-all;
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
