import type { PluginListParams } from '@/api/types'

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
  config: {
    system: () => ['config', 'system'] as const,
  },
}
