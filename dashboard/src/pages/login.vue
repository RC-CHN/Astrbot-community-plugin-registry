<template>
  <section class="login-panel">
    <div class="heading">
      <h1>AstrBot Plugin Registry</h1>
      <p class="muted">管理插件提交、构建与发布</p>
    </div>
    <api-error-alert :error="error" />
    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="login" tab="登录">
        <n-form :model="form" label-placement="top" @submit.prevent="handleLogin">
          <n-form-item label="用户名">
            <n-input v-model:value="form.username" autocomplete="username" />
          </n-form-item>
          <n-form-item label="密码">
            <n-input
              v-model:value="form.password"
              autocomplete="current-password"
              type="password"
              show-password-on="click"
            />
          </n-form-item>
          <n-button type="primary" block :loading="loading" @click="handleLogin">登录</n-button>
        </n-form>
      </n-tab-pane>

      <n-tab-pane name="register" tab="注册">
        <n-alert v-if="registrationMode === 'disabled'" type="info" :bordered="false">
          当前实例未开放公开注册，请联系管理员创建账号。
        </n-alert>
        <template v-else>
          <n-alert v-if="registrationMode === 'approval'" type="info" :bordered="false" class="register-note">
            注册后需要管理员批准，激活前不能创建插件提交请求。
          </n-alert>
          <n-form :model="registerForm" label-placement="top" @submit.prevent="handleRegister">
            <n-form-item label="用户名">
              <n-input v-model:value="registerForm.username" autocomplete="username" placeholder="3-50 个字符" />
            </n-form-item>
            <n-form-item label="邮箱">
              <n-input v-model:value="registerForm.email" autocomplete="email" placeholder="用于接收管理员反馈" />
            </n-form-item>
            <n-form-item label="密码">
              <n-input
                v-model:value="registerForm.password"
                autocomplete="new-password"
                type="password"
                show-password-on="click"
                placeholder="至少 12 个字符"
              />
            </n-form-item>
            <n-form-item v-if="registrationMode === 'invite'" label="邀请码">
              <n-input v-model:value="registerForm.invite_code" autocomplete="off" />
            </n-form-item>
            <n-form-item v-if="powRequired" label="人机验证">
              <div class="pow-box">
                <div>
                  <div class="pow-title">{{ powStatusText }}</div>
                  <div class="pow-meta">
                    提交注册时自动完成 PoW 校验，不需要手动填写图片验证码。
                  </div>
                </div>
                <n-tag :type="powStatus === 'done' ? 'success' : powStatus === 'idle' ? 'default' : 'info'" size="small">
                  {{ powStatus === 'done' ? '已完成' : powStatus === 'idle' ? '待提交' : '计算中' }}
                </n-tag>
              </div>
            </n-form-item>
            <n-button type="primary" block :loading="registering" @click="handleRegister">
              {{ registering ? '正在计算 PoW 并注册' : '注册账号' }}
            </n-button>
          </n-form>
        </template>
      </n-tab-pane>
    </n-tabs>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import { getCurrentUser, getRegisterChallenge, getRegistrationConfig, login, register } from '@/api/auth'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import { useAuthStore } from '@/stores/auth'
import type { RegistrationMode } from '@/api/types'
import { solveRegistrationPow } from '@/utils/pow'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const message = useMessage()
const activeTab = ref<'login' | 'register'>('login')
const loading = ref(false)
const registering = ref(false)
const error = ref<unknown>(null)
const registrationMode = ref<RegistrationMode>('disabled')
const powRequired = ref(true)
const powAttempts = ref(0)
const powDifficulty = ref<number | null>(null)
const powStatus = ref<'idle' | 'fetching' | 'solving' | 'done'>('idle')
const form = reactive({ username: 'admin', password: '' })
const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  invite_code: '',
})

const powStatusText = computed(() => {
  if (powStatus.value === 'fetching') return '正在获取验证挑战'
  if (powStatus.value === 'solving') {
    const attempts = powAttempts.value > 0 ? `，已尝试 ${powAttempts.value.toLocaleString()} 次` : ''
    const difficulty = powDifficulty.value ? `难度 ${powDifficulty.value}` : '计算中'
    return `${difficulty}${attempts}`
  }
  if (powStatus.value === 'done') return '验证已完成'
  return '提交时自动验证'
})

onMounted(loadRegistrationConfig)

async function handleLogin() {
  loading.value = true
  error.value = null
  try {
    const result = await login(form)
    auth.setSession(result.access_token, form.username)
    const user = await getCurrentUser()
    auth.setUser(user.username, user.role)
    message.success('登录成功')
    await router.push(String(route.query.redirect || (user.role === 'user' ? '/submissions' : '/plugins')))
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

async function loadRegistrationConfig() {
  try {
    const config = await getRegistrationConfig()
    registrationMode.value = config.mode
    powRequired.value = config.pow_required
  } catch {
    registrationMode.value = 'disabled'
    powRequired.value = true
  }
}

async function handleRegister() {
  if (registrationMode.value === 'disabled') return
  const validationError = validateRegisterForm()
  if (validationError) {
    error.value = { status: 400, message: validationError }
    return
  }
  registering.value = true
  error.value = null
  powAttempts.value = 0
  powDifficulty.value = null
  powStatus.value = 'fetching'
  try {
    const challenge = await getRegisterChallenge()
    powDifficulty.value = challenge.difficulty
    powStatus.value = 'solving'
    const nonce = await solveRegistrationPow(challenge.challenge_id, challenge.salt, challenge.difficulty, {
      timeoutMs: 45000,
      onProgress: (attempts) => {
        powAttempts.value = attempts
      },
    })
    powStatus.value = 'done'
    const result = await register({
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password,
      invite_code: registerForm.invite_code || null,
      challenge_id: challenge.challenge_id,
      nonce,
    })
    if (result.status === 'active') {
      message.success('注册成功，可以登录')
      form.username = registerForm.username
      form.password = ''
      activeTab.value = 'login'
    } else {
      message.info('注册成功，等待管理员批准')
    }
  } catch (err) {
    error.value = err
    powStatus.value = 'idle'
  } finally {
    registering.value = false
  }
}

function validateRegisterForm() {
  if (!registerForm.username.trim()) return '用户名不能为空。'
  if (!registerForm.email.trim()) return '邮箱不能为空。'
  if (!registerForm.password) return '密码不能为空。'
  if (registerForm.password.length < 12) return '密码至少需要 12 个字符。'
  if (registrationMode.value === 'invite' && !registerForm.invite_code.trim()) return '邀请码不能为空。'
  return ''
}
</script>

<style scoped>
.login-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow-md);
  display: grid;
  gap: 18px;
  padding: 28px;
  width: min(420px, 100%);
}

.heading h1 {
  font-size: 22px;
  line-height: 30px;
  margin: 0;
}

.heading p {
  margin: 4px 0 0;
}

.register-note {
  margin-bottom: 14px;
}

.pow-box {
  align-items: center;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  min-height: 54px;
  padding: 10px 12px;
  width: 100%;
}

.pow-title {
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
}

.pow-meta {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 18px;
  margin-top: 2px;
}
</style>
