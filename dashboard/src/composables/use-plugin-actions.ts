import type { PluginDetail, VersionSummary } from '@/api/types'

export function getVersionBlockers(
  plugin: PluginDetail,
  version: VersionSummary,
  options: { includePluginStatus?: boolean } = {},
): string[] {
  const includePluginStatus = options.includePluginStatus ?? true
  const blockers: string[] = []
  if (includePluginStatus && plugin.status !== 'active') blockers.push('插件尚未审核通过')
  if (version.version_status !== 'active') blockers.push('版本未设为可用')
  if (version.build_status !== 'success') blockers.push('构建未成功')
  if (!version.scan) {
    blockers.push('未完成扫描')
  } else if (!version.scan.virustotal.pass || !version.scan.llm_agent.pass) {
    blockers.push('扫描未通过')
  }
  return blockers
}

export function canActivateVersion(version: VersionSummary): { ok: boolean; reason: string } {
  if (version.build_status !== 'success') {
    return { ok: false, reason: '构建未成功，不能设为可用' }
  }
  if (!version.scan || !version.scan.virustotal.pass || !version.scan.llm_agent.pass) {
    return { ok: false, reason: '扫描未通过，不能设为可用' }
  }
  return { ok: true, reason: '' }
}
