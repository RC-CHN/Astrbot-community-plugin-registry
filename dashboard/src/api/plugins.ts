import { apiRequest } from './client'
import type {
  PluginDetail,
  PluginListParams,
  PluginListResponse,
  PluginStatus,
  SubmitPluginRequest,
  SubmitPluginResponse,
  VersionStatus,
  VersionSubmitResponse,
  VersionSummary,
} from './types'

export function listPlugins(params: PluginListParams) {
  return apiRequest<PluginListResponse>('/admin/plugins', { query: params })
}

export function listPendingPlugins() {
  return apiRequest<PluginListResponse['items']>('/admin/plugins/pending')
}

export function getPlugin(id: string) {
  return apiRequest<PluginDetail>(`/admin/plugins/${id}`)
}

export function listVersions(pluginId: string) {
  return apiRequest<VersionSummary[]>(`/admin/plugins/${pluginId}/versions`)
}

export function submitPlugin(data: SubmitPluginRequest) {
  return apiRequest<SubmitPluginResponse>('/admin/plugins', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function uploadPlugin(file: File) {
  const body = new FormData()
  body.append('file', file)
  return apiRequest<VersionSubmitResponse>('/admin/plugins/upload', {
    method: 'POST',
    body,
  })
}

export function updatePluginStatus(pluginId: string, status: PluginStatus) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  })
}

export function updateVersionStatus(pluginId: string, versionId: string, status: VersionStatus) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/versions/${versionId}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  })
}

export function setLatestVersion(pluginId: string, versionId: string) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/versions/${versionId}/latest`, {
    method: 'PUT',
    body: JSON.stringify({ is_latest: true }),
  })
}

export function refreshCache() {
  return apiRequest<{ status: string }>('/admin/cache/refresh', { method: 'POST' })
}
