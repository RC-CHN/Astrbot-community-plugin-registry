import { apiRequest } from './client'
import type { SystemConfigResponse } from './types'

export function getSystemConfig() {
  return apiRequest<SystemConfigResponse>('/admin/config')
}

export function updateSystemConfig(values: Record<string, string>) {
  return apiRequest<SystemConfigResponse>('/admin/config', {
    method: 'PUT',
    body: JSON.stringify({ values }),
  })
}
