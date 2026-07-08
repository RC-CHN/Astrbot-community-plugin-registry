<template>
  <page-header title="提交请求" description="处理普通用户提交的插件收录请求" />
  <api-error-alert :error="error" />

  <section class="panel">
    <div class="toolbar">
      <n-select v-model:value="status" class="status-filter" :options="statusOptions" />
    </div>
    <n-data-table
      :columns="columns"
      :data="items"
      :loading="query.isLoading.value"
      :pagination="false"
      size="small"
      :scroll-x="1200"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { NButton, NInput, NPopconfirm, NSpace, NTag, type DataTableColumns } from 'naive-ui'

import {
  acceptSubmission,
  listAdminSubmissions,
  markSubmissionDuplicate,
  rejectSubmission,
} from '@/api/submissions'
import type { SubmissionRequest, SubmissionStatus } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import PageHeader from '@/components/common/page-header.vue'
import { formatDateTime } from '@/utils/datetime'

const queryClient = useQueryClient()
const error = ref<unknown>(null)
const status = ref<SubmissionStatus | ''>('pending_review')
const messages = ref<Record<string, string>>({})

const statusOptions = [
  { label: '待处理', value: 'pending_review' },
  { label: '已接受', value: 'accepted' },
  { label: '已拒绝', value: 'rejected' },
  { label: '重复', value: 'duplicate' },
  { label: '全部', value: '' },
]

const query = useQuery({
  queryKey: computed(() => ['admin-submissions', status.value]),
  queryFn: () => listAdminSubmissions({ status: status.value }),
  refetchInterval: 5000,
})

const items = computed(() => query.data.value?.items || [])
const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-submissions'] })

const acceptMutation = useMutation({
  mutationFn: ({ id, admin_message }: { id: string; admin_message: string | null }) =>
    acceptSubmission(id, { admin_message }),
  onSuccess: invalidate,
  onError: (err) => {
    error.value = err
  },
})

const rejectMutation = useMutation({
  mutationFn: ({ id, admin_message }: { id: string; admin_message: string | null }) =>
    rejectSubmission(id, { admin_message }),
  onSuccess: invalidate,
  onError: (err) => {
    error.value = err
  },
})

const duplicateMutation = useMutation({
  mutationFn: ({ id, admin_message }: { id: string; admin_message: string | null }) =>
    markSubmissionDuplicate(id, { admin_message }),
  onSuccess: invalidate,
  onError: (err) => {
    error.value = err
  },
})

const columns = computed<DataTableColumns<SubmissionRequest>>(() => [
  {
    title: '用户',
    key: 'username',
    width: 120,
    render: (row) => row.username || row.user_id,
  },
  {
    title: '仓库',
    key: 'repo_url',
    minWidth: 260,
    render: (row) => h('a', { href: row.repo_url, target: '_blank', rel: 'noreferrer' }, row.repo_url),
  },
  {
    title: 'Ref',
    key: 'ref',
    width: 150,
    render: (row) => (row.ref_type === 'default' ? '默认分支' : `${row.ref_type}: ${row.ref || '-'}`),
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (row) =>
      h(NTag, { size: 'small', round: true, type: statusType(row.status) }, { default: () => statusLabel(row.status) }),
  },
  {
    title: '用户说明',
    key: 'user_message',
    minWidth: 220,
    render: (row) => row.user_message || '-',
  },
  {
    title: '管理员说明',
    key: 'admin_message',
    minWidth: 220,
    render(row) {
      if (row.status !== 'pending_review') return row.admin_message || '-'
      return h(NInput, {
        value: messages.value[row.id] || '',
        placeholder: '接受时作为 changelog；拒绝/重复时作为说明',
        clearable: true,
        onUpdateValue: (value: string) => {
          messages.value[row.id] = value
        },
      })
    },
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 140,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    title: '操作',
    key: 'actions',
    width: 230,
    align: 'right',
    render(row) {
      if (row.status !== 'pending_review') return null
      const message = () => messages.value[row.id] || null
      return h(NSpace, { justify: 'end', size: 'small' }, () => [
        h(
          NPopconfirm,
          { onPositiveClick: () => acceptMutation.mutate({ id: row.id, admin_message: message() }) },
          {
            trigger: () => h(NButton, { size: 'small', type: 'primary' }, { default: () => '接受导入' }),
            default: () => '接受后会进入现有导入、构建和扫描队列，确认继续？',
          },
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => rejectMutation.mutate({ id: row.id, admin_message: message() }) },
          {
            trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' }, { default: () => '拒绝' }),
            default: () => '确认拒绝这个提交请求？',
          },
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => duplicateMutation.mutate({ id: row.id, admin_message: message() }) },
          {
            trigger: () => h(NButton, { size: 'small', secondary: true }, { default: () => '重复' }),
            default: () => '确认标记为重复请求？',
          },
        ),
      ])
    },
  },
])

function statusLabel(value: SubmissionStatus) {
  if (value === 'pending_review') return '待处理'
  if (value === 'accepted') return '已接受'
  if (value === 'rejected') return '已拒绝'
  return '重复'
}

function statusType(value: SubmissionStatus) {
  if (value === 'accepted') return 'success'
  if (value === 'pending_review') return 'warning'
  if (value === 'rejected') return 'error'
  return 'default'
}
</script>

<style scoped>
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 16px;
  min-width: 0;
  padding: 18px;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
}

.status-filter {
  width: 140px;
}
</style>
