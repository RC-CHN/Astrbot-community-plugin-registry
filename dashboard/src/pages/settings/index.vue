<template>
  <page-header
    title="配置"
    description="运行时覆盖项会即时写入数据库；敏感值只显示配置状态，不回显明文。"
  />
  <api-error-alert :error="query.error.value || mutation.error.value" />

  <div class="settings-shell" :class="{ 'provider-view': activeSection === 'providers' }">
    <aside class="settings-nav" aria-label="配置分组">
      <button
        v-for="item in settingsNavItems"
        :key="item.key"
        class="settings-nav-item"
        :class="{ active: activeSection === item.key }"
        type="button"
        @click="activeSection = item.key"
      >
        <span>
          <strong>{{ item.label }}</strong>
          <small>{{ item.description }}</small>
        </span>
      </button>
    </aside>

    <main class="settings-main">
      <div v-if="activeSection === 'registry'" class="section-stack">
        <settings-panel
          title="插件源"
          description="公开索引、缓存和新产物 URL。"
          :groups="registryPanelGroups"
          :get-value="fieldValue"
          :is-dirty="isDirty"
          :is-overridden="fieldOverridden"
          :is-sensitive-configured="fieldSensitiveConfigured"
          :is-loading="fieldLoading"
          :can-clear="fieldCanClear"
          :provider-options="providerOptions"
          @update-value="setDraft"
          @clear="clearOverride"
        />
      </div>

      <div v-else-if="activeSection === 'build'" class="section-stack">
        <settings-panel
          title="上传与构建"
          description="包体限制、仓库预检和 Git 拉取参数。"
          :groups="buildPanelGroups"
          :get-value="fieldValue"
          :is-dirty="isDirty"
          :is-overridden="fieldOverridden"
          :is-sensitive-configured="fieldSensitiveConfigured"
          :is-loading="fieldLoading"
          :can-clear="fieldCanClear"
          :provider-options="providerOptions"
          @update-value="setDraft"
          @clear="clearOverride"
        />
      </div>

      <div v-else-if="activeSection === 'scan'" class="section-stack">
        <section class="settings-section">
          <header class="section-head">
            <div>
              <h2>扫描策略</h2>
              <p>机器扫描 provider 统一由启用列表控制；人工审核作为最后一道发布门禁。</p>
            </div>
            <n-tag size="small" round :type="humanReviewRequired ? 'warning' : 'success'">
              {{ humanReviewRequired ? '人工审核开启' : '可自动发布' }}
            </n-tag>
          </header>

          <n-alert v-if="enabledProviders.length === 0" type="warning" :bordered="false" class="section-alert">
            当前没有启用机器扫描 provider。发布仍会受人工审核和已有扫描结果约束。
          </n-alert>

          <div class="settings-groups">
            <div class="settings-group">
              <header class="group-head">
                <h3>发布门禁</h3>
                <p>控制未配置 provider 的占位结果、人工审核和自动发布。</p>
              </header>
              <div class="field-list">
                <setting-field
                  v-for="item in scanPolicyItems"
                  :key="item.key"
                  :item="item"
                  :value="fieldValue(item)"
                  :dirty="isDirty(item)"
                  :overridden="fieldOverridden(item)"
                  :sensitive-configured="fieldSensitiveConfigured(item)"
                  :loading="fieldLoading(item)"
                  :can-clear="fieldCanClear(item)"
                  :provider-options="providerOptions"
                  @update-value="setDraft(item, $event)"
                  @clear="clearOverride(item)"
                />
              </div>
            </div>
          </div>

          <n-alert v-if="humanReviewRequired" type="info" :bordered="false" class="section-alert">
            需要人工审核时，自动发布开关会隐藏且不会生效。
          </n-alert>
        </section>
      </div>

      <div v-else-if="activeSection === 'providers'" class="section-stack">
        <section class="settings-section">
          <header class="section-head">
            <div>
              <h2>扫描 Provider</h2>
              <p>只勾选实际要运行的扫描器；未启用 provider 不调度，也不阻断发布。</p>
            </div>
            <n-tag size="small" round :type="enabledProviders.length ? 'info' : 'default'">
              {{ enabledProviderSummary }}
            </n-tag>
          </header>

          <n-checkbox-group
            class="provider-choice-group"
            :value="csvToList(draftValue(providerPolicyItem.key))"
            @update:value="setProviderDraft(providerPolicyItem, $event)"
          >
            <div class="provider-choice-grid">
              <n-checkbox
                v-for="option in providerOptions"
                :key="option.value"
                class="provider-choice"
                :value="option.value"
              >
                <span class="provider-choice-copy">
                  <strong>{{ option.label }}</strong>
                  <small>{{ providerHint(option.value) }}</small>
                </span>
              </n-checkbox>
            </div>
          </n-checkbox-group>

          <div v-if="isDirty(providerPolicyItem) || isOverridden(providerPolicyItem.key)" class="section-actions">
            <n-button
              size="small"
              type="primary"
              :disabled="!isDirty(providerPolicyItem)"
              :loading="savingKey === providerPolicyItem.key"
              @click="saveItem(providerPolicyItem)"
            >
              <template #icon><n-icon :component="Save" /></template>
              保存启用列表
            </n-button>
            <n-button
              size="small"
              secondary
              :disabled="savingKey === providerPolicyItem.key || !isOverridden(providerPolicyItem.key)"
              @click="clearOverride(providerPolicyItem)"
            >
              <template #icon><n-icon :component="RotateCcw" /></template>
              恢复默认
            </n-button>
          </div>
        </section>

        <div class="provider-status-grid">
          <article
            v-for="provider in providerPanels"
            :key="provider.name"
            class="provider-status"
            :class="{ inactive: !provider.enabled }"
          >
            <header>
              <span class="status-dot" :class="{ ok: provider.enabled && provider.configured, warn: provider.enabled && !provider.configured }" />
              <strong>{{ provider.label }}</strong>
              <n-tag :type="provider.enabled ? (provider.configured ? 'success' : 'warning') : 'default'" size="small" round>
                {{ provider.enabled ? (provider.configured ? '就绪' : '待配置') : '未启用' }}
              </n-tag>
            </header>
            <p>{{ provider.description }}</p>
          </article>
        </div>

        <template v-for="provider in providerPanels" :key="provider.name">
          <section v-if="provider.enabled" class="settings-section">
            <header class="section-head">
              <div>
                <h2>{{ provider.label }} 参数</h2>
                <p>{{ provider.description }}</p>
              </div>
              <n-tag :type="provider.configured ? 'success' : 'warning'" size="small" round>
                {{ provider.configured ? '配置完整' : '待配置' }}
              </n-tag>
            </header>

            <div class="field-list">
              <setting-field
                v-for="item in provider.basic"
                :key="item.key"
                :item="item"
                :value="fieldValue(item)"
                :dirty="isDirty(item)"
                :overridden="fieldOverridden(item)"
                :sensitive-configured="fieldSensitiveConfigured(item)"
                :loading="fieldLoading(item)"
                :can-clear="fieldCanClear(item)"
                :provider-options="providerOptions"
                @update-value="setDraft(item, $event)"
                @clear="clearOverride(item)"
              />
            </div>

            <n-collapse v-if="provider.advanced.length" class="advanced-collapse">
              <n-collapse-item title="高级参数" name="advanced">
                <div class="field-list">
                  <setting-field
                    v-for="item in provider.advanced"
                    :key="item.key"
                    :item="item"
                    :value="fieldValue(item)"
                    :dirty="isDirty(item)"
                    :overridden="fieldOverridden(item)"
                    :sensitive-configured="fieldSensitiveConfigured(item)"
                    :loading="fieldLoading(item)"
                    :can-clear="fieldCanClear(item)"
                    :provider-options="providerOptions"
                    @update-value="setDraft(item, $event)"
                    @clear="clearOverride(item)"
                  />
                </div>
              </n-collapse-item>
            </n-collapse>
          </section>
        </template>
      </div>

      <div v-else-if="activeSection === 'ops'" class="section-stack">
        <settings-panel
          title="Worker / Webhook"
          description="任务重试和 GitHub push 事件处理。"
          :groups="opsPanelGroups"
          :get-value="fieldValue"
          :is-dirty="isDirty"
          :is-overridden="fieldOverridden"
          :is-sensitive-configured="fieldSensitiveConfigured"
          :is-loading="fieldLoading"
          :can-clear="fieldCanClear"
          :provider-options="providerOptions"
          @update-value="setDraft"
          @clear="clearOverride"
        />
      </div>

      <div v-else class="section-stack">
        <section class="settings-section">
          <header class="section-head">
            <div>
              <h2>部署环境</h2>
              <p>这些值来自进程环境，只读展示；敏感内容已做遮蔽。</p>
            </div>
          </header>
          <div class="readonly-grid">
            <article v-for="row in readonlyRows" :key="row.key" class="readonly-item">
              <span>{{ row.key }}</span>
              <strong>{{ row.value || '-' }}</strong>
            </article>
          </div>
        </section>
      </div>

      <div v-if="dirtyItems.length" class="settings-save-bar">
        <div>
          <strong>{{ dirtyItems.length }} 项未保存</strong>
          <span>修改只保存在当前页面，保存后才写入运行时配置。</span>
        </div>
        <div class="save-bar-actions">
          <n-button secondary :disabled="savingKey === dirtySaveKey" @click="discardDirtyItems">
            <template #icon><n-icon :component="RotateCcw" /></template>
            放弃更改
          </n-button>
          <n-button type="primary" :loading="savingKey === dirtySaveKey" @click="saveDirtyItems">
            <template #icon><n-icon :component="Save" /></template>
            保存修改
          </n-button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { NButton, NCheckbox, NCheckboxGroup, NIcon, NTag, useMessage } from 'naive-ui'
