import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    siderCollapsed: false,
  }),
  actions: {
    toggleSider() {
      this.siderCollapsed = !this.siderCollapsed
    },
  },
})
