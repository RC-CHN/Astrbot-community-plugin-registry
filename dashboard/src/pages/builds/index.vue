<template>
  <page-header title="任务" description="查看构建、提交、扫描和轮询任务状态" />

  <api-error-alert :error="statusQuery.error.value || tasksQuery.error.value" />

  <section class="worker-overview">
    <article class="metric-panel">
      <span>待执行</span>
      <strong>{{ workerStatus?.queue_length ?? 0 }}</strong>
    </article>
    <article class="metric-panel">
      <span>延迟队列</span>
      <strong>{{ workerStatus?.delayed_length ?? 0 }}</strong>
    </article>
    <article class="metric-panel">
      <span>死信队列</span>
      <strong>{{ workerStatus?.dead_letter_length ?? 0 }}</strong>
    </article>
    <article class="metric-panel">
      <span>活跃 Worker</span>
      <strong>{{ workerStatus?.active_workers.length ?? 0 }}</strong>
    </article>
  </section>

  <section class="worker-panel">
    <header class="panel-head">
      <div>
        <h2>Worker 状态</h2>
        <p>{{ workerStatus?.redis_connected ? 'Redis 已连接' : 'Redis 不可用' }}</p>
      </div>
      <n-tag :type="workerStatus?.redis_connected ? 'success' : 'error'" round>
        {{ workerStatus?.redis_connected ? '在线' : '离线' }}
      </n-tag>
    </header>
    <div v-if="workerStatus?.active_workers.length" class="worker-list">
      <div v-for="worker in workerStatus.active_workers" :key="worker.worker_id" class="worker-row">
        <div>
          <strong>{{ worker.worker_id }}</strong>
          <span>{{ worker.hostname || '-' }} · pid {{ worker.pid || '-' }}</span>
        </div>
        <div class="worker-row-meta">
          <n-tag v-if="worker.current_task_id" type="info" size="small" round>
            运行 {{ shortId(worker.current_task_id) }}
          </n-tag>
          <span>{{ formatDateTime(worker.heartbeat_at) }}</span>
        </div>
      </div>
    </div>
    <n-empty v-else description="暂无活跃 worker" />
  </section>

  <page-toolbar>
    <n-select v-model:value="filters.status" clearable placeholder="任务状态" :options="statusOptions" class="filter" />
    <n-select v-model:value="filters.type" clearable placeholder="任务类型" :options="typeOptions" class="filter" />
    <n-button secondary :loading="tasksQuery.isFetching.value || statusQuery.isFetching.value" @click="refresh">
      刷新
    </n-button>
  </page-toolbar>

  <n-data-table
    remote
    :columns="columns"
    :data="rows"
    :loading="tasksQuery.isLoading.value"
    :pagination="pagination"
    :row-key="rowKey"
    @update:page="setPage"
  />
</template>

<script setup lang="ts">
import { computed, h, reactive, watch } from 'vue'
import { NButton, NTag, NTooltip, type DataTableColumns, type SelectOption } from 'naive-ui'

import type { WorkerTaskListParams, WorkerTaskStatus, WorkerTaskSummary } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import CopyableText from '@/components/common/copyable-text.vue'
import PageHeader from '@/components/common/page-header.vue'
import PageToolbar from '@/components/common/page-toolbar.vue'
import { useTaskMutations, useTasks, useWorkerStatus } from '@/query/tasks'
import { formatDateTime } from '@/utils/datetime'

const filters = reactive<WorkerTaskListParams>({
  status: '',
  type: '',
  page: 1,
  page_size: 50,
})

const tasksQuery = useTasks(computed(() => ({ ...filters })))
const statusQuery = useWorkerStatus()
const mutations = useTaskMutations()
const rows = computed(() => tasksQuery.data.value?.items || [])
const workerStatus = computed(() => statusQuery.data.value)
const rowKey = (row: WorkerTaskSummary) => row.id

const statusOptions: SelectOption[] = [
  { label: '等待中', value: 'queued' },
  { label: '延迟中', value: 'delayed' },
  { label: '运行中', value: 'running' },
  { label: '重试等待', value: 'retrying' },
  { label: '已完成', value: 'succeeded' },
  { label: '失败', value: 'failed' },
  { label: '死信', value: 'dead' },
  { label: '已取消', value: 'cancelled' },
]

const typeOptions: SelectOption[] = [
  { label: '提交', value: 'submit' },
  { label: '构建', value: 'build' },
  { label: '扫描', value: 'scan' },
  { label: 'VirusTotal 轮询', value: 'virustotal_poll' },
]

const pagination = computed(() => ({
  itemCount: tasksQuery.data.value?.total || 0,
  page: filters.page,
  pageSize: filters.page_size,
  showSizePicker: false,
}))

watch(
  () => [filters.status, filters.type],
  () => {
    filters.page = 1
  },
)

const columns: DataTableColumns<WorkerTaskSummary> = [
  {
    title: '任务',
    key: 'task',
    width: 170,
    render: (row) =>
      h('div', { class: 'task-title' }, [
        h('strong', taskTypeLabel(row.task_type)),
        h(CopyableText, { value: row.id, max: 14 }),
      ]),
  },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) => h(NTag, { type: taskStatusMeta(row.status).type, round: true }, { default: () => taskStatusMeta(row.status).label }),
  },
  {
    title: '目标',
    key: 'target',
    minWidth: 230,
    render: (row) => h('div', { class: 'target-cell' }, targetLines(row).map((line) => h('span', line))),
  },
  {
    title: 'Provider',
    key: 'provider',
    width: 130,
    render: (row) => row.provider || '-',
  },
  {
    title: '尝试',
    key: 'attempts',
    width: 90,
    render: (row) => `${row.attempts}/${row.max_attempts}`,
  },
  {
    title: '时间',
    key: 'time',
    width: 210,
    render: (row) => renderTaskTimes(row),
  },
  {
    title: '耗时',
    key: 'duration',
    width: 90,
    render: (row) => formatDuration(row.duration_ms),
  },
  {
    title: '错误',
    key: 'error',
    minWidth: 180,
    render: (row) => renderError(row),
  },
  {
    title: '操作',
    key: 'actions',
    align: 'right',
    width: 100,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          secondary: true,
          disabled: !canRetry(row),
          loading: mutations.retry.isPending.value,
          onClick: () => mutations.retry.mutate({ taskId: row.id }),
        },
        { default: () => '重试' },
      ),
  },
]

