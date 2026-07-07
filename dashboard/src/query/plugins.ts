import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type Ref } from 'vue'

import {
  deletePlugin,
  getPlugin,
  listPendingPlugins,
  listPlugins,
  publishVersion,
  refreshCache,
  runVersionScanProvider,
  setLatestVersion,
  skipVersionScanProvider,
  submitPlugin,
  triggerVersionScan,
  updatePluginReviewStatus,
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
    refetchInterval: 3000,
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
    updatePluginReviewStatus: useMutation({
      mutationFn: ({ pluginId, status, reviewStatus }: { pluginId: string; status: Parameters<typeof updatePluginStatus>[1]; reviewStatus: Parameters<typeof updatePluginReviewStatus>[2] }) =>
        updatePluginReviewStatus(pluginId, status, reviewStatus),
      onSuccess: invalidatePlugins,
    }),
    deletePlugin: useMutation({
      mutationFn: ({ pluginId }: { pluginId: string }) => deletePlugin(pluginId),
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
    publishVersion: useMutation({
      mutationFn: ({
        pluginId,
        versionId,
        reviewStatus,
      }: {
        pluginId: string
        versionId: string
        reviewStatus: 'approved' | 'skipped'
      }) => publishVersion(pluginId, versionId, reviewStatus),
      onSuccess: invalidatePlugins,
    }),
    triggerScan: useMutation({
      mutationFn: ({ pluginId, versionId }: { pluginId: string; versionId: string }) =>
        triggerVersionScan(pluginId, versionId),
      onSuccess: invalidatePlugins,
    }),
    runScanProvider: useMutation({
      mutationFn: ({ pluginId, versionId, provider }: { pluginId: string; versionId: string; provider: 'virustotal' | 'llm_agent' }) =>
        runVersionScanProvider(pluginId, versionId, provider),
      onSuccess: invalidatePlugins,
    }),
    skipScanProvider: useMutation({
      mutationFn: ({ pluginId, versionId, provider }: { pluginId: string; versionId: string; provider: 'virustotal' | 'llm_agent' }) =>
        skipVersionScanProvider(pluginId, versionId, provider),
      onSuccess: invalidatePlugins,
    }),
    refreshCache: useMutation({ mutationFn: refreshCache, onSuccess: invalidatePlugins }),
  }
}
