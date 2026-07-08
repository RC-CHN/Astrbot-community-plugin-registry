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
export type ScanProviderName = string

export type ScanProviderResult = {
  pass: boolean | null
  msg: string | null
  mode: ScanMode
}

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
  [provider: ScanProviderName]: ScanProviderResult | string | string[] | null | undefined
  scanned_at?: string | null
  required_providers?: string[] | null
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

export type ArtifactTreeEntry = {
  path: string
  name: string
  kind: 'dir' | 'file'
  size: number | null
}

export type ArtifactTreeResponse = {
  entries: ArtifactTreeEntry[]
}

export type ArtifactFileResponse = {
  path: string
  name: string
  size: number
  language: string
  content: string | null
  truncated: boolean
  binary: boolean
}

export type RegistryStats = {
  total_plugins: number
  total_active_versions: number
  total_downloads: number
  total_installs: number
}

export type RegistryMd5 = {
  md5: string
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

export type WorkerTaskStatus =
  | 'queued'
  | 'delayed'
  | 'running'
  | 'retrying'
  | 'succeeded'
  | 'failed'
  | 'dead'
  | 'cancelled'

export type WorkerTaskSummary = {
  id: string
  task_type: string
  status: WorkerTaskStatus
  plugin_id: string | null
  version_id: string | null
  provider: string | null
  payload_summary: Record<string, unknown>
  attempts: number
  max_attempts: number
  queued_at: string | null
  started_at: string | null
  finished_at: string | null
  next_run_at: string | null
  worker_id: string | null
  duration_ms: number | null
  last_error: string | null
  created_at: string | null
  updated_at: string | null
}

export type WorkerTaskListParams = {
  status?: WorkerTaskStatus | ''
  type?: string
  plugin_id?: string
  version_id?: string
  page?: number
  page_size?: number
}

export type WorkerTaskListResponse = {
  items: WorkerTaskSummary[]
  total: number
  page: number
  page_size: number
}

export type WorkerHeartbeat = {
  worker_id: string
  hostname?: string | null
  pid?: number | null
  heartbeat_at?: string | null
  current_task_id?: string | null
}

export type WorkerStatusResponse = {
  redis_connected: boolean
  queue_length: number
  delayed_length: number
  dead_letter_length: number
  active_workers: WorkerHeartbeat[]
  tasks_by_status: Record<WorkerTaskStatus | string, number>
}
