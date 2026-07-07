import type { BuildStatus, PluginStatus, VersionStatus } from '@/api/types'

export type StatusKind = 'plugin' | 'version' | 'build' | 'scan'

export type StatusMeta = {
  label: string
  type: 'default' | 'success' | 'warning' | 'error' | 'info'
}

export const pluginStatusMeta: Record<PluginStatus, StatusMeta> = {
  pending: { label: '待审核', type: 'warning' },
  active: { label: '已启用', type: 'success' },
  disabled: { label: '已禁用', type: 'default' },
  deleted: { label: '已删除', type: 'error' },
}

export const versionStatusMeta: Record<VersionStatus, StatusMeta> = {
  draft: { label: '草稿', type: 'info' },
  active: { label: '发布候选', type: 'success' },
  deprecated: { label: '已废弃', type: 'default' },
  deleted: { label: '已删除', type: 'error' },
}

export const buildStatusMeta: Record<BuildStatus, StatusMeta> = {
  pending: { label: '排队中', type: 'warning' },
  building: { label: '构建中', type: 'info' },
  success: { label: '构建成功', type: 'success' },
  failed: { label: '构建失败', type: 'error' },
  scanning: { label: '扫描中', type: 'info' },
}

export function scanStatusMeta(pass?: boolean | null): StatusMeta {
  if (pass === true) return { label: '通过', type: 'success' }
  if (pass === false) return { label: '未通过', type: 'error' }
  return { label: '未扫描', type: 'warning' }
}
