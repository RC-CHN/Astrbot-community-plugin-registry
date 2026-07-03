import { router } from '@/router'
import { useAuthStore } from '@/stores/auth'
import type { ApiError } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type RequestOptions = RequestInit & {
  auth?: boolean
  query?: Record<string, string | number | boolean | null | undefined>
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const auth = useAuthStore()
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(options.query || {})) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }

  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.auth !== false && auth.token) {
    headers.set('Authorization', `Bearer ${auth.token}`)
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    auth.clearSession()
    await router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
  }

  if (!response.ok) {
    throw await normalizeError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

async function normalizeError(response: Response): Promise<ApiError> {
  let detail: unknown
  let message = response.statusText
  try {
    detail = await response.json()
    if (detail && typeof detail === 'object' && 'detail' in detail) {
      message = String((detail as { detail: unknown }).detail)
    }
  } catch {
    message = await response.text()
  }
  return { status: response.status, message, detail }
}
