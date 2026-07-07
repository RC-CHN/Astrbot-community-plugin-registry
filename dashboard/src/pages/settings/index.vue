<template>
  <page-header title="配置" description="编辑运行时配置覆盖项；部署连接和密钥类配置保持只读" />
  <api-error-alert :error="query.error.value || mutation.error.value" />

  <n-tabs type="line" animated>
    <n-tab-pane v-for="group in groups" :key="group.name" :name="group.name" :tab="group.label">
      <n-data-table
        :columns="columns"
        :data="rowsByGroup(group.name)"
        :loading="query.isLoading.value"
        :pagination="false"
        size="small"
      />
    </n-tab-pane>
    <n-tab-pane name="readonly" tab="只读部署信息">
      <n-data-table :columns="readonlyColumns" :data="readonlyRows" :pagination="false" size="small" />
    </n-tab-pane>
  </n-tabs>

  <n-modal v-model:show="editor.show" preset="dialog" :title="`编辑 ${editor.item?.key || ''}`" style="width: 560px">
    <template v-if="editor.item">
      <n-alert v-if="editor.item.sensitive" type="warning" :bordered="false" class="modal-alert">
        敏感值不会回显。留空保存会清空当前覆盖值。
      </n-alert>
      <n-form label-placement="top">
        <n-form-item label="值">
          <n-switch
            v-if="editor.item.input === 'boolean'"
            v-model:value="editorBooleanValue"
            checked-value="true"
            unchecked-value="false"
          />
          <n-input-number
            v-else-if="editor.item.input === 'number'"
            v-model:value="editorNumberValue"
            :min="0"
            style="width: 100%"
          />
          <n-input
            v-else
            v-model:value="editor.value"
            :type="editor.item.sensitive ? 'password' : 'textarea'"
            :rows="editor.item.input === 'textarea' ? 4 : 1"
            show-password-on="click"
          />
        </n-form-item>
      </n-form>
    </template>
    <template #action>
      <n-button @click="editor.show = false">取消</n-button>
      <n-button type="primary" :loading="mutation.isPending.value" @click="saveEditor">保存</n-button>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, reactive } from 'vue'
import { NButton, NInput, NTag, type DataTableColumns } from 'naive-ui'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import { getSystemConfig, updateSystemConfig } from '@/api/config'
import { queryKeys } from '@/query/keys'

type ConfigInput = 'text' | 'textarea' | 'number' | 'boolean'
type ConfigScope = '即时生效' | '新任务生效' | '新产物生效' | '扫描时生效'
type ConfigItem = {
  key: string
  label: string
  group: string
  input: ConfigInput
  scope: ConfigScope
  description: string
  sensitive?: boolean
}
type ConfigRow = ConfigItem & {
  value: string
  effectiveValue: string
  overridden: boolean
  sensitiveSet: boolean
}
type ReadonlyRow = {
  key: string
  value: string
}

const query = useQuery({ queryKey: queryKeys.config.system(), queryFn: getSystemConfig })
const queryClient = useQueryClient()
const mutation = useMutation({
  mutationFn: updateSystemConfig,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.config.system() }),
})

const groups = [
  { name: 'registry', label: '插件源' },
  { name: 'limits', label: '上传与构建' },
  { name: 'git', label: 'Git' },
  { name: 'scan', label: '扫描' },
  { name: 'worker', label: 'Worker' },
  { name: 'webhook', label: 'Webhook' },
]

