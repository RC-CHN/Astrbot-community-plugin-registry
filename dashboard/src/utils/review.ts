import type { TagProps } from 'naive-ui'

type TagType = NonNullable<TagProps['type']>

export function reviewStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '人工审核待处理',
    approved: '人工审核通过',
    skipped: '人工审核跳过',
    rejected: '人工审核拒绝',
  }
  return labels[status] || status
}

export function humanReviewMeta(status: string): { label: string; type: TagType } {
  const meta: Record<string, { label: string; type: TagType }> = {
    pending: { label: '待处理', type: 'warning' },
    approved: { label: '通过', type: 'success' },
    skipped: { label: '跳过', type: 'default' },
    rejected: { label: '拒绝', type: 'error' },
  }
  return meta[status] || { label: status, type: 'default' }
}
