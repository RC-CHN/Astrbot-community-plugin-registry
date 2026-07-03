export type TokenResponse = {
  access_token: string
  token_type: string
}

export type LoginRequest = {
  username: string
  password: string
}

export type PluginStatus = 'pending' | 'active' | 'disabled' | 'deleted'
export type ReviewStatus = 'pending' | 'approved' | 'skipped' | 'rejected'
export type VersionStatus = 'draft' | 'active' | 'deprecated' | 'deleted'
export type BuildStatus = 'pending' | 'building' | 'success' | 'failed' | 'scanning'
export type ScanMode = 'pending' | 'real' | 'skipped' | 'error'

export type PluginSummary = {
  id: string
  plugin_key: string
  display_name: string | null
  author: string
  status: PluginStatus
  review_status: ReviewStatus
  category: string | null
  version_count: number
  created_at: string | null
  updated_at: string | null
}

export type ScanSummary = {
  virustotal: { pass: boolean | null; msg: string | null; mode: ScanMode }
  llm_agent: { pass: boolean | null; msg: string | null; mode: ScanMode }
  scanned_at?: string | null
}

export type VersionSummary = {
  id: string
  version: string
  source_type: 'git_auto' | 'manual_upload'
  commit_sha: string | null
  build_status: BuildStatus
  build_log: string | null
  version_status: VersionStatus
  is_latest: boolean
  download_url: string | null
  file_size: number | null
  created_at: string | null
  updated_at: string | null
  scan: ScanSummary | null
}

export type PluginDetail = PluginSummary & {
  description: string
  repo_url: string | null
  social_link: string | null
  tags: string[]
  support_platforms: string[]
  astrbot_version: string | null
  versions: VersionSummary[]
}

export type PluginListParams = {
  status?: PluginStatus | ''
  q?: string
  page?: number
  page_size?: number
}

export type PluginListResponse = {
  items: PluginSummary[]
  total: number
  page: number
  page_size: number
}

export type SubmitPluginRequest = {
  repo_url: string
  ref?: string
  version?: string
  changelog?: string
}

export type SubmitPluginResponse = {
  plugin_id: string
  version: string
  status: string
}

export type VersionSubmitResponse = {
  plugin_id?: string | null
  version_id?: string | null
  version?: string | null
  status?: string | null
}

export type RegistryStats = {
  total_plugins: number
  total_active_versions: number
  total_downloads: number
  total_installs: number
}

export type AdminStats = {
  total_plugins: number
  pending_plugins: number
}

export type SystemConfigResponse = {
  values: Record<string, string>
  effective_values: Record<string, string>
  sensitive_status: Record<string, boolean>
  sensitive_keys: string[]
  deployment_values: Record<string, string>
}

export type ApiError = {
  status: number
  message: string
  detail?: unknown
}
