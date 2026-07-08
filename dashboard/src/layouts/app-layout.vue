<template>
  <n-layout has-sider class="app-shell">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed="ui.siderCollapsed"
      :collapsed-width="64"
      :width="236"
    >
      <div class="brand">
        <n-button quaternary circle size="small" @click="ui.toggleSider">
          <template #icon><n-icon :component="PanelLeftClose" /></template>
        </n-button>
        <span v-if="!ui.siderCollapsed">AstrBot Registry</span>
      </div>
      <n-menu
        :collapsed="ui.siderCollapsed"
        :collapsed-width="64"
        :options="menuOptions"
        :value="activeMenu"
        @update:value="navigate"
      />
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="topbar">
        <n-input v-if="isOperator" v-model:value="globalSearch" clearable placeholder="搜索插件" class="global-search">
          <template #prefix><n-icon :component="Search" /></template>
        </n-input>
        <n-button v-if="isOperator" secondary @click="goPlugins">搜索</n-button>
        <n-button v-if="isOperator" type="primary" @click="showSubmit = true">
          <template #icon><n-icon :component="Plus" /></template>
          提交插件
        </n-button>
        <n-dropdown :options="userOptions" @select="handleUserAction">
          <n-button quaternary>{{ auth.username || 'admin' }}</n-button>
        </n-dropdown>
      </n-layout-header>
      <n-layout-content class="content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
  <plugin-submit-modal v-model:show="showSubmit" />
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NIcon, type MenuOption } from 'naive-ui'
import {
  ClipboardCheck,
  FilePlus2,
  FileJson,
  Hammer,
  PanelLeftClose,
  Plus,
  Search,
  Settings,
  Shield,
  Users,
} from 'lucide-vue-next'

import PluginSubmitModal from '@/components/plugin/plugin-submit-modal.vue'
import { getCurrentUser } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const ui = useUiStore()
const showSubmit = ref(false)
const globalSearch = ref('')
const isOperator = computed(() => auth.role === 'admin' || auth.role === 'reviewer')

onMounted(async () => {
  if (auth.token && !auth.role) {
    try {
      const user = await getCurrentUser()
      auth.setUser(user.username, user.role)
      if (user.role === 'user' && route.path !== '/submissions') {
        await router.replace('/submissions')
      }
    } catch {
      auth.clearSession()
      await router.replace({ name: 'login' })
    }
  }
})

const icon = (component: unknown) => () => h(NIcon, null, { default: () => h(component as never) })

const menuOptions = computed<MenuOption[]>(() => {
  if (!isOperator.value) {
    return [{ label: '我的提交', key: '/submissions', icon: icon(FilePlus2) }]
  }
  return [
    { label: '插件', key: '/plugins', icon: icon(Shield) },
    { label: '提交请求', key: '/submission-requests', icon: icon(FilePlus2) },
    { label: '待审核', key: '/reviews', icon: icon(ClipboardCheck) },
    { label: '任务', key: '/builds', icon: icon(Hammer) },
    { label: '插件源', key: '/source', icon: icon(FileJson) },
    { label: '配置', key: '/settings', icon: icon(Settings) },
    { label: '用户', key: '/users', icon: icon(Users) },
  ]
})

const userOptions = [{ label: '退出登录', key: 'logout' }]
const activeMenu = computed(() => {
  if (route.path.startsWith('/plugins')) return '/plugins'
  if (route.path.startsWith('/submissions')) return '/submissions'
  if (route.path.startsWith('/submission-requests')) return '/submission-requests'
  if (route.path.startsWith('/reviews')) return '/reviews'
  if (route.path.startsWith('/builds')) return '/builds'
  if (route.path.startsWith('/source')) return '/source'
  return route.path
})

function navigate(path: string) {
  router.push(path)
}

function goPlugins() {
  router.push({ path: '/plugins', query: globalSearch.value ? { q: globalSearch.value } : {} })
}

function handleUserAction(key: string) {
  if (key === 'logout') {
    auth.clearSession()
    router.push({ name: 'login' })
  }
}
</script>

<style scoped>
.app-shell {
  height: 100vh;
  overflow: hidden;
}

.brand {
  align-items: center;
  border-bottom: 1px solid var(--divider);
  display: flex;
  font-size: 15px;
  font-weight: 650;
  gap: 8px;
  height: 56px;
  padding: 0 14px;
}

.topbar {
  align-items: center;
  background: var(--surface);
  display: flex;
  gap: 8px;
  height: 56px;
  justify-content: flex-end;
  padding: 0 20px;
}

.global-search {
  max-width: 360px;
}

.content {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
  padding: 24px;
}
</style>
