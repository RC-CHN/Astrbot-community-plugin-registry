<template>
  <n-modal
    :show="show"
    class="artifact-browser-modal"
    transform-origin="center"
    @update:show="emit('update:show', $event)"
  >
    <section class="artifact-modal-shell" role="dialog" aria-modal="true" aria-label="制品文件浏览">
      <header class="artifact-modal-titlebar">
        <div class="artifact-modal-heading">
          <strong>制品文件浏览</strong>
          <span>版本 {{ version?.version || '-' }}</span>
        </div>
        <n-button size="small" quaternary @click="emit('update:show', false)">
          关闭
        </n-button>
      </header>

      <div class="artifact-modal-body">
        <div class="artifact-browser">
          <header class="artifact-browser-head">
            <div>
              <div class="artifact-title">版本 {{ version?.version || '-' }}</div>
              <div class="artifact-subtitle">打开时加载目录，点击文件后读取内容；二进制文件只展示元信息。</div>
            </div>
            <n-button size="small" secondary :loading="treeLoading" :disabled="!version" @click="loadTree">
              刷新目录
            </n-button>
          </header>

          <n-alert v-if="error" type="error" :bordered="false" closable @close="error = ''">
            {{ error }}
          </n-alert>

          <div class="artifact-layout">
            <aside class="artifact-tree-pane">
              <n-spin class="pane-spin tree-spin" :show="treeLoading">
                <n-empty v-if="!treeLoading && !treeData.length" description="暂无可浏览文件" />
                <n-tree
                  v-else
                  block-line
                  :data="treeData"
                  :selected-keys="selectedKeys"
                  :default-expanded-keys="defaultExpandedKeys"
                  key-field="key"
                  label-field="label"
                  @update:selected-keys="handleSelect"
                />
              </n-spin>
            </aside>

            <section class="artifact-file-pane">
              <n-spin class="pane-spin file-spin" :show="fileLoading">
                <n-empty v-if="!selectedPath" description="选择左侧文件查看内容" />
                <template v-else-if="selectedFile">
                  <header class="file-head">
                    <div>
                      <strong>{{ selectedFile.name }}</strong>
                      <span>{{ selectedFile.path }}</span>
                    </div>
                    <n-space size="small">
                      <n-tag size="small" round>{{ selectedFile.language }}</n-tag>
                      <n-tag size="small" round>{{ formatFileSize(selectedFile.size) }}</n-tag>
                    </n-space>
                  </header>

                  <n-alert v-if="selectedFile.binary" type="warning" :bordered="false">
                    该文件看起来是二进制内容，未在浏览器中展开。
                  </n-alert>
                  <n-alert v-else-if="selectedFile.truncated" type="warning" :bordered="false">
                    文件较大，仅显示前 512 KiB。
                  </n-alert>

                  <div v-if="!selectedFile.binary" class="code-viewer" v-html="highlightedHtml" />
                </template>
              </n-spin>
            </section>
          </div>
        </div>
      </div>
    </section>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TreeOption } from 'naive-ui'
import type { HighlighterCore, LanguageRegistration } from '@shikijs/core'

import { getVersionArtifactFile, getVersionArtifactTree } from '@/api/plugins'
import type { ArtifactFileResponse, ArtifactTreeEntry, VersionSummary } from '@/api/types'
import { formatFileSize } from '@/utils/file-size'

type ArtifactTreeOption = TreeOption & {
  key: string
  label: string
  path: string
  kind: 'dir' | 'file'
  children?: ArtifactTreeOption[]
}

const SHIKI_THEME = 'github-dark'
const SHIKI_LANGUAGES = [
  'bash',
  'css',
  'html',
  'javascript',
  'json',
  'markdown',
  'python',
  'toml',
  'typescript',
  'vue',
  'yaml',
] as const
type SupportedShikiLanguage = (typeof SHIKI_LANGUAGES)[number]

const SHIKI_LANGUAGE_SET = new Set<string>(SHIKI_LANGUAGES)
let highlighterPromise: Promise<HighlighterCore> | null = null

