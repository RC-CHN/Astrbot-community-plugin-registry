import type { RouteRecordRaw } from 'vue-router'

import AppLayout from '@/layouts/app-layout.vue'
import AuthLayout from '@/layouts/auth-layout.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    component: AuthLayout,
    children: [{ path: '', name: 'login', component: () => import('@/pages/login.vue') }],
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', redirect: '/plugins' },
      { path: 'submissions', name: 'submissions', component: () => import('@/pages/submissions/index.vue') },
      { path: 'submission-requests', name: 'submission-requests', component: () => import('@/pages/submission-requests/index.vue') },
      { path: 'plugins', name: 'plugins', component: () => import('@/pages/plugins/index.vue') },
      { path: 'plugins/:id', name: 'plugin-detail', component: () => import('@/pages/plugins/detail.vue') },
      { path: 'reviews', name: 'reviews', component: () => import('@/pages/reviews/index.vue') },
      { path: 'builds', name: 'builds', component: () => import('@/pages/builds/index.vue') },
      { path: 'stats', redirect: '/source' },
      { path: 'source', name: 'source', component: () => import('@/pages/source/index.vue') },
      { path: 'settings', name: 'settings', component: () => import('@/pages/settings/index.vue') },
      { path: 'users', name: 'users', component: () => import('@/pages/users/index.vue') },
    ],
  },
]
