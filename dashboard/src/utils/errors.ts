import type { ApiError } from '@/api/types'

export function getErrorMessage(error: unknown): string {
  const validationMessage = formatValidationError(error)
  if (validationMessage) return validationMessage

  if (error && typeof error === 'object' && 'message' in error) {
    const message = String((error as ApiError).message)
    return message === '[object Object]' ? '请求失败' : message
  }
  return '请求失败'
}

type ValidationIssue = {
  type?: string
  loc?: Array<string | number>
  msg?: string
  ctx?: Record<string, unknown>
}

function formatValidationError(error: unknown) {
  const issues = getValidationIssues(error)
  if (!issues.length) return ''
  return issues.map(formatValidationIssue).join('\n')
}

function getValidationIssues(error: unknown): ValidationIssue[] {
  if (!error || typeof error !== 'object') return []
  const apiError = error as ApiError
  const detail = apiError.detail
  if (!detail || typeof detail !== 'object') return []
  const payloadDetail = 'detail' in detail ? (detail as { detail: unknown }).detail : detail
  return Array.isArray(payloadDetail) ? payloadDetail.filter(isValidationIssue) : []
}

function isValidationIssue(value: unknown): value is ValidationIssue {
  return Boolean(value && typeof value === 'object' && ('loc' in value || 'msg' in value))
}

function formatValidationIssue(issue: ValidationIssue) {
  const label = fieldLabel(issue.loc)
  const message = translateValidationIssue(issue)
  return label ? `${label}：${message}` : message
}

function fieldLabel(loc: ValidationIssue['loc']) {
  const field = loc?.filter((item) => item !== 'body').at(-1)
  if (field === undefined) return ''
  return fieldLabels[String(field)] || String(field)
}

function translateValidationIssue(issue: ValidationIssue) {
  const minLength = issue.ctx?.min_length
  const maxLength = issue.ctx?.max_length
  if (issue.type === 'missing') return '不能为空。'
  if (issue.type === 'string_too_short' && typeof minLength === 'number') {
    return `至少需要 ${minLength} 个字符。`
  }
  if (issue.type === 'string_too_long' && typeof maxLength === 'number') {
    return `不能超过 ${maxLength} 个字符。`
  }
  if (issue.type === 'string_pattern_mismatch') return '格式不正确。'
  if (issue.type === 'value_error') return issue.msg || '取值不合法。'
  return issue.msg || '输入不合法。'
}

const fieldLabels: Record<string, string> = {
  admin_message: '管理员说明',
  challenge_id: '验证挑战',
  email: '邮箱',
  invite_code: '邀请码',
  nonce: '人机验证',
  password: '密码',
  ref: 'Ref',
  ref_type: 'Ref 类型',
  repo_url: '仓库地址',
  user_message: '提交说明',
  username: '用户名',
}
