import { apiRequest } from './client'
import type { AdminStats, RegistryStats } from './types'

export function getRegistryStats() {
  return apiRequest<RegistryStats>('/stats', { auth: false })
}

export function getAdminStats() {
  return apiRequest<AdminStats>('/admin/stats')
}