import {
  FileJson,
  GitBranch,
  RotateCcw,
  Save,
  ScanSearch,
  ServerCog,
  ShieldCheck,
  Webhook,
} from 'lucide-vue-next'

import { getSystemConfig, updateSystemConfig } from '@/api/config'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import { queryKeys } from '@/query/keys'
import SettingField from './components/setting-field.vue'
import SettingsPanel from './components/settings-panel.vue'
import type { ConfigGroup, ConfigItem, ProviderOption, SettingsGroup, SettingsNavItem, SettingsViewKey } from './types'

type ReadonlyRow = {
  key: string
  value: string
}

type ProviderPanel = {
  name: string
  label: string
  description: string
  enabled: boolean
  configured: boolean
  basic: ConfigItem[]
  advanced: ConfigItem[]
}

const query = useQuery({ queryKey: queryKeys.config.system(), queryFn: getSystemConfig })
const queryClient = useQueryClient()
const message = useMessage()
const savingKey = ref<string | null>(null)
const activeSection = ref<SettingsViewKey>('scan')
const dirtySaveKey = '__dirty_settings__'
const drafts = reactive<Record<string, string>>({})
const dirty = reactive<Record<string, boolean>>({})

const mutation = useMutation({
  mutationFn: updateSystemConfig,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.config.system() }),
})

