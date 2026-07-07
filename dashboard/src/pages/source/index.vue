<template>
  <page-header title="插件源" description="AstrBot 自定义插件源接入信息" />
  <api-error-alert :error="statsQuery.error.value || md5Query.error.value" />

  <div class="source-page">
    <section class="source-panel primary">
      <div class="panel-heading hero-heading">
        <div>
          <h2>推荐填写地址</h2>
          <p>在 AstrBot Dashboard 的插件市场自定义源中添加这个 URL。</p>
        </div>
        <div class="panel-actions">
          <n-tag type="success" round>AstrBot 兼容</n-tag>
          <n-button type="primary" class="hero-copy-button" @click="copySourceUrl">
            <template #icon><n-icon :component="Copy" /></template>
            复制插件源 URL
          </n-button>
        </div>
      </div>

      <div class="hero-copy-grid">
        <source-copy-card
          label="插件源 URL"
          description="推荐在 AstrBot 自定义源中填写这一项"
          :value="sourceUrl"
          featured
        />
        <source-copy-card
          label="MD5 校验 URL"
          description="AstrBot 会按插件源 URL 自动推导这个地址"
          :value="sourceMd5Url"
        />
      </div>

      <n-alert type="info" :bordered="false">
        AstrBot 不要求插件源 URL 必须以 .json 结尾。若填写不带 .json 的 URL，AstrBot 会追加
        <span class="mono">-md5.json</span> 获取校验值；若填写以 .json 结尾的 URL，会替换成
        <span class="mono">-md5.json</span>。
      </n-alert>
    </section>

    <section class="source-panel">
      <h2>公开数据</h2>
      <div class="metric-grid">
        <div v-for="item in metrics" :key="item.label" class="metric">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
      <source-copy-card label="当前 MD5" :value="md5Query.data.value?.md5 || '-'" />
    </section>

    <section class="source-panel">
      <h2>兼容入口</h2>
      <div class="endpoint-list">
        <source-copy-card label="主入口" description="推荐填写给 AstrBot" :value="sourceUrl" />
        <source-copy-card label="JSON 别名" description="兼容习惯使用 .json 的客户端" :value="jsonSourceUrl" />
        <source-copy-card label="MD5 主入口" description="主入口推导出的校验地址" :value="sourceMd5Url" />
        <source-copy-card label="MD5 JSON 别名" description=".json 入口推导出的校验地址" :value="jsonMd5Url" />
        <source-copy-card label="公开统计" description="插件数、版本数、下载和安装统计" :value="statsUrl" />
      </div>
    </section>

    <section class="source-panel">
      <h2>格式说明</h2>
      <p class="muted">
        插件源返回一个 JSON 对象，顶层 key 是插件 key，值为 AstrBot 市场条目。当前源会输出这些核心字段：
      </p>
      <div class="field-list">
        <n-tag v-for="field in fields" :key="field" size="small" round>{{ field }}</n-tag>
      </div>
      <pre class="source-example">{{ exampleJson }}</pre>
    </section>

    <section class="source-panel">
      <h2>AstrBot 中怎么填</h2>
      <ol class="steps">
        <li>打开 AstrBot Dashboard 的插件市场页面。</li>
        <li>进入自定义插件源设置，新增插件源。</li>
        <li>填入上方“插件源 URL”，保存后刷新市场列表。</li>
      </ol>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMessage } from 'naive-ui'
import { Copy } from 'lucide-vue-next'

import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import SourceCopyCard from '@/components/source/source-copy-card.vue'
import { useRegistryMd5, useRegistryStats } from '@/query/stats'

const statsQuery = useRegistryStats()
const md5Query = useRegistryMd5()
const message = useMessage()
const origin = computed(() => window.location.origin)
const sourceUrl = computed(() => `${origin.value}/api/v1/plugins`)
const jsonSourceUrl = computed(() => `${origin.value}/api/v1/plugins.json`)
const sourceMd5Url = computed(() => `${origin.value}/api/v1/plugins-md5.json`)
const jsonMd5Url = computed(() => `${origin.value}/api/v1/plugins-md5.json`)
const statsUrl = computed(() => `${origin.value}/api/v1/plugins/stats`)
const metrics = computed(() => [
  { label: '公开插件', value: statsQuery.data.value?.total_plugins ?? '-' },
  { label: '活跃版本', value: statsQuery.data.value?.total_active_versions ?? '-' },
  { label: '下载量', value: statsQuery.data.value?.total_downloads ?? '-' },
  { label: '安装量', value: statsQuery.data.value?.total_installs ?? '-' },
])
const fields = [
  'name',
  'display_name',
  'desc',
  'author',
  'repo',
  'tags',
  'version',
  'updated_at',
  'logo',
  'commit_sha',
  'download_url',
  'sec_scan',
  'i18n',
  'astrbot_version',
  'support_platforms',
  'category',
]
const exampleJson = `{
  "astrbot-plugin-example": {
    "name": "astrbot-plugin-example",
    "display_name": "Example Plugin",
    "desc": "Plugin description",
    "author": "author",
    "repo": "https://github.com/owner/repo",
    "version": "1.0.0",
    "download_url": "https://registry.example.com/s3/...",
    "sec_scan": {
      "virustotal": { "pass": true, "mode": "real" },
      "llm_agent": { "pass": true, "mode": "real" }
    }
  }
}`

async function copySourceUrl() {
  await navigator.clipboard.writeText(sourceUrl.value)
  message.success('插件源 URL 已复制')
}
</script>

<style scoped>
.source-page {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr));
}

.source-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 14px;
  min-width: 0;
  padding: 18px;
}

.source-panel.primary {
  grid-column: 1 / -1;
}

.panel-heading {
  align-items: flex-start;
  display: flex;
  gap: 16px;
  justify-content: space-between;
}

.panel-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.hero-heading {
  align-items: center;
}

.hero-copy-button {
  min-width: 168px;
}

.hero-copy-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));
}

h2 {
  font-size: 17px;
  margin: 0;
}

.panel-heading p,
.source-panel p {
  line-height: 1.6;
  margin: 6px 0 0;
}

.metric-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  padding: 12px;
}

.metric span {
  color: var(--text-secondary);
  display: block;
  font-size: 12px;
}

.metric strong {
  display: block;
  font-size: 24px;
  margin-top: 4px;
}

.endpoint-list {
  display: grid;
  gap: 12px;
}

.field-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-example {
  background: #0f172a;
  border-radius: 8px;
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
  max-height: 360px;
  overflow: auto;
  padding: 14px;
}

.steps {
  line-height: 1.8;
  margin: 0;
  padding-left: 20px;
}

@media (max-width: 980px) {
  .hero-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
