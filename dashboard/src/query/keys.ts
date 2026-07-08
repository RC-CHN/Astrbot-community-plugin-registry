import type { PluginListParams, WorkerTaskListParams } from '@/api/types'

export const queryKeys = {
  plugins: {
    list: (params: PluginListParams) => ['plugins', 'list', params] as const,
    pending: () => ['plugins', 'pending'] as const,
    detail: (id: string) => ['plugins', 'detail', id] as const,
    versions: (id: string) => ['plugins', 'versions', id] as const,
  },
  stats: {
    registry: () => ['stats', 'registry'] as const,
    admin: () => ['stats', 'admin'] as const,
  },
  source: {
    md5: () => ['source', 'md5'] as const,
  },
  config: {
    system: () => ['config', 'system'] as const,
  },
  tasks: {
    list: (params: WorkerTaskListParams) => ['tasks', 'list', params] as const,
    status: () => ['tasks', 'worker-status'] as const,
  },
}
