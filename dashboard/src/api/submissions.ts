import { apiRequest } from './client'
import type {
  SubmissionCreateRequest,
  SubmissionDecisionRequest,
  SubmissionListResponse,
  SubmissionRequest,
  SubmissionStatus,
} from './types'

export function listMySubmissions() {
  return apiRequest<SubmissionListResponse>('/submissions')
}

export function createSubmission(data: SubmissionCreateRequest) {
  return apiRequest<SubmissionRequest>('/submissions', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function listAdminSubmissions(params: { status?: SubmissionStatus | '' } = {}) {
  return apiRequest<SubmissionListResponse>('/admin/submissions', {
    query: params,
  })
}

export function acceptSubmission(id: string, data: SubmissionDecisionRequest) {
  return apiRequest<SubmissionRequest>(`/admin/submissions/${id}/accept`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function rejectSubmission(id: string, data: SubmissionDecisionRequest) {
  return apiRequest<SubmissionRequest>(`/admin/submissions/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function markSubmissionDuplicate(id: string, data: SubmissionDecisionRequest) {
  return apiRequest<SubmissionRequest>(`/admin/submissions/${id}/duplicate`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
