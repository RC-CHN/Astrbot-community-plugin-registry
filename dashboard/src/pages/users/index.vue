<template>
  <page-header title="用户" description="管理注册策略、用户审批和邀请码" />

  <api-error-alert :error="error || configQuery.error.value" />

  <section class="users-grid">
    <div class="panel full policy-panel">
      <header class="panel-head">
        <div>
          <h2>注册策略</h2>
          <p>控制公开注册入口。保存后立即生效，公开注册页会按当前模式显示或隐藏字段。</p>
        </div>
        <n-tag v-if="hasPolicyChanges" type="warning" round>未保存</n-tag>
      </header>

      <div class="mode-row">
        <n-radio-group v-model:value="registrationMode" name="registration-mode" class="mode-options">
          <n-radio-button value="disabled">关闭注册</n-radio-button>
          <n-radio-button value="invite">邀请码注册</n-radio-button>
          <n-radio-button value="approval">注册后审批</n-radio-button>
        </n-radio-group>
        <n-button type="primary" :disabled="!hasPolicyChanges" :loading="savingPolicy" @click="saveRegistrationPolicy">
          保存策略
        </n-button>
      </div>

      <n-alert :type="registrationModeAlertType" :bordered="false">
        {{ registrationModeDescription }}
      </n-alert>
    </div>

    <div v-if="registrationMode === 'invite'" class="panel">
      <header class="panel-head">
        <div>
          <h2>创建邀请码</h2>
          <p>邀请码注册会直接激活普通用户；明文邀请码只在创建后显示一次。</p>
        </div>
      </header>
      <n-form :model="inviteForm" label-placement="top" class="invite-form">
        <n-form-item label="使用次数">
          <n-input-number v-model:value="inviteForm.max_uses" :min="1" :max="1000" />
        </n-form-item>
        <n-form-item label="过期时间">
          <n-date-picker
            v-model:value="inviteForm.expires_at"
            type="datetime"
            clearable
            placeholder="不设置则长期有效"
          />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="inviteForm.note" placeholder="例如：给某个社区成员" />
        </n-form-item>
        <n-button type="primary" :loading="creatingInvite" @click="createInviteCode">
          创建邀请码
        </n-button>
      </n-form>
      <n-alert v-if="createdInviteCode" type="success" :bordered="false" class="created-code">
        <div class="code-row">
          <span>新邀请码</span>
          <copyable-text :value="createdInviteCode" :max="48" />
        </div>
      </n-alert>
    </div>

    <div class="panel" :class="{ full: registrationMode !== 'invite' }">
      <header class="panel-head">
        <div>
          <h2>{{ registrationMode === 'approval' ? '用户审批' : '用户' }}</h2>
          <p>{{ userPanelDescription }}</p>
        </div>
        <n-select v-model:value="userStatus" class="status-filter" :options="statusOptions" />
      </header>
      <n-data-table
        :columns="userColumns"
        :data="users"
        :loading="usersQuery.isLoading.value"
        :pagination="false"
        size="small"
        :scroll-x="900"
      />
    </div>

    <div v-if="registrationMode === 'invite'" class="panel full">
      <header class="panel-head">
        <div>
          <h2>邀请码</h2>
          <p>禁用后邀请码不能再用于注册，已注册用户不受影响。</p>
        </div>
      </header>
      <n-data-table
        :columns="inviteColumns"
        :data="invites"
        :loading="invitesQuery.isLoading.value"
        :pagination="false"
        size="small"
        :scroll-x="900"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useMessage, NButton, NPopconfirm, NSpace, NTag, type DataTableColumns } from 'naive-ui'

import { getSystemConfig, updateSystemConfig } from '@/api/config'
import {
  approveUser,
  createInvite,
  disableInvite,
  disableUser,
  listInvites,
  listUsers,
} from '@/api/users'
import type { InviteSummary, RegistrationMode, UserStatus, UserSummary } from '@/api/types'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import CopyableText from '@/components/common/copyable-text.vue'
import PageHeader from '@/components/common/page-header.vue'
import { queryKeys } from '@/query/keys'
import { formatDateTime } from '@/utils/datetime'

