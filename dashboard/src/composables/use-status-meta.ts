import type { BuildStatus, PluginStatus, ScanSummary, VersionStatus } from '@/api/types'
import {
  buildStatusMeta,
  pluginStatusMeta,
  scanStatusMeta,
  versionStatusMeta,
  type StatusMeta,
} from '@/constants/status'
import { scanHasBlockingResult, scanHasPending, scanProviderEntries } from '@/utils/scans'

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
  const entries = scanProviderEntries(scan)
  if (scan?.required_providers) {
    if (!scan.required_providers.length) return { label: '未启用扫描', type: 'default' }
    if (scanHasPending(scan)) return { label: '扫描中', type: 'info' }
    if (scanHasBlockingResult(scan)) return scanStatusMeta(false)
    return scanStatusMeta(true)
  }
  if (!entries.length) return scanStatusMeta(null)
  const modes = entries.map(({ result }) => result.mode)
  if (modes.some((mode) => mode === 'pending')) return { label: '扫描中', type: 'info' }
  if (modes.every((mode) => mode === 'skipped')) return { label: '已略过', type: 'warning' }
  const activeEntries = entries.filter(({ result }) => result.mode !== 'skipped')
  const values = activeEntries.map(({ result }) => result.pass)
  if (activeEntries.some(({ result }) => result.mode === 'error') || values.some((value) => value === false)) {
    return scanStatusMeta(false)
  }
  if (modes.some((mode) => mode === 'skipped')) return { label: '部分略过', type: 'warning' }
  if (values.every(Boolean)) return scanStatusMeta(true)
  return scanStatusMeta(null)
}
