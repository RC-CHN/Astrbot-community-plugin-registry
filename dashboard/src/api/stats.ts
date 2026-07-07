import { apiRequest } from './client'
import type { AdminStats, RegistryMd5, RegistryStats } from './types'

export function getRegistryStats() {
  return apiRequest<RegistryStats>('/stats', { auth: false })
}

export function getRegistryMd5() {
  return apiRequest<RegistryMd5>('/plugins-md5', { auth: false })
}

export function getAdminStats() {
  return apiRequest<AdminStats>('/admin/stats')
}