const providerOptions: ProviderOption[] = [
  { label: 'VirusTotal', value: 'virustotal' },
  { label: 'LLM Agent', value: 'llm_agent' },
  { label: 'ClamAV', value: 'clamav' },
]

const settingsNavItems: SettingsNavItem[] = [
  { key: 'registry', label: '插件源', description: '公开索引与对象地址', icon: FileJson },
  { key: 'build', label: '上传与构建', description: '包体限制和 Git 拉取', icon: GitBranch },
  { key: 'scan', label: '扫描策略', description: '发布门禁和自动发布', icon: ShieldCheck },
  { key: 'providers', label: 'Provider', description: '扫描器启用与参数', icon: ScanSearch },
  { key: 'ops', label: 'Worker / Webhook', description: '任务重试和推送事件', icon: Webhook },
  { key: 'deployment', label: '部署环境', description: '只读环境变量快照', icon: ServerCog },
]

const editableItems: ConfigItem[] = [
  {
    key: 'PUBLIC_CACHE_MAX_AGE',
    label: '公开缓存时间',
    group: 'registry',
    input: 'number',
    scope: '即时生效',
    description: '公开插件索引响应的 Cache-Control max-age，单位秒。',
    min: 0,
    unit: '秒',
  },
  {
    key: 'REDIS_CACHE_TTL',
    label: 'Redis 缓存 TTL',
    group: 'registry',
    input: 'number',
    scope: '即时生效',
    description: '插件源 JSON 和 MD5 的 Redis 缓存时间，单位秒。',
    min: 0,
    unit: '秒',
  },
  {
    key: 'S3_PUBLIC_URL',
    label: 'S3 公开 URL',
    group: 'registry',
    input: 'text',
    scope: '即时生效',
    description: '公开索引中 logo 和新产物 download_url 使用的外部访问地址。',
    placeholder: 'https://registry.example.com/s3/astrbot-plugins',
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
    min: 1,
    unit: 'bytes',
  },
  {
    key: 'MAX_UNZIP_BYTES',
    label: '最大解压大小',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: 'ZIP 解压后的总大小上限。',
    min: 1,
    unit: 'bytes',
  },
  {
    key: 'MAX_ZIP_ENTRIES',
    label: '最大文件数',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: 'ZIP 内文件数量上限。',
    min: 1,
    unit: 'files',
  },
  {
    key: 'MAX_SINGLE_FILE_BYTES',
    label: '单文件大小上限',
    group: 'limits',
    input: 'number',
    scope: '即时生效',
    description: 'ZIP 内单个文件大小上限。',
    min: 1,
    unit: 'bytes',
  },
  {
    key: 'MAX_RELEASE_ZIP_BYTES',
    label: '构建产物大小上限',
    group: 'limits',
    input: 'number',
    scope: '新任务生效',
    description: '从 Git repo 打包出的 release zip 大小上限。',
    min: 1,
    unit: 'bytes',
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
    description: 'Git clone 超时时间。',
    min: 1,
    unit: '秒',
  },
  {
    key: 'GIT_PREFLIGHT_TIMEOUT',
    label: '仓库预检超时',
    group: 'git',
    input: 'number',
    scope: '即时生效',
    description: 'GitHub 仓库元数据预检超时时间。',
    min: 1,
    unit: '秒',
  },
  {
    key: 'GIT_MAX_REPO_SIZE_KB',
    label: '仓库大小上限',
    group: 'git',
    input: 'number',
    scope: '即时生效',
    description: 'Clone 前允许的最大 GitHub 仓库大小，设为 0 可关闭大小预检。',
    min: 0,
    unit: 'KiB',
  },
  {
    key: 'GIT_HTTP_PROXY',
    label: 'Git HTTP 代理',
    group: 'git',
    input: 'text',
    scope: '即时生效',
    description: '可选 HTTP/HTTPS clone 代理；敏感值不回显。',
    sensitive: true,
    placeholder: 'http://user:pass@proxy.example:8080',
  },
  {
    key: 'GITHUB_TOKEN',
    label: 'GitHub 全局 Token',
    group: 'git',
    input: 'text',
    scope: '即时生效',
    description: '用于公开仓库预检、Ref 解析和 clone，避免匿名 API 限流；提交时填写的临时 Token 优先生效。',
    sensitive: true,
    placeholder: 'github_pat_...',
  },
  {
    key: 'SCAN_ENABLED_PROVIDERS',
    label: '启用 provider',
    group: 'scan-policy',
    input: 'providers',
    scope: '扫描时生效',
    description: '唯一的机器扫描启用来源。未勾选的 provider 不调度，也不阻断发布。',
  },
  {
    key: 'SCAN_PASS_WHEN_UNCONFIGURED',
    label: '未配置时放行',
    group: 'scan-policy',
    input: 'boolean',
    scope: '扫描时生效',
    description: '启用的 provider 缺少密钥或连接参数时，是否把占位结果记为通过。',
  },
  {
    key: 'SCAN_UNCONFIGURED_MESSAGE',
    label: '未配置提示',
    group: 'scan-policy',
    input: 'text',
    scope: '扫描时生效',
    description: 'provider 未配置时写入扫描结果的提示文本。',
  },
  {
    key: 'SCAN_REQUIRE_HUMAN_REVIEW',
    label: '需要人工审核',
    group: 'scan-policy',
    input: 'boolean',
    scope: '扫描时生效',
    description: '开启后，机器扫描全通过也会停在待审核，等待管理员发布。',
  },
  {
    key: 'SCAN_AUTO_PUBLISH_ENABLED',
    label: '扫描通过自动发布',
    group: 'scan-policy',
    input: 'boolean',
    scope: '扫描时生效',
    description: '只在关闭人工审核时显示并生效；启用 provider 全通过后自动发布当前版本。',
  },
  {
    key: 'VIRUSTOTAL_API_KEY',
    label: 'API Key',
    group: 'virustotal',
    input: 'text',
    scope: '扫描时生效',
    description: 'VirusTotal API Key；敏感值只允许写入，不回显明文。',
    sensitive: true,
  },
  {
    key: 'VIRUSTOTAL_TIMEOUT_SECONDS',
    label: '请求超时',
    group: 'virustotal',
    input: 'number',
    scope: '扫描时生效',
    description: 'VirusTotal 上传和查询请求的超时时间。',
    advanced: true,
    min: 1,
    unit: '秒',
  },
  {
    key: 'VIRUSTOTAL_POLL_INTERVAL_SECONDS',
    label: '初始轮询间隔',
    group: 'virustotal',
    input: 'number',
    scope: '扫描时生效',
    description: '分析未完成时第一次延迟查询的等待时间，后续会指数退避。',
    advanced: true,
    min: 1,
    unit: '秒',
  },
  {
    key: 'VIRUSTOTAL_MAX_POLL_INTERVAL_SECONDS',
    label: '最大轮询间隔',
    group: 'virustotal',
    input: 'number',
    scope: '扫描时生效',
    description: '指数退避后的最大单次等待时间。',
    advanced: true,
    min: 1,
    unit: '秒',
  },
  {
    key: 'VIRUSTOTAL_MAX_POLL_ATTEMPTS',
    label: '最大轮询次数',
    group: 'virustotal',
    input: 'number',
    scope: '扫描时生效',
    description: '超过次数或最大等待时长仍未完成时记录为扫描超时。',
    advanced: true,
    min: 1,
    unit: '次',
  },
  {
    key: 'VIRUSTOTAL_MAX_WAIT_SECONDS',
    label: '最大等待时长',
    group: 'virustotal',
    input: 'number',
    scope: '扫描时生效',
    description: '从提交分析开始到放弃等待的最长时长。',
    advanced: true,
    min: 1,
    unit: '秒',
  },
  {
    key: 'VIRUSTOTAL_MAX_DIRECT_UPLOAD_BYTES',
    label: '直传上限',
    group: 'virustotal',
    input: 'number',
    scope: '扫描时生效',
    description: '超过该大小的文件不走直传扫描。',
    advanced: true,
    min: 1,
    unit: 'bytes',
  },
  {
    key: 'CLAMAV_HOST',
    label: 'Host',
    group: 'clamav',
    input: 'text',
    scope: '扫描时生效',
    description: 'backend 和 worker 可访问的 clamd 主机名或 IP。',
  },
  {
    key: 'CLAMAV_PORT',
    label: '端口',
    group: 'clamav',
    input: 'number',
    scope: '扫描时生效',
    description: 'clamd TCP 端口。',
    min: 1,
  },
  {
    key: 'CLAMAV_TIMEOUT_SECONDS',
    label: '扫描超时',
    group: 'clamav',
    input: 'number',
    scope: '扫描时生效',
    description: '单次 ClamAV 扫描最长等待时间。',
    advanced: true,
    min: 1,
    unit: '秒',
  },
  {
    key: 'CLAMAV_STREAM_CHUNK_BYTES',
    label: '分块大小',
    group: 'clamav',
    input: 'number',
    scope: '扫描时生效',
    description: 'clamd INSTREAM 上传分块大小。',
    advanced: true,
    min: 1,
    unit: 'bytes',
  },
  {
    key: 'CLAMAV_MAX_STREAM_BYTES',
    label: '扫描上限',
    group: 'clamav',
    input: 'number',
    scope: '扫描时生效',
    description: '允许发送给 clamd 的最大插件包大小。',
    advanced: true,
    min: 1,
    unit: 'bytes',
  },
  {
    key: 'LLM_AGENT_BASE_URL',
    label: '接口地址',
    group: 'llm',
    input: 'text',
    scope: '扫描时生效',
    description: 'OpenAI-compatible 接口根地址，请填写到 /v1。',
    placeholder: 'https://api.example.com/v1',
  },
  {
    key: 'LLM_AGENT_MODEL',
    label: '模型名称',
    group: 'llm',
    input: 'text',
    scope: '扫描时生效',
    description: '用于 LLM 扫描的模型名称。',
  },
  {
    key: 'LLM_AGENT_API_KEY',
    label: 'API Key',
    group: 'llm',
    input: 'text',
    scope: '扫描时生效',
    description: 'LLM 接口密钥；敏感值只允许写入，不回显明文。',
    sensitive: true,
  },
  {
    key: 'LLM_AGENT_MAX_CONTEXT_CHARS',
    label: '最大上下文字符',
    group: 'llm',
    input: 'number',
    scope: '扫描时生效',
    description: '发送给 LLM 的插件摘要最大字符数，超出会截断。',
    advanced: true,
    min: 1,
    unit: 'chars',
  },
  {
    key: 'TASK_MAX_ATTEMPTS',
    label: '任务最大尝试次数',
    group: 'worker',
    input: 'number',
    scope: '新任务生效',
    description: '构建/扫描任务失败后的最大尝试次数。',
    min: 1,
  },
  {
    key: 'TASK_RETRY_DELAY_SECONDS',
    label: '任务重试延迟',
    group: 'worker',
    input: 'number',
    scope: '新任务生效',
    description: '任务失败后再次入队前等待的秒数。',
    min: 0,
    unit: '秒',
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
    description: 'GitHub webhook 签名密钥；敏感值只允许写入，不回显明文。',
    sensitive: true,
  },
]