const editableItems: ConfigItem[] = [
  {
    key: 'PUBLIC_CACHE_MAX_AGE',
    label: '公开缓存时间',
    group: 'registry',
    input: 'number',
    scope: '即时生效',
    description: '公开插件索引响应的 Cache-Control max-age。',
  },
  {
    key: 'REDIS_CACHE_TTL',
    label: 'Redis 缓存 TTL',
    group: 'registry',
    input: 'number',
    scope: '即时生效',
    description: '插件源 JSON 和 MD5 的 Redis 缓存时间。',
  },
  {
    key: 'S3_PUBLIC_URL',
    label: 'S3 公开 URL',
    group: 'registry',
    input: 'text',
    scope: '即时生效',
    description: '公开索引中 logo / 新产物 download_url 使用的外部访问地址。',
  },
  {
    key: 'S3_PLUGINS_PREFIX',
    label: '插件对象前缀',
    group: 'registry',
    input: 'text',
    scope: '新产物生效',
    description: '新上传插件包在 S3 中的对象路径前缀。',
  },
  {
    key: 'S3_UNKNOWN_AUTHOR',
    label: '未知作者占位',
    group: 'registry',
    input: 'text',
    scope: '新产物生效',
    description: '构造 S3 key 时作者为空的占位值。',
  },
  {
    key: 'MAX_UPLOAD_BYTES',
    label: '最大上传大小',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: '手动上传 ZIP 的最大字节数。',
  },
  {
    key: 'MAX_UNZIP_BYTES',
    label: '最大解压大小',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: 'ZIP 解压后的总大小上限。',
  },
  {
    key: 'MAX_ZIP_ENTRIES',
    label: '最大文件数',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: 'ZIP 内文件数量上限。',
  },
  {
    key: 'MAX_SINGLE_FILE_BYTES',
    label: '单文件大小上限',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: 'ZIP 内单个文件大小上限。',
  },
  {
    key: 'MAX_RELEASE_ZIP_BYTES',
    label: '构建产物大小上限',
    group: 'limits',
    input: 'number',
    scope: '新任务生效',
    description: '从 Git repo 打包出的 release zip 大小上限。',
  },
  {
    key: 'GIT_ALLOWED_HOSTS',
    label: '允许的 Git Host',
    group: 'git',
    input: 'text',
    scope: '即时生效',
    description: '逗号分隔，例如 github.com,git.example.com。',
  },
  {
    key: 'GIT_CLONE_TIMEOUT',
    label: 'Clone 超时',
    group: 'git',
    input: 'number',
    scope: '即时生效',
    description: 'Git clone 超时时间，单位秒。',
  },
  {
    key: 'SCAN_PASS_WHEN_UNCONFIGURED',
    label: '扫描未配置时放行',
    group: 'scan',
    input: 'boolean',
    scope: '扫描时生效',
    description: '真实扫描 API 未配置时是否允许扫描占位通过。',
  },
  {
    key: 'SCAN_UNCONFIGURED_MESSAGE',
    label: '扫描未配置提示',
    group: 'scan',
    input: 'text',
    scope: '扫描时生效',
    description: '扫描服务未配置时写入的提示文本。',
  },
  {
    key: 'VIRUSTOTAL_TIMEOUT_SECONDS',
    label: 'VirusTotal 请求超时',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: 'VirusTotal 上传和查询请求的超时时间，单位秒。',
  },
  {
    key: 'VIRUSTOTAL_POLL_INTERVAL_SECONDS',
    label: 'VirusTotal 初始轮询间隔',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: '分析未完成时第一次延迟查询的等待时间，后续会指数退避，单位秒。',
  },
  {
    key: 'VIRUSTOTAL_MAX_POLL_INTERVAL_SECONDS',
    label: 'VirusTotal 最大轮询间隔',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: '指数退避后的最大单次等待时间，默认可退避到 320 秒。',
  },
  {
    key: 'VIRUSTOTAL_MAX_POLL_ATTEMPTS',
    label: 'VirusTotal 最大轮询次数',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: '超过次数或最大等待时长仍未完成时记录为扫描超时。',
  },
  {
    key: 'VIRUSTOTAL_MAX_WAIT_SECONDS',
    label: 'VirusTotal 最大等待时长',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: '从提交分析开始到放弃等待的最长时长，单位秒。',
  },
  {
    key: 'VIRUSTOTAL_MAX_DIRECT_UPLOAD_BYTES',
    label: 'VirusTotal 直传上限',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: '超过该大小的文件不走直传扫描，单位字节。',
  },
  {
    key: 'LLM_AGENT_ENABLED',
    label: '启用 LLM Agent',
    group: 'scan',
    input: 'boolean',
    scope: '扫描时生效',
    description: '后续接入 LLM 扫描时使用。',
  },
  {
    key: 'LLM_AGENT_BASE_URL',
    label: 'LLM 接口地址',
    group: 'scan',
    input: 'text',
    scope: '扫描时生效',
    description: 'OpenAI-compatible completion/chat completion 接口根地址，请填写到 /v1。',
  },
  {
    key: 'LLM_AGENT_MODEL',
    label: 'LLM 模型名称',
    group: 'scan',
    input: 'text',
    scope: '扫描时生效',
    description: '用于 LLM 扫描的模型名称。',
  },
  {
    key: 'LLM_AGENT_MAX_CONTEXT_CHARS',
    label: 'LLM 最大上下文字符',
    group: 'scan',
    input: 'number',
    scope: '扫描时生效',
    description: '发送给 LLM 的插件摘要最大字符数，超出后自动截断并注明。',
  },
  {
    key: 'TASK_MAX_ATTEMPTS',
    label: '任务最大尝试次数',
    group: 'worker',
    input: 'number',
    scope: '新任务生效',
    description: '构建/扫描任务失败后的最大尝试次数。',
  },
  {
    key: 'TASK_RETRY_DELAY_SECONDS',
    label: '任务重试延迟',
    group: 'worker',
    input: 'number',
    scope: '新任务生效',
    description: '任务失败后再次入队前等待的秒数。',
  },
  {
    key: 'WEBHOOK_AUTO_VERSION',
    label: 'Webhook 自动版本',
    group: 'webhook',
    input: 'text',
    scope: '即时生效',
    description: 'Push webhook 无法获知版本时使用的占位版本。',
  },
  {
    key: 'GITHUB_WEBHOOK_SECRET',
    label: 'GitHub Webhook Secret',
    group: 'webhook',
    input: 'text',
    scope: '即时生效',
    description: '敏感值，只允许写入，不回显明文。',
    sensitive: true,
  },
  {
    key: 'VIRUSTOTAL_API_KEY',
    label: 'VirusTotal API Key',
    group: 'scan',
    input: 'text',
    scope: '扫描时生效',
    description: '敏感值，只允许写入，不回显明文。',
    sensitive: true,
  },
  {
    key: 'LLM_AGENT_API_KEY',
    label: 'LLM Agent API Key',
    group: 'scan',
    input: 'text',
    scope: '扫描时生效',
    description: '敏感值，只允许写入，不回显明文。',
    sensitive: true,
  },
]

