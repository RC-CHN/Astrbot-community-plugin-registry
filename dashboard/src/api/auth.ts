import { apiRequest } from './client'
import type { LoginRequest, TokenResponse } from './types'

export function login(data: LoginRequest) {
  return apiRequest<TokenResponse>('/admin/login', {
    method: 'POST',
    auth: false,
    body: JSON.stringify(data),
  })
}