const readonlyRows = computed<ReadonlyRow[]>(() =>
  Object.entries(query.data.value?.deployment_values || {}).map(([key, value]) => ({ key, value })),
)

const values = computed(() => query.data.value?.values || {})
const effectiveValues = computed(() => query.data.value?.effective_values || {})
const sensitiveStatus = computed(() => query.data.value?.sensitive_status || {})

const providerPolicyItem = computed(
  () => editableItems.find((item) => item.key === 'SCAN_ENABLED_PROVIDERS') as ConfigItem,
)
const enabledProviders = computed(() => csvToList(draftValue('SCAN_ENABLED_PROVIDERS')))
const enabledProviderSummary = computed(() =>
  enabledProviders.value.length ? `${enabledProviders.value.length} 个已启用` : '未启用机器扫描',
)
const humanReviewRequired = computed(() => booleanDraftValue('SCAN_REQUIRE_HUMAN_REVIEW'))
const scanPolicyItems = computed(() =>
  visibleItemsByGroup('scan-policy').filter((item) => item.key !== 'SCAN_ENABLED_PROVIDERS'),
)
const dirtyItems = computed(() => editableItems.filter((item) => item.key !== 'SCAN_ENABLED_PROVIDERS' && isDirty(item)))
const registryPanelGroups = computed<SettingsGroup[]>(() => [
  {
    title: '公开索引与对象地址',
    description: '控制公开插件索引缓存，以及新产物在插件源中暴露的 URL。',
    items: itemsByGroup('registry'),
  },
])
const buildPanelGroups = computed<SettingsGroup[]>(() => [
  {
    title: '上传限制',
    description: '手动上传 ZIP、解压和发布产物的硬限制。',
    items: itemsByGroup('limits'),
  },
  {
    title: 'Git 拉取',
    description: '仓库提交和构建任务使用；仓库大小预检仅支持 GitHub。',
    items: itemsByGroup('git'),
  },
])
const opsPanelGroups = computed<SettingsGroup[]>(() => [
  {
    title: 'Worker 队列',
    description: '影响后续入队任务，不会修改已经执行中的任务。',
    items: itemsByGroup('worker'),
  },
  {
    title: 'GitHub Webhook',
    description: 'Webhook 只用于已注册插件的 push 事件；Secret 不会回显。',
    items: itemsByGroup('webhook'),
  },
])

