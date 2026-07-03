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
  const values = [scan.virustotal.pass, scan.llm_agent.pass]
  if (values.every(Boolean)) return scanStatusMeta(true)
  if (values.some((value) => value === false)) return scanStatusMeta(false)
  return scanStatusMeta(null)
}
