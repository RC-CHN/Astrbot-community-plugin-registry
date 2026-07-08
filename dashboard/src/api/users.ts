import { apiRequest } from './client'
import type {
  InviteCreateRequest,
  InviteListResponse,
  InviteSummary,
  UserListResponse,
  UserStatus,
  UserSummary,
} from './types'

export function listUsers(params: { role?: string; status?: UserStatus | '' } = {}) {
  return apiRequest<UserListResponse>('/admin/users', {
    query: params,
  })
}

export function approveUser(userId: string) {
  return apiRequest<UserSummary>(`/admin/users/${userId}/approve`, {
    method: 'POST',
  })
}

export function disableUser(userId: string) {
  return apiRequest<UserSummary>(`/admin/users/${userId}/disable`, {
    method: 'POST',
  })
}

export function listInvites() {
  return apiRequest<InviteListResponse>('/admin/invites')
}

export function createInvite(data: InviteCreateRequest) {
  return apiRequest<InviteSummary>('/admin/invites', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function disableInvite(inviteId: string) {
  return apiRequest<InviteSummary>(`/admin/invites/${inviteId}/disable`, {
    method: 'POST',
  })
}