const queryClient = useQueryClient()
const message = useMessage()
const error = ref<unknown>(null)
const userStatus = ref<UserStatus | ''>('pending_approval')
const createdInviteCode = ref('')
const registrationMode = ref<RegistrationMode>('disabled')
const inviteForm = reactive({
  max_uses: 1,
  expires_at: null as number | null,
  note: '',
})

const statusOptions = [
  { label: '待批准', value: 'pending_approval' },
  { label: '已激活', value: 'active' },
  { label: '已禁用', value: 'disabled' },
  { label: '全部', value: '' },
]

const configQuery = useQuery({ queryKey: queryKeys.config.system(), queryFn: getSystemConfig })

const savedRegistrationMode = computed<RegistrationMode>(() =>
  normalizeRegistrationMode(configQuery.data.value?.effective_values.USER_REGISTRATION_MODE),
)

watch(
  savedRegistrationMode,
  (mode) => {
    registrationMode.value = mode
  },
  { immediate: true },
)

watch(registrationMode, (mode) => {
  createdInviteCode.value = ''
  if (mode === 'approval') {
    userStatus.value = 'pending_approval'
  } else if (userStatus.value === 'pending_approval') {
    userStatus.value = ''
  }
})

const usersQuery = useQuery({
  queryKey: computed(() => ['users', userStatus.value]),
  queryFn: () => listUsers({ status: userStatus.value }),
})

const invitesQuery = useQuery({
  queryKey: ['invites'],
  queryFn: listInvites,
  enabled: computed(() => registrationMode.value === 'invite'),
})

const users = computed(() => usersQuery.data.value?.items || [])
const invites = computed(() => invitesQuery.data.value?.items || [])
const hasPolicyChanges = computed(() => registrationMode.value !== savedRegistrationMode.value)

const registrationModeDescription = computed(() => {
  if (registrationMode.value === 'disabled') {
    return '公开注册关闭。登录页会保留注册入口说明，但不会显示注册表单。'
  }
  if (registrationMode.value === 'invite') {
    return '用户必须填写有效邀请码才能注册；注册成功后账号立即激活。'
  }
  return '用户可以提交注册申请；账号需要管理员批准后才能登录和创建插件提交请求。'
})

const registrationModeAlertType = computed(() => {
  if (registrationMode.value === 'disabled') return 'default'
  if (registrationMode.value === 'invite') return 'success'
  return 'info'
})

const userPanelDescription = computed(() => {
  if (registrationMode.value === 'approval') {
    return '待批准用户激活后才能登录并创建插件提交请求。'
  }
  if (registrationMode.value === 'invite') {
    return '邀请码注册用户默认已激活；这里仍可禁用异常账号。'
  }
  return '公开注册已关闭；这里可查看和禁用已有用户。'
})

const invalidateUsers = () => queryClient.invalidateQueries({ queryKey: ['users'] })
const invalidateInvites = () => queryClient.invalidateQueries({ queryKey: ['invites'] })

const policyMutation = useMutation({
  mutationFn: (mode: RegistrationMode) => updateSystemConfig({ USER_REGISTRATION_MODE: mode }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.config.system() })
    message.success('注册策略已保存')
  },
  onError: (err) => {
    error.value = err
  },
})

const approveMutation = useMutation({
  mutationFn: approveUser,
  onSuccess: invalidateUsers,
  onError: (err) => {
    error.value = err
  },
})

const disableUserMutation = useMutation({
  mutationFn: disableUser,
  onSuccess: invalidateUsers,
  onError: (err) => {
    error.value = err
  },
})

const createInviteMutation = useMutation({
  mutationFn: createInvite,
  onSuccess: (invite) => {
    createdInviteCode.value = invite.code || ''
    inviteForm.max_uses = 1
    inviteForm.expires_at = null
    inviteForm.note = ''
    return invalidateInvites()
  },
  onError: (err) => {
    error.value = err
  },
})

const disableInviteMutation = useMutation({
  mutationFn: disableInvite,
  onSuccess: invalidateInvites,
  onError: (err) => {
    error.value = err
  },
})

const savingPolicy = computed(() => policyMutation.isPending.value)
const creatingInvite = computed(() => createInviteMutation.isPending.value)