function setPage(page: number) {
  filters.page = page
}

function refresh() {
  void tasksQuery.refetch()
  void statusQuery.refetch()
}

function taskTypeLabel(type: string) {
  const labels: Record<string, string> = {
    submit: '提交',
    build: '构建',
    scan: '扫描',
    virustotal_poll: 'VT 轮询',
  }
  return labels[type] || type
}

function taskStatusMeta(status: WorkerTaskStatus | string): { label: string; type: 'default' | 'success' | 'warning' | 'error' | 'info' } {
  const metas: Record<string, { label: string; type: 'default' | 'success' | 'warning' | 'error' | 'info' }> = {
    queued: { label: '等待中', type: 'default' },
    delayed: { label: '延迟中', type: 'info' },
    running: { label: '运行中', type: 'info' },
    retrying: { label: '重试等待', type: 'warning' },
    succeeded: { label: '已完成', type: 'success' },
    failed: { label: '失败', type: 'error' },
    dead: { label: '死信', type: 'error' },
    cancelled: { label: '已取消', type: 'default' },
  }
  return metas[status] || { label: status, type: 'default' }
}

function targetLines(row: WorkerTaskSummary) {
  const payload = row.payload_summary || {}
  const lines: string[] = []
  if (typeof payload.repo_url === 'string') lines.push(payload.repo_url)
  if (row.plugin_id) lines.push(`插件 ${shortId(row.plugin_id)}`)
  if (row.version_id) lines.push(`版本 ${shortId(row.version_id)}`)
  if (typeof payload.version === 'string') lines.push(`版本号 ${payload.version}`)
  if (typeof payload.ref === 'string') lines.push(`ref ${payload.ref}`)
  if (!lines.length) lines.push('-')
  return lines
}

function renderTaskTimes(row: WorkerTaskSummary) {
  return h(
    'div',
    { class: 'time-cell' },
    taskTimeItems(row).map((item) =>
      h('div', { class: 'time-item' }, [
        h('span', { class: `time-label ${item.kind}` }, item.label),
        h('time', item.value),
      ]),
    ),
  )
}

function taskTimeItems(row: WorkerTaskSummary) {
  const items = [{ label: '入队', value: formatDateTime(row.queued_at), kind: 'queued' }]
  if (row.started_at) items.push({ label: '开始', value: formatDateTime(row.started_at), kind: 'running' })
  if (row.next_run_at) items.push({ label: '下次', value: formatDateTime(row.next_run_at), kind: 'delayed' })
  if (row.finished_at) items.push({ label: '结束', value: formatDateTime(row.finished_at), kind: 'done' })
  return items
}

function renderError(row: WorkerTaskSummary) {
  if (!row.last_error) return '-'
  const message = row.last_error
  return h(NTooltip, null, {
    trigger: () => h('span', { class: 'error-preview' }, message),
    default: () => message,
  })
}

function canRetry(row: WorkerTaskSummary) {
  return ['dead', 'failed', 'cancelled'].includes(row.status)
}

function formatDuration(durationMs: number | null) {
  if (durationMs == null) return '-'
  if (durationMs < 1000) return `${durationMs}ms`
  const seconds = durationMs / 1000
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value
}
</script>

<style scoped>
.worker-overview {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
}

.metric-panel,
.worker-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.metric-panel {
  display: grid;
  gap: 8px;
  padding: 16px;
}

.metric-panel span,
.panel-head p,
.worker-row span,
.target-cell span {
  color: var(--text-secondary);
  font-size: 12px;
}

.metric-panel strong {
  color: var(--text-primary);
  font-size: 26px;
  line-height: 1;
}

.worker-panel {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
  padding: 16px;
}

.panel-head {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.panel-head h2 {
  font-size: 16px;
  line-height: 1.2;
  margin: 0;
}

.panel-head p {
  margin: 4px 0 0;
}

.worker-list {
  display: grid;
  gap: 8px;
}

.worker-row {
  align-items: center;
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  min-width: 0;
  padding: 10px 12px;
}

.worker-row > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.worker-row strong,
.worker-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.worker-row-meta {
  justify-items: end;
}

.filter {
  width: 180px;
}

.task-title,
.target-cell,
.time-cell {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.task-title strong {
  color: var(--text-primary);
  font-weight: 650;
}

.target-cell span,
.error-preview {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time-item {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: 36px minmax(0, 1fr);
  min-width: 0;
}

.time-label {
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
}

.time-label.queued {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.time-label.running {
  background: #e8f3fa;
  color: #2f86bd;
}

.time-label.delayed {
  background: #fff8c5;
  color: #9a6700;
}

.time-label.done {
  background: #dafbe1;
  color: #1a7f37;
}

.time-item time {
  color: var(--text-secondary);
  font-size: 12px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.error-preview {
  color: var(--danger);
  display: block;
  max-width: 280px;
}

@media (max-width: 1180px) {
  .worker-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .worker-overview {
    grid-template-columns: 1fr;
  }

  .worker-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .worker-row-meta {
    justify-items: start;
  }
}
</style>
