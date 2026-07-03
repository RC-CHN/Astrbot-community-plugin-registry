import { defineStore } from 'pinia'

const TOKEN_KEY = 'astrbot_registry_token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: localStorage.getItem('astrbot_registry_username') || '',
  }),
  actions: {
    setSession(token: string, username: string) {
      this.token = token
      this.username = username
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem('astrbot_registry_username', username)
    },
    clearSession() {
      this.token = ''
      this.username = ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('astrbot_registry_username')
    },
  },
})