const providerPanels = computed<ProviderPanel[]>(() => [
  {
    name: 'virustotal',
    label: 'VirusTotal',
    description: '基于 VirusTotal 文件分析结果判断恶意或可疑命中。',
    enabled: providerEnabled('virustotal'),
    configured: sensitiveConfigured('VIRUSTOTAL_API_KEY'),
    basic: itemsByGroup('virustotal').filter((item) => !item.advanced),
    advanced: itemsByGroup('virustotal').filter((item) => item.advanced),
  },
  {
    name: 'llm_agent',
    label: 'LLM Agent',
    description: '用 OpenAI-compatible 模型对插件源码做语义安全审查。',
    enabled: providerEnabled('llm_agent'),
    configured:
      Boolean(draftValue('LLM_AGENT_BASE_URL')) &&
      Boolean(draftValue('LLM_AGENT_MODEL')) &&
      sensitiveConfigured('LLM_AGENT_API_KEY'),
    basic: itemsByGroup('llm').filter((item) => !item.advanced),
    advanced: itemsByGroup('llm').filter((item) => item.advanced),
  },
  {
    name: 'clamav',
    label: 'ClamAV',
    description: '连接自托管 clamd，通过 INSTREAM 扫描插件压缩包。',
    enabled: providerEnabled('clamav'),
    configured: Boolean(draftValue('CLAMAV_HOST')) && Number(draftValue('CLAMAV_PORT') || 0) > 0,
    basic: itemsByGroup('clamav').filter((item) => !item.advanced),
    advanced: itemsByGroup('clamav').filter((item) => item.advanced),
  },
])