const readonlyRows = computed<ReadonlyRow[]>(() =>
  Object.entries(query.data.value?.deployment_values || {}).map(([key, value]) => ({ key, value })),
)

const editor = reactive<{
  show: boolean
  item: ConfigRow | null
  value: string
}>({
  show: false,
  item: null,
  value: '',
})

const editorNumberValue = computed({
  get: () => Number(editor.value || 0),
  set: (value: number | null) => {
    editor.value = value === null ? '' : String(value)
  },
})

const editorBooleanValue = computed({
  get: () => editor.value || 'false',
  set: (value: string) => {
    editor.value = value
  },
})

const rows = computed<ConfigRow[]>(() => {
  const values = query.data.value?.values || {}
  const effectiveValues = query.data.value?.effective_values || {}
  const sensitiveStatus = query.data.value?.sensitive_status || {}
  return editableItems.map((item) => ({
    ...item,
    value: values[item.key] || '',
    effectiveValue: effectiveValues[item.key] || '',
    overridden: Object.prototype.hasOwnProperty.call(values, item.key),
    sensitiveSet: Boolean(sensitiveStatus[item.key]),
  }))
})

function rowsByGroup(group: string) {
  return rows.value.filter((item) => item.group === group)
}

const columns: DataTableColumns<ConfigRow> = [
  {
    title: '配置项',
    key: 'label',
    width: 260,
    render(row) {
      return h('div', [h('div', { class: 'config-label' }, row.label), h('div', { class: 'muted mono' }, row.key)])
    },
  },
  {
    title: '当前生效值',
    key: 'value',
    render(row) {
      if (row.sensitive) {
        return h(NTag, { size: 'small', round: true }, { default: () => (row.sensitiveSet ? '已设置' : '未设置') })
      }
      return h(NInput, {
        value: row.effectiveValue || '-',
        readonly: true,
        type: row.input === 'textarea' ? 'textarea' : 'text',
      })
    },
  },
  {
    title: '覆盖状态',
    key: 'overridden',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: row.overridden ? 'info' : 'default', size: 'small', round: true },
        { default: () => (row.overridden ? '已覆盖' : '默认') },
      )
    },
  },
  {
    title: '生效范围',
    key: 'scope',
    width: 130,
    render(row) {
      return h(NTag, { type: 'success', size: 'small', round: true }, { default: () => row.scope })
    },
  },
  { title: '说明', key: 'description' },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    align: 'right',
    render(row) {
      return h(NButton, { size: 'small', onClick: () => openEditor(row) }, { default: () => '编辑' })
    },
  },
]

const readonlyColumns: DataTableColumns<ReadonlyRow> = [
  { title: '配置项', key: 'key', width: 320 },
  { title: '当前值', key: 'value' },
]

function openEditor(row: ConfigRow) {
  editor.item = row
  editor.value = row.sensitive ? '' : row.effectiveValue
  editor.show = true
}

async function saveEditor() {
  if (!editor.item) return
  await mutation.mutateAsync({ [editor.item.key]: editor.value })
  editor.show = false
}
</script>

<style scoped>
.config-label {
  font-weight: 600;
}

.modal-alert {
  margin-bottom: 12px;
}
</style>
