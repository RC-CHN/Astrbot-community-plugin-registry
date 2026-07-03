import type { BuildStatus, PluginStatus, ScanSummary, VersionStatus } from '@/api/types'
import {
  buildStatusMeta,
  pluginStatusMeta,
  scanStatusMeta,
  versionStatusMeta,
  type StatusMeta,
} from '@/constants/status'

export function getPluginStatusMeta(status: PluginStatus): StatusMeta {
  return pluginStatusMeta[status]
}

export function getVersionStatusMeta(status: VersionStatus): StatusMeta {
  return versionStatusMeta[status]
}

export function getBuildStatusMeta(status: BuildStatus): StatusMeta {
  return buildStatusMeta[status]
}

export function getScanAggregateMeta(scan: ScanSummary | null): StatusMeta {
  if (!scan) return scanStatusMeta(null)
  const modes = [scan.virustotal.mode, scan.llm_agent.mode]
  if (modes.some((mode) => mode === 'pending')) return { label: '扫描中', type: 'info' }
  const values = [scan.virustotal.pass, scan.llm_agent.pass]
  if (values.some((value) => value === false)) return scanStatusMeta(false)
  if (modes.every((mode) => mode === 'skipped')) return { label: '已略过', type: 'warning' }
  if (modes.some((mode) => mode === 'skipped')) return { label: '部分略过', type: 'warning' }
  if (values.every(Boolean)) return scanStatusMeta(true)
  return scanStatusMeta(null)
}