watch(
  () => query.data.value,
  () => {
    for (const item of editableItems) {
      if (!dirty[item.key]) {
        drafts[item.key] = item.sensitive ? '' : effectiveValue(item.key)
      }
    }
  },
  { immediate: true },
)

function itemsByGroup(group: ConfigGroup) {
  return editableItems.filter((item) => item.group === group)
}

function visibleItemsByGroup(group: ConfigGroup) {
  return itemsByGroup(group).filter((item) => {
    if (item.key === 'SCAN_AUTO_PUBLISH_ENABLED') {
      return !humanReviewRequired.value
    }
    return true
  })
}

function effectiveValue(key: string) {
  return effectiveValues.value[key] || ''
}

function savedValue(item: ConfigItem) {
  return item.sensitive ? '' : effectiveValue(item.key)
}

function draftValue(key: string) {
  if (Object.prototype.hasOwnProperty.call(drafts, key)) {
    return drafts[key]
  }
  return effectiveValue(key)
}

function setDraft(item: ConfigItem, value: string) {
  drafts[item.key] = value
  dirty[item.key] = item.sensitive ? value.length > 0 : value !== savedValue(item)
}

function setProviderDraft(item: ConfigItem, value: Array<string | number>) {
  setDraft(item, value.map(String).join(','))
}