const props = defineProps<{
  show: boolean
  pluginId?: string
  version?: VersionSummary | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

const entries = ref<ArtifactTreeEntry[]>([])
const selectedPath = ref('')
const selectedFile = ref<ArtifactFileResponse | null>(null)
const highlightedHtml = ref('')
const treeLoading = ref(false)
const fileLoading = ref(false)
const error = ref('')

const show = computed(() => props.show)
const selectedKeys = computed(() => (selectedPath.value ? [selectedPath.value] : []))
const defaultExpandedKeys = computed(() => treeData.value.filter((item) => item.kind === 'dir').slice(0, 4).map((item) => item.key))

const treeData = computed<ArtifactTreeOption[]>(() => {
  const nodeMap = new Map<string, ArtifactTreeOption>()
  const roots: ArtifactTreeOption[] = []

  for (const entry of entries.value) {
    const node = ensureNode(entry.path, entry.kind, entry.name)
    const parentPath = entry.path.split('/').slice(0, -1).join('/')
    if (!parentPath) {
      if (!roots.includes(node)) roots.push(node)
      continue
    }
    const parent = ensureNode(parentPath, 'dir', parentPath.split('/').pop() || parentPath)
    parent.children ||= []
    if (!parent.children.includes(node)) parent.children.push(node)
  }

  sortNodes(roots)
  return roots

  function ensureNode(path: string, kind: 'dir' | 'file', label: string) {
    const existing = nodeMap.get(path)
    if (existing) {
      if (kind === 'dir') existing.kind = 'dir'
      return existing
    }
    const node: ArtifactTreeOption = { key: path, label, path, kind, isLeaf: kind === 'file' }
    nodeMap.set(path, node)
    return node
  }
})

watch(
  () => [props.show, props.version?.id, props.pluginId] as const,
  ([visible]) => {
    if (visible) void loadTree()
  },
)

async function loadTree() {
  if (!props.pluginId || !props.version) return
  treeLoading.value = true
  error.value = ''
  selectedPath.value = ''
  selectedFile.value = null
  highlightedHtml.value = ''
  try {
    const result = await getVersionArtifactTree(props.pluginId, props.version.id)
    entries.value = result.entries
  } catch (err) {
    entries.value = []
    error.value = errorMessage(err)
  } finally {
    treeLoading.value = false
  }
}

async function handleSelect(keys: Array<string | number>) {
  const path = String(keys[0] || '')
  selectedPath.value = path
  selectedFile.value = null
  highlightedHtml.value = ''
  if (!path || !props.pluginId || !props.version) return
  const entry = entries.value.find((item) => item.path === path)
  if (!entry || entry.kind !== 'file') return

  fileLoading.value = true
  error.value = ''
  try {
    const file = await getVersionArtifactFile(props.pluginId, props.version.id, path)
    selectedFile.value = file
    highlightedHtml.value = await highlightFile(file)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    fileLoading.value = false
  }
}

function sortNodes(nodes: ArtifactTreeOption[]) {
  nodes.sort((a, b) => Number(a.kind === 'file') - Number(b.kind === 'file') || a.label.localeCompare(b.label))
  for (const node of nodes) {
    if (node.children) sortNodes(node.children)
  }
}

function errorMessage(err: unknown) {
  if (err instanceof Error) return err.message
  return '制品文件读取失败'
}

async function highlightFile(file: ArtifactFileResponse) {
  if (file.binary || !file.content) return ''
  try {
    const highlighter = await getHighlighter()
    const lang = shikiLanguage(file.language)
    if (!lang) return plainCodeHtml(file.content)
    return highlighter.codeToHtml(file.content, {
      lang,
      theme: SHIKI_THEME,
    })
  } catch (err) {
    console.warn('Shiki highlight failed; falling back to escaped text', err)
    return `<pre class="shiki"><code>${escapeHtml(file.content)}</code></pre>`
  }
}

function getHighlighter() {
  highlighterPromise ||= createArtifactHighlighter()
  return highlighterPromise
}

async function createArtifactHighlighter() {
  const [
    core,
    engine,
    bashLang,
    cssLang,
    htmlLang,
    javascriptLang,
    jsonLang,
    markdownLang,
    pythonLang,
    tomlLang,
    typescriptLang,
    vueLang,
    yamlLang,
    githubDarkTheme,
  ] = await Promise.all([
    import('@shikijs/core'),
    import('@shikijs/engine-javascript'),
    import('@shikijs/langs/bash'),
    import('@shikijs/langs/css'),
    import('@shikijs/langs/html'),
    import('@shikijs/langs/javascript'),
    import('@shikijs/langs/json'),
    import('@shikijs/langs/markdown'),
    import('@shikijs/langs/python'),
    import('@shikijs/langs/toml'),
    import('@shikijs/langs/typescript'),
    import('@shikijs/langs/vue'),
    import('@shikijs/langs/yaml'),
    import('@shikijs/themes/github-dark'),
  ])
  const grammars: LanguageRegistration[] = [
    ...bashLang.default,
    ...cssLang.default,
    ...htmlLang.default,
    ...javascriptLang.default,
    ...jsonLang.default,
    ...markdownLang.default,
    ...pythonLang.default,
    ...tomlLang.default,
    ...typescriptLang.default,
    ...vueLang.default,
    ...yamlLang.default,
  ]
  return core.createHighlighterCore({
    themes: [githubDarkTheme.default],
    langs: grammars,
    engine: engine.createJavaScriptRegexEngine(),
  })
}

function shikiLanguage(language: string): SupportedShikiLanguage | null {
  const aliases: Record<string, string> = {
    dotenv: 'bash',
    sh: 'bash',
    shell: 'bash',
    shellscript: 'bash',
  }
  const normalized = aliases[language] || language
  return SHIKI_LANGUAGE_SET.has(normalized) ? (normalized as SupportedShikiLanguage) : null
}

function plainCodeHtml(value: string) {
  return `<pre class="shiki plain"><code>${escapeHtml(value)}</code></pre>`
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}
</script>

<style scoped>
.artifact-modal-shell {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 18px 50px rgb(15 23 42 / 18%);
  box-sizing: border-box;
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  height: 80vh;
  max-height: calc(100vh - 32px);
  max-width: calc(100vw - 32px);
  min-height: min(520px, calc(100vh - 32px));
  min-width: min(720px, calc(100vw - 32px));
  overflow: hidden;
  width: 80vw;
}

.artifact-modal-titlebar {
  align-items: center;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex: 0 0 auto;
  gap: 12px;
  justify-content: space-between;
  min-height: 56px;
  padding: 0 16px 0 18px;
}

.artifact-modal-heading {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.artifact-modal-heading strong,
.artifact-modal-heading span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-modal-heading strong {
  font-size: 15px;
  font-weight: 650;
}

.artifact-modal-heading span {
  color: var(--text-secondary);
  font-size: 12px;
}

.artifact-modal-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  padding: 16px;
}

.artifact-browser {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1 1 auto;
  height: 100%;
  min-height: 0;
  min-width: 0;
}

.artifact-browser-head {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  min-width: 0;
}

.artifact-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

.artifact-subtitle {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
  margin-top: 2px;
}

.artifact-layout {
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  flex: 1;
  grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.artifact-tree-pane,
.artifact-file-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  padding: 12px;
}

.artifact-tree-pane {
  border-right: 1px solid var(--border);
  background: var(--surface-hover);
}

.artifact-file-pane {
  background: var(--surface);
}

.file-head {
  align-items: flex-start;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  margin-bottom: 10px;
  min-height: 42px;
  min-width: 0;
}

.file-head div {
  display: grid;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}

.file-head strong,
.file-head span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-head span {
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.code-viewer {
  background: #0f1720;
  border-radius: 8px;
  flex: 1 1 auto;
  margin: 10px 0 0;
  min-height: 0;
  min-width: 0;
  overflow: auto;
}

.code-viewer :deep(pre) {
  background: transparent !important;
  margin: 0;
  min-height: 100%;
  overflow: visible;
  padding: 14px;
  tab-size: 2;
}

.code-viewer :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.pane-spin {
  flex: 1 1 auto;
  height: 100%;
  min-height: 0;
  min-width: 0;
}

.pane-spin :deep(.n-spin-container),
.pane-spin :deep(.n-spin-content) {
  height: 100%;
  min-height: 0;
  min-width: 0;
}

.tree-spin :deep(.n-spin-content) {
  overflow: auto;
}

.file-spin :deep(.n-spin-content) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.artifact-tree-pane :deep(.n-tree-node-content__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 820px) {
  .artifact-modal-shell {
    height: calc(100vh - 24px);
    max-height: calc(100vh - 24px);
    max-width: calc(100vw - 24px);
    min-height: 0;
    min-width: 0;
    width: calc(100vw - 24px);
  }

  .artifact-modal-body {
    padding: 12px;
  }

  .artifact-browser-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .artifact-layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(180px, 34%) minmax(0, 1fr);
  }

  .artifact-tree-pane {
    border-bottom: 1px solid var(--border);
    border-right: 0;
  }
}
</style>
