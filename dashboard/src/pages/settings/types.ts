import type { Component } from 'vue'

export type ConfigInput = 'text' | 'textarea' | 'number' | 'boolean' | 'providers'
export type ConfigScope = '即时生效' | '新任务生效' | '新产物生效' | '扫描时生效'
export type ConfigGroup =
  | 'registry'
  | 'limits'
  | 'git'
  | 'scan-policy'
  | 'virustotal'
  | 'clamav'
  | 'llm'
  | 'worker'
  | 'webhook'

export type ConfigItem = {
  key: string
  label: string
  group: ConfigGroup
  input: ConfigInput
  scope: ConfigScope
  description: string
  sensitive?: boolean
  advanced?: boolean
  placeholder?: string
  unit?: string
  min?: number
}

export type ProviderOption = {
  label: string
  value: string
}

export type SettingsGroup = {
  title: string
  description: string
  items: ConfigItem[]
}

export type SettingsViewKey = 'registry' | 'build' | 'scan' | 'providers' | 'ops' | 'deployment'

export type SettingsNavItem = {
  key: SettingsViewKey
  label: string
  description: string
  icon: Component
}
