import { defineStore } from 'pinia'

const TOKEN_KEY = 'astrbot_registry_token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: localStorage.getItem('astrbot_registry_username') || '',
    role: localStorage.getItem('astrbot_registry_role') || '',
  }),
  actions: {
    setSession(token: string, username: string, role = '') {
      this.token = token
      this.username = username
      this.role = role
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem('astrbot_registry_username', username)
      localStorage.setItem('astrbot_registry_role', role)
    },
    setUser(username: string, role: string) {
      this.username = username
      this.role = role
      localStorage.setItem('astrbot_registry_username', username)
      localStorage.setItem('astrbot_registry_role', role)
    },
    clearSession() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('astrbot_registry_username')
      localStorage.removeItem('astrbot_registry_role')
    },
  },
})
