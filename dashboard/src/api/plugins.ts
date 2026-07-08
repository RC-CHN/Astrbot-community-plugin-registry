import { apiRequest } from './client'
import type {
  PluginDetail,
  ArtifactFileResponse,
  ArtifactTreeResponse,
  PluginListParams,
  PluginListResponse,
  PluginStatus,
  RepoInspectRequest,
  RepoInspectResponse,
  RepoResolveRequest,
  RepoResolveResponse,
  ReviewStatus,
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

export function inspectRepo(data: RepoInspectRequest) {
  return apiRequest<RepoInspectResponse>('/admin/plugins/inspect-repo', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function resolveRepoRef(data: RepoResolveRequest) {
  return apiRequest<RepoResolveResponse>('/admin/plugins/resolve-ref', {
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

export function updatePluginReviewStatus(pluginId: string, status: PluginStatus, reviewStatus: ReviewStatus) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status, review_status: reviewStatus }),
  })
}

export function deletePlugin(pluginId: string) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}`, {
    method: 'DELETE',
  })
}

export function deleteVersion(pluginId: string, versionId: string) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/versions/${versionId}`, {
    method: 'DELETE',
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

export function publishVersion(pluginId: string, versionId: string, reviewStatus: 'approved' | 'skipped') {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/versions/${versionId}/publish`, {
    method: 'POST',
    body: JSON.stringify({ review_status: reviewStatus }),
  })
}

export function triggerVersionScan(pluginId: string, versionId: string) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/scan`, {
    method: 'POST',
    query: { version_id: versionId },
  })
}

export function runVersionScanProvider(pluginId: string, versionId: string, provider: string) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/versions/${versionId}/scans/${provider}/run`, {
    method: 'POST',
  })
}

export function skipVersionScanProvider(pluginId: string, versionId: string, provider: string) {
  return apiRequest<{ status: string }>(`/admin/plugins/${pluginId}/versions/${versionId}/scans/${provider}/skip`, {
    method: 'POST',
  })
}

export function getVersionArtifactTree(pluginId: string, versionId: string) {
  return apiRequest<ArtifactTreeResponse>(`/admin/plugins/${pluginId}/versions/${versionId}/artifact/tree`)
}

export function getVersionArtifactFile(pluginId: string, versionId: string, path: string) {
  return apiRequest<ArtifactFileResponse>(`/admin/plugins/${pluginId}/versions/${versionId}/artifact/file`, {
    query: { path },
  })
}

export function refreshCache() {
  return apiRequest<{ status: string }>('/admin/cache/refresh', { method: 'POST' })
}
