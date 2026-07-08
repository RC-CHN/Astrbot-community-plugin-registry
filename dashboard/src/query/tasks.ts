import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type Ref } from 'vue'

import { getWorkerStatus, listTasks, retryTask } from '@/api/tasks'
import type { WorkerTaskListParams } from '@/api/types'
import { queryKeys } from './keys'

export function useTasks(params: Ref<WorkerTaskListParams>) {
  return useQuery({
    queryKey: computed(() => queryKeys.tasks.list(params.value)),
    queryFn: () => listTasks(params.value),
    refetchInterval: 3000,
  })
}

export function useWorkerStatus() {
  return useQuery({
    queryKey: queryKeys.tasks.status(),
    queryFn: getWorkerStatus,
    refetchInterval: 3000,
  })
}

export function useTaskMutations() {
  const queryClient = useQueryClient()
  const invalidateTasks = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['tasks'] }),
      queryClient.invalidateQueries({ queryKey: ['plugins'] }),
    ])

  return {
    retry: useMutation({
      mutationFn: ({ taskId }: { taskId: string }) => retryTask(taskId),
      onSuccess: invalidateTasks,
    }),
  }
}
