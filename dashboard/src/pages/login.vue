<template>
  <section class="login-panel">
    <div class="heading">
      <h1>AstrBot Plugin Registry</h1>
      <p class="muted">管理插件提交、构建与发布</p>
    </div>
    <api-error-alert :error="error" />
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
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

import { login } from '@/api/auth'
import ApiErrorAlert from '@/components/common/api-error-alert.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const message = useMessage()
const loading = ref(false)
const error = ref<unknown>(null)
const form = reactive({ username: 'admin', password: '' })

async function handleLogin() {
  loading.value = true
  error.value = null
  try {
    const result = await login(form)
    auth.setSession(result.access_token, form.username)
    message.success('登录成功')
    await router.push(String(route.query.redirect || '/plugins'))
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-panel {
  background: var(--surface);
  border: 1px solid var(--divider);
  border-radius: 8px;
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
</style>
