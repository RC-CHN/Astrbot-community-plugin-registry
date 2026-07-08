import { apiRequest } from './client'
import type {
  LoginRequest,
  CurrentUserResponse,
  RegisterChallengeResponse,
  RegisterRequest,
  RegisterResponse,
  RegistrationConfigResponse,
  TokenResponse,
} from './types'

export function login(data: LoginRequest) {
  return apiRequest<TokenResponse>('/admin/login', {
    method: 'POST',
    auth: false,
    body: JSON.stringify(data),
  })
}

export function getCurrentUser() {
  return apiRequest<CurrentUserResponse>('/auth/me')
}

export function getRegistrationConfig() {
  return apiRequest<RegistrationConfigResponse>('/auth/register/config', {
    auth: false,
  })
}

export function getRegisterChallenge() {
  return apiRequest<RegisterChallengeResponse>('/auth/register/challenge', {
    auth: false,
  })
}

export function register(data: RegisterRequest) {
  return apiRequest<RegisterResponse>('/auth/register', {
    method: 'POST',
    auth: false,
    body: JSON.stringify(data),
  })
}
