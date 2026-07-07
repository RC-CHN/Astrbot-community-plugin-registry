import type { PluginDetail, VersionSummary } from '@/api/types'
import { scanHasBlockingResult, scanHasPending } from '@/utils/scans'

export function getVersionBlockers(
  plugin: PluginDetail,
  version: VersionSummary,
  options: { includePluginStatus?: boolean; includeVersionStatus?: boolean } = {},
): string[] {
  const includePluginStatus = options.includePluginStatus ?? true
  const includeVersionStatus = options.includeVersionStatus ?? true
  const blockers: string[] = []
  if (includePluginStatus && plugin.status !== 'active') blockers.push('插件尚未审核通过')
  if (includeVersionStatus && version.version_status !== 'active') blockers.push('版本尚未标记为发布候选')
  if (version.build_status === 'building' || version.build_status === 'pending') {
    blockers.push('构建仍在进行')
  } else if (version.build_status === 'scanning') {
    blockers.push('扫描仍在进行')
  } else if (version.build_status !== 'success') {
    blockers.push('构建未成功')
  }
  if (scanHasPending(version.scan)) {
    blockers.push('扫描仍在进行')
  } else if (scanHasBlockingResult(version.scan)) {
    blockers.push('扫描未通过')
  }
  return [...new Set(blockers)]
}

export function canActivateVersion(version: VersionSummary): { ok: boolean; reason: string } {
  if (version.build_status !== 'success') {
    return { ok: false, reason: '构建未成功，不能标记为发布候选' }
  }
  if (scanHasPending(version.scan)) {
    return { ok: false, reason: '扫描仍在进行，不能标记为发布候选' }
  }
  if (scanHasBlockingResult(version.scan)) {
    return { ok: false, reason: '扫描未通过，不能标记为发布候选' }
  }
  return { ok: true, reason: '' }
}
