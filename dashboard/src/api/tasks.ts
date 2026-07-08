import { apiRequest } from './client'
import type { WorkerStatusResponse, WorkerTaskListParams, WorkerTaskListResponse, WorkerTaskSummary } from './types'

export function listTasks(params: WorkerTaskListParams) {
  return apiRequest<WorkerTaskListResponse>('/admin/tasks', { query: params })
}

export function getTask(taskId: string) {
  return apiRequest<WorkerTaskSummary>(`/admin/tasks/${taskId}`)
}

export function retryTask(taskId: string) {
  return apiRequest<{ status: string; task_id: string }>(`/admin/tasks/${taskId}/retry`, {
    method: 'POST',
  })
}

export function getWorkerStatus() {
  return apiRequest<WorkerStatusResponse>('/admin/worker/status')
}