function booleanDraftValue(key: string) {
  return ['1', 'true', 'yes', 'on'].includes(draftValue(key).trim().toLowerCase())
}

function csvToList(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function providerEnabled(provider: string) {
  return enabledProviders.value.includes(provider)
}

function providerHint(provider: string) {
  if (provider === 'virustotal') return '第三方文件分析'
  if (provider === 'llm_agent') return '语义安全审查'
  if (provider === 'clamav') return '自托管恶意文件扫描'
  return '扫描 provider'
}

function sensitiveConfigured(key: string) {
  return Boolean(sensitiveStatus.value[key])
}

function isOverridden(key: string) {
  return Object.prototype.hasOwnProperty.call(values.value, key)
}

function isDirty(item: ConfigItem) {
  return Boolean(dirty[item.key])
}

function fieldValue(item: ConfigItem) {
  return draftValue(item.key)
}

function fieldOverridden(item: ConfigItem) {
  return isOverridden(item.key)
}

function fieldSensitiveConfigured(item: ConfigItem) {
  return item.sensitive ? sensitiveConfigured(item.key) : false
}

function fieldLoading(item: ConfigItem) {
  return savingKey.value === item.key
}

function fieldCanClear(item: ConfigItem) {
  return item.sensitive ? sensitiveConfigured(item.key) : isOverridden(item.key)
}

async function saveItem(item: ConfigItem) {
  savingKey.value = item.key
  try {
    await mutation.mutateAsync({ [item.key]: drafts[item.key] ?? '' })
    dirty[item.key] = false
    if (item.sensitive) drafts[item.key] = ''
    message.success(`${item.label} 已保存`)
  } finally {
    savingKey.value = null
  }
}

async function clearOverride(item: ConfigItem) {
  drafts[item.key] = ''
  dirty[item.key] = false
  savingKey.value = item.key
  try {
    await mutation.mutateAsync({ [item.key]: '' })
    message.success(`${item.label} 已恢复默认`)
  } finally {
    savingKey.value = null
  }
}

async function saveDirtyItems() {
  const items = dirtyItems.value
  if (!items.length) return
  savingKey.value = dirtySaveKey
  try {
    const values = Object.fromEntries(items.map((item) => [item.key, drafts[item.key] ?? '']))
    await mutation.mutateAsync(values)
    for (const item of items) {
      dirty[item.key] = false
      if (item.sensitive) drafts[item.key] = ''
    }
    message.success(`${items.length} 项配置已保存`)
  } finally {
    savingKey.value = null
  }
}

function discardDirtyItems() {
  for (const item of dirtyItems.value) {
    dirty[item.key] = false
    drafts[item.key] = item.sensitive ? '' : effectiveValue(item.key)
  }
  message.info('未保存更改已放弃')
}
</script>

<style scoped>
.settings-shell {
  align-items: start;
  display: grid;
  gap: 34px;
  grid-template-columns: 128px minmax(0, 760px);
  justify-content: center;
  margin: 0 auto;
  max-width: 960px;
  min-width: 0;
}

.settings-shell.provider-view {
  grid-template-columns: 150px minmax(0, 1fr);
  max-width: 1220px;
}

.settings-nav {
  display: grid;
  gap: 0;
  padding: 18px 0 0;
  position: sticky;
  top: 12px;
}

.settings-nav-item {
  align-items: center;
  background: transparent;
  border: 0;
  border-left: 3px solid transparent;
  border-radius: 0;
  color: var(--text-secondary);
  cursor: pointer;
  display: block;
  min-width: 0;
  padding: 11px 14px;
  text-align: left;
}

.settings-nav-item:hover,
.settings-nav-item.active {
  background: var(--surface-hover);
}

.settings-nav-item.active {
  background: var(--surface-hover);
  border-left-color: var(--accent);
  color: var(--text-primary);
  font-weight: 700;
}

.settings-nav-item span {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.settings-nav-item strong {
  color: inherit;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-nav-item small {
  display: none;
}

.settings-main,
.section-stack {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.settings-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 0;
  min-width: 0;
  padding: 22px 26px;
}

.section-head {
  align-items: flex-start;
  border-bottom: 1px solid var(--divider);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  min-width: 0;
  padding-bottom: 16px;
}

.section-head h2 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
  line-height: 26px;
  margin: 0 0 4px;
}

.section-head p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

.section-alert {
  margin-top: 14px;
}

.section-head + .provider-choice-group {
  margin-top: 16px;
}

.settings-groups {
  display: grid;
  min-width: 0;
}

.section-head + .settings-groups,
.section-alert + .settings-groups {
  margin-top: 16px;
}

.settings-groups + .section-alert {
  margin-top: 14px;
}

.settings-group {
  min-width: 0;
}

.settings-group + .settings-group {
  border-top: 1px solid var(--divider);
  margin-top: 20px;
  padding-top: 18px;
}

.group-head {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding-bottom: 10px;
}

.group-head h3 {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
  margin: 0;
}

.group-head p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

.section-actions {
  align-items: center;
  border-top: 1px solid var(--divider);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 14px;
}

.field-list {
  border-top: 1px solid var(--border);
  display: grid;
  min-width: 0;
}

.settings-save-bar {
  align-items: center;
  background: rgba(255, 253, 245, 0.98);
  border: 1px solid #efd68a;
  border-radius: 8px;
  bottom: 18px;
  box-shadow: var(--shadow-md);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-top: 4px;
  padding: 12px 14px;
  position: sticky;
  z-index: 8;
}

.settings-save-bar > div:first-child {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.settings-save-bar strong {
  color: var(--warning-fg);
  font-size: 14px;
}

.settings-save-bar span {
  color: var(--text-secondary);
  font-size: 12px;
}

.save-bar-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.provider-choice-group {
  display: block;
}

.provider-choice-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  min-width: 0;
}

.provider-choice {
  align-items: flex-start;
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: flex;
  margin: 0;
  min-width: 0;
  padding: 12px;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.provider-choice:hover {
  background: var(--hover-bg);
  border-color: var(--border-muted);
}

.provider-choice:deep(.n-checkbox__label) {
  min-width: 0;
  width: 100%;
}

.provider-choice:deep(.n-checkbox-box) {
  margin-top: 2px;
}

.provider-choice-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.provider-choice-copy strong {
  font-size: 14px;
}

.provider-choice-copy small {
  color: var(--text-secondary);
  font-size: 12px;
}

.provider-status-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  min-width: 0;
}

.provider-status {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 14px;
}

.provider-status.inactive {
  background: var(--hover-bg);
}

.provider-status header {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.provider-status strong {
  flex: 1;
  font-size: 14px;
  min-width: 0;
}

.provider-status p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
  margin: 0;
}

.status-dot {
  background: var(--border-muted);
  border-radius: 50%;
  flex: 0 0 auto;
  height: 8px;
  width: 8px;
}

.status-dot.ok {
  background: var(--success-fg);
}

.status-dot.warn {
  background: var(--warning-fg);
}

.advanced-collapse {
  border-top: 1px solid var(--divider);
  padding-top: 2px;
}

.readonly-grid {
  border-top: 1px solid var(--divider);
  display: grid;
  gap: 0;
}

.readonly-item {
  border-top: 1px solid var(--divider);
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(220px, 0.8fr) minmax(0, 1.2fr);
  min-width: 0;
  padding: 12px 0;
}

.readonly-item:first-child {
  border-top: 0;
}

.readonly-item span {
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.readonly-item strong {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  overflow-wrap: anywhere;
}

@media (max-width: 1120px) {
  .settings-shell {
    grid-template-columns: 1fr;
  }

  .settings-nav {
    position: static;
  }

  .settings-nav {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .settings-nav,
  .provider-choice-grid,
  .provider-status-grid {
    grid-template-columns: 1fr;
  }

  .section-head {
    display: grid;
  }

  .readonly-item {
    grid-template-columns: 1fr;
  }

  .settings-save-bar {
    align-items: stretch;
    display: grid;
  }

  .save-bar-actions {
    justify-content: flex-start;
  }

  .section-actions {
    justify-content: flex-start;
  }
}
</style>
