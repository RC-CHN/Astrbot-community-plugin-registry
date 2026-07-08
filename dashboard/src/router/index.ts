import { createRouter, createWebHistory } from 'vue-router'

import { routes } from './routes'
import { useAuthStore } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.role === 'user' && to.path !== '/submissions' && to.name !== 'login') {
    return { path: '/submissions' }
  }
  if (to.name === 'login' && auth.token) {
    return { path: String(to.query.redirect || (auth.role === 'user' ? '/submissions' : '/plugins')) }
  }
  return true
})
