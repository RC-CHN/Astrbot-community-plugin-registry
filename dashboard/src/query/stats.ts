import { useQuery } from '@tanstack/vue-query'

import { getAdminStats, getRegistryMd5, getRegistryStats } from '@/api/stats'
import { queryKeys } from './keys'

export function useRegistryStats() {
  return useQuery({
    queryKey: queryKeys.stats.registry(),
    queryFn: getRegistryStats,
  })
}

export function useAdminStats() {
  return useQuery({
    queryKey: queryKeys.stats.admin(),
    queryFn: getAdminStats,
  })
}

export function useRegistryMd5() {
  return useQuery({
    queryKey: queryKeys.source.md5(),
    queryFn: getRegistryMd5,
  })
}
