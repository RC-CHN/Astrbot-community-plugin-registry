import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type Ref } from 'vue'

import {
  getPlugin,
  listPendingPlugins,
  listPlugins,
  refreshCache,
  setLatestVersion,
  submitPlugin,
  updatePluginStatus,
  updateVersionStatus,
  uploadPlugin,
} from '@/api/plugins'
import type { PluginListParams } from '@/api/types'
import { queryKeys } from './keys'

export function usePlugins(params: Ref<PluginListParams>) {
  return useQuery({
    queryKey: computed(() => queryKeys.plugins.list(params.value)),
    queryFn: () => listPlugins(params.value),
  })
}

export function usePendingPlugins() {
  return useQuery({
    queryKey: queryKeys.plugins.pending(),
    queryFn: listPendingPlugins,
    refetchInterval: 3000,
  })
}

export function usePluginDetail(id: Ref<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.plugins.detail(id.value)),
    queryFn: () => getPlugin(id.value),
    enabled: computed(() => Boolean(id.value)),
  })
}

export function usePluginMutations() {
  const queryClient = useQueryClient()
  const invalidatePlugins = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plugins'] }),
      queryClient.invalidateQueries({ queryKey: ['stats'] }),
    ])

  return {
    submit: useMutation({ mutationFn: submitPlugin, onSuccess: invalidatePlugins }),
    upload: useMutation({ mutationFn: uploadPlugin, onSuccess: invalidatePlugins }),
    updatePluginStatus: useMutation({
      mutationFn: ({ pluginId, status }: Parameters<typeof updatePluginStatus>[0] extends never
        ? never
        : { pluginId: string; status: Parameters<typeof updatePluginStatus>[1] }) =>
        updatePluginStatus(pluginId, status),
      onSuccess: invalidatePlugins,
    }),
    updateVersionStatus: useMutation({
      mutationFn: ({ pluginId, versionId, status }: { pluginId: string; versionId: string; status: Parameters<typeof updateVersionStatus>[2] }) =>
        updateVersionStatus(pluginId, versionId, status),
      onSuccess: invalidatePlugins,
    }),
    setLatest: useMutation({
      mutationFn: ({ pluginId, versionId }: { pluginId: string; versionId: string }) =>
        setLatestVersion(pluginId, versionId),
      onSuccess: invalidatePlugins,
    }),
    refreshCache: useMutation({ mutationFn: refreshCache, onSuccess: invalidatePlugins }),
  }
}
