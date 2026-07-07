import type { ScanProviderResult, ScanSummary } from '@/api/types'

export type ScanProviderEntry = {
  provider: string
  result: ScanProviderResult
}

const PROVIDER_ORDER = ['clamav', 'virustotal', 'llm_agent']

export function scanProviderEntries(scan: ScanSummary | null): ScanProviderEntry[] {
  if (!scan) return []
  const entries: ScanProviderEntry[] = []
  for (const [provider, value] of Object.entries(scan)) {
    if (provider !== 'scanned_at' && isScanProviderResult(value)) {
      entries.push({ provider, result: value })
    }
  }
  return entries.sort(
    (a, b) => providerRank(a.provider) - providerRank(b.provider) || a.provider.localeCompare(b.provider),
  )
}

export function providerLabel(provider: string): string {
  const labels: Record<string, string> = {
    clamav: 'ClamAV',
    virustotal: 'VirusTotal',
    llm_agent: 'LLM Agent',
  }
  return labels[provider] || provider
}

export function scanHasPending(scan: ScanSummary | null): boolean {
  return scanProviderEntries(scan).some(({ result }) => result.mode === 'pending')
}

export function scanHasBlockingResult(scan: ScanSummary | null): boolean {
  return scanProviderEntries(scan).some(({ result }) => {
    if (result.mode === 'skipped') return false
    if (result.mode === 'pending' || result.mode === 'error') return true
    if (result.pass === false) return true
    return result.pass === null
  })
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
