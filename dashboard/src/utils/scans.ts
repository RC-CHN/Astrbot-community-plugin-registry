import type { ScanProviderResult, ScanSummary } from '@/api/types'

export type ScanProviderEntry = {
  provider: string
  result: ScanProviderResult
}

export type ScanFinding = {
  severity?: string
  category?: string
  file?: string
  reason?: string
  recommendation?: string
  raw: unknown
}

export type ScanMetric = {
  label: string
  value: string
}

export type ParsedScanMessage =
  | {
      kind: 'json'
      raw: string
      data: Record<string, unknown>
      summary: string
      riskLevel: string
      contextTruncated: boolean | null
      findings: ScanFinding[]
    }
  | {
      kind: 'metrics'
      raw: string
      title: string
      metrics: ScanMetric[]
    }
  | {
      kind: 'text'
      raw: string
      text: string
    }

const PROVIDER_ORDER = ['clamav', 'virustotal', 'llm_agent']

export const SCAN_ACTION_PROVIDERS = [
  { provider: 'clamav', label: 'ClamAV' },
  { provider: 'virustotal', label: 'VirusTotal' },
  { provider: 'llm_agent', label: 'LLM' },
]

export function scanProviderEntries(scan: ScanSummary | null): ScanProviderEntry[] {
  if (!scan) return []
  const enabled = enabledScanProviders(scan)
  const entries: ScanProviderEntry[] = []
  for (const [provider, value] of Object.entries(scan)) {
    if (enabled && !enabled.includes(provider)) continue
    if (provider !== 'scanned_at' && isScanProviderResult(value)) {
      entries.push({ provider, result: value })
    }
  }
  return entries.sort(
    (a, b) => providerRank(a.provider) - providerRank(b.provider) || a.provider.localeCompare(b.provider),
  )
}

export function enabledScanActionProviders(scan: ScanSummary | null) {
  const enabled = enabledScanProviders(scan)
  if (!enabled) return SCAN_ACTION_PROVIDERS
  return SCAN_ACTION_PROVIDERS.filter((item) => enabled.includes(item.provider))
}

export function providerLabel(provider: string): string {
  const labels: Record<string, string> = {
    clamav: 'ClamAV',
    virustotal: 'VirusTotal',
    llm_agent: 'LLM Agent',
  }
  return labels[provider] || provider
}

export function scanResultMeta(result: ScanProviderResult) {
  if (result.mode === 'pending') return { label: '扫描中', type: 'info' as const }
  if (result.mode === 'skipped') return { label: '已略过', type: 'warning' as const }
  if (result.mode === 'error' || result.pass === false) return { label: '未通过', type: 'error' as const }
  if (result.pass === true) return { label: '通过', type: 'success' as const }
  return { label: '无结果', type: 'default' as const }
}

export function modeLabel(mode: string) {
  const labels: Record<string, string> = {
    pending: '等待结果',
    real: '真实扫描',
    skipped: '已略过',
    error: '扫描错误',
  }
  return labels[mode] || mode
}

export function passLabel(value: boolean | null, mode: string) {
  if (mode === 'pending') return '等待结果'
  if (value === true) return '通过'
  if (value === false) return '未通过'
  return '无结果'
}

export function scanHasPending(scan: ScanSummary | null): boolean {
  const required = requiredProviderResults(scan)
  if (required) return required.some((result) => !result || result.mode === 'pending')
  return scanProviderEntries(scan).some(({ result }) => result.mode === 'pending')
}

export function scanHasBlockingResult(scan: ScanSummary | null): boolean {
  const required = requiredProviderResults(scan)
  const results = required || scanProviderEntries(scan).map(({ result }) => result)
  return results.some((result) => {
    if (!result) return true
    if (result.mode === 'skipped') return false
    if (result.mode === 'pending' || result.mode === 'error') return true
    if (result.pass === false) return true
    return result.pass === null
  })
}

export function parseScanMessage(message: string | null): ParsedScanMessage | null {
  const text = message?.trim()
  if (!text) return null

  const json = parseJsonObject(text)
  if (json) {
    return {
      kind: 'json',
      raw: text,
      data: json,
      summary: stringValue(json.summary),
      riskLevel: stringValue(json.risk_level),
      contextTruncated: typeof json.context_truncated === 'boolean' ? json.context_truncated : null,
      findings: normalizeFindings(json.findings),
    }
  }

  const metrics = parseMetricsMessage(text)
  if (metrics) return metrics

  return { kind: 'text', raw: text, text }
}

export function scanMessagePreview(result: ScanProviderResult): string {
  const parsed = parseScanMessage(result.msg)
  if (!parsed) return modeLabel(result.mode)
  if (parsed.kind === 'json') {
    return parsed.summary || parsed.findings[0]?.reason || parsed.raw
  }
  if (parsed.kind === 'metrics') {
    return parsed.metrics.slice(0, 4).map((metric) => `${metric.label}=${metric.value}`).join(' · ') || parsed.title
  }
  return parsed.text
}

export function formatRawScanMessage(message: string | null): string {
  if (!message) return ''
  const json = parseJsonObject(message)
  return json ? JSON.stringify(json, null, 2) : message
}

function isScanProviderResult(value: unknown): value is ScanProviderResult {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<ScanProviderResult>
  return typeof candidate.mode === 'string' && 'pass' in candidate
}

function providerRank(provider: string): number {
  const index = PROVIDER_ORDER.indexOf(provider)
  return index === -1 ? PROVIDER_ORDER.length : index
}

function requiredProviderResults(scan: ScanSummary | null): Array<ScanProviderResult | null> | null {
  const enabled = enabledScanProviders(scan)
  if (!scan || !enabled) return null
  const byProvider = new Map(scanProviderEntries(scan).map((entry) => [entry.provider, entry.result]))
  return enabled.map((provider) => byProvider.get(provider) || null)
}

function enabledScanProviders(scan: ScanSummary | null): string[] | null {
  if (!scan || !Array.isArray(scan.required_providers)) return null
  return scan.required_providers.filter((provider): provider is string => typeof provider === 'string')
}

function parseJsonObject(text: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null
  } catch {
    return null
  }
}

function parseMetricsMessage(text: string): ParsedScanMessage | null {
  const [title, detail] = splitMessageTitle(text)
  if (!detail) return null
  const metrics = detail
    .split(',')
    .map((part) => part.trim())
    .map((part) => {
      const separator = part.indexOf('=')
      if (separator === -1) return null
      const label = part.slice(0, separator).trim()
      const value = part.slice(separator + 1).trim()
      return label && value ? { label, value } : null
    })
    .filter((metric): metric is ScanMetric => Boolean(metric))
  return metrics.length ? { kind: 'metrics', raw: text, title, metrics } : null
}

function splitMessageTitle(text: string): [string, string] {
  const index = text.indexOf(':')
  if (index === -1) return ['', '']
  return [text.slice(0, index).trim(), text.slice(index + 1).trim()]
}

function normalizeFindings(value: unknown): ScanFinding[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      return { reason: String(item), raw: item }
    }
    const record = item as Record<string, unknown>
    return {
      severity: stringValue(record.severity),
      category: stringValue(record.category),
      file: stringValue(record.file),
      reason: stringValue(record.reason),
      recommendation: stringValue(record.recommendation),
      raw: item,
    }
  })
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}