const userColumns = computed<DataTableColumns<UserSummary>>(() => [
  { title: '用户名', key: 'username', minWidth: 160 },
  {
    title: '邮箱',
    key: 'email',
    minWidth: 220,
    render: (row) => row.email || '-',
  },
  {
    title: '角色',
    key: 'role',
    width: 100,
    render: (row) => h(NTag, { size: 'small', round: true }, { default: () => row.role }),
  },
  {
    title: '状态',
    key: 'status',
    width: 130,
    render: (row) =>
      h(
        NTag,
        { size: 'small', round: true, type: userStatusType(row.status) },
        { default: () => userStatusLabel(row.status) },
      ),
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
    width: 180,
    align: 'right',
    render(row) {
      return h(NSpace, { justify: 'end', size: 'small' }, () => [
        row.status === 'pending_approval'
          ? h(
              NButton,
              {
                size: 'small',
                type: 'primary',
                loading: approveMutation.isPending.value,
                onClick: () => approveMutation.mutate(row.id),
              },
              { default: () => '批准' },
            )
          : null,
        row.status !== 'disabled'
          ? h(
              NPopconfirm,
              { onPositiveClick: () => disableUserMutation.mutate(row.id) },
              {
                trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '禁用' }),
                default: () => '禁用后该用户不能继续登录，确认继续？',
              },
            )
          : null,
      ])
    },
  },
])

const inviteColumns = computed<DataTableColumns<InviteSummary>>(() => [
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', round: true, type: row.status === 'active' ? 'success' : 'default' },
        { default: () => (row.status === 'active' ? '可用' : '已禁用') },
      ),
  },
  {
    title: '使用',
    key: 'used_count',
    width: 120,
    render: (row) => `${row.used_count} / ${row.max_uses}`,
  },
  {
    title: '过期时间',
    key: 'expires_at',
    width: 150,
    render: (row) => formatDateTime(row.expires_at),
  },
  {
    title: '备注',
    key: 'note',
    minWidth: 260,
    render: (row) => row.note || '-',
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
    width: 120,
    align: 'right',
    render(row) {
      if (row.status !== 'active') return null
      return h(
        NPopconfirm,
        { onPositiveClick: () => disableInviteMutation.mutate(row.id) },
        {
          trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '禁用' }),
          default: () => '禁用后该邀请码不能继续注册，确认继续？',
        },
      )
    },
  },
])

function saveRegistrationPolicy() {
  error.value = null
  policyMutation.mutate(registrationMode.value)
}

function createInviteCode() {
  error.value = null
  createdInviteCode.value = ''
  createInviteMutation.mutate({
    max_uses: inviteForm.max_uses,
    expires_at: inviteForm.expires_at ? new Date(inviteForm.expires_at).toISOString() : null,
    note: inviteForm.note || null,
  })
}

function normalizeRegistrationMode(value: string | undefined): RegistrationMode {
  if (value === 'invite' || value === 'approval') return value
  return 'disabled'
}

function userStatusLabel(status: UserStatus) {
  if (status === 'pending_approval') return '待批准'
  if (status === 'active') return '已激活'
  return '已禁用'
}

function userStatusType(status: UserStatus) {
  if (status === 'active') return 'success'
  if (status === 'pending_approval') return 'warning'
  return 'default'
}
</script>

<style scoped>
.users-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(280px, 420px) minmax(0, 1fr);
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 16px;
  min-width: 0;
  padding: 18px;
}

.panel.full {
  grid-column: 1 / -1;
}

.policy-panel {
  gap: 14px;
}

.panel-head {
  align-items: flex-start;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  min-width: 0;
}

.panel-head h2 {
  font-size: 18px;
  line-height: 24px;
  margin: 0;
}

.panel-head p {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 20px;
  margin: 4px 0 0;
}

.mode-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
}

.mode-options {
  max-width: 100%;
}

.invite-form {
  max-width: 360px;
}

.status-filter {
  width: 140px;
}

.created-code {
  max-width: 100%;
}

.code-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.code-row > span {
  color: var(--text-muted);
  font-size: 13px;
}

@media (max-width: 1100px) {
  .users-grid {
    grid-template-columns: 1fr;
  }
}
</style>
