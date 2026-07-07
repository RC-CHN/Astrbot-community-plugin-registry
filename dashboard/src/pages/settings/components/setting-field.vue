<template>
  <article class="setting-field" :class="{ dirty }">
    <div class="field-label">
      <h3>{{ item.label }}</h3>
      <p class="field-description">{{ item.description }}</p>
      <div class="field-key">
        <code>{{ item.key }}</code>
        <span>{{ item.scope }}</span>
      </div>
      <div v-if="dirty || overridden || item.sensitive" class="field-meta">
        <span v-if="dirty" class="meta-chip unsaved">未保存</span>
        <span v-if="overridden" class="meta-chip override">运行时覆盖</span>
        <span v-if="item.sensitive" class="meta-chip" :class="sensitiveConfigured ? 'configured' : 'missing'">
          {{ sensitiveConfigured ? '密钥已设置' : '密钥未设置' }}
        </span>
      </div>
    </div>

    <div class="field-body">
      <div class="control-shell">
        <n-switch v-if="item.input === 'boolean'" :value="booleanValue" @update:value="updateBoolean" />
        <n-checkbox-group v-else-if="item.input === 'providers'" :value="providerValue" @update:value="updateProviders">
          <n-space :size="12" wrap>
            <n-checkbox v-for="option in providerOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </n-checkbox>
          </n-space>
        </n-checkbox-group>
        <n-input-number
          v-else-if="item.input === 'number'"
          :value="numberValue"
          :min="item.min ?? 0"
          :placeholder="item.unit"
          @update:value="updateNumber"
        />
        <n-input
          v-else
          :value="value"
          :type="item.sensitive ? 'password' : item.input === 'textarea' ? 'textarea' : 'text'"
          :rows="item.input === 'textarea' ? 3 : undefined"
          :placeholder="inputPlaceholder"
          :show-password-on="item.sensitive ? 'click' : undefined"
          @update:value="updateText"
        />
      </div>

      <n-button
        v-if="canClear"
        size="tiny"
        quaternary
        class="field-clear-action"
        :disabled="loading || dirty"
        @click="$emit('clear')"
      >
        <template #icon><n-icon :component="RotateCcw" /></template>
        {{ item.sensitive ? '清空密钥' : '恢复默认' }}
      </n-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NCheckbox, NCheckboxGroup, NIcon, NInput, NInputNumber, NSpace, NSwitch } from 'naive-ui'
import { RotateCcw } from 'lucide-vue-next'

import type { ConfigItem, ProviderOption } from '../types'

const props = withDefaults(
  defineProps<{
    item: ConfigItem
    value: string
    dirty?: boolean
    overridden?: boolean
    sensitiveConfigured?: boolean
    loading?: boolean
    canClear?: boolean
    providerOptions?: ProviderOption[]
  }>(),
  {
    dirty: false,
    overridden: false,
    sensitiveConfigured: false,
    loading: false,
    canClear: false,
    providerOptions: () => [],
  },
)

const emit = defineEmits<{
  (event: 'update-value', value: string): void
  (event: 'clear'): void
}>()

const booleanValue = computed(() => ['1', 'true', 'yes', 'on'].includes(props.value.trim().toLowerCase()))
const numberValue = computed(() => (props.value === '' ? null : Number(props.value)))
const providerValue = computed(() =>
  props.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean),
)
const inputPlaceholder = computed(() => {
  if (!props.item.sensitive) return props.item.placeholder
  return props.sensitiveConfigured ? '输入新值以替换当前密钥' : '输入密钥'
})

function updateText(value: string) {
  emit('update-value', value)
}

function updateBoolean(value: boolean) {
  emit('update-value', value ? 'true' : 'false')
}

function updateNumber(value: number | null) {
  emit('update-value', value === null ? '' : String(value))
}

function updateProviders(value: Array<string | number>) {
  emit('update-value', value.map(String).join(','))
}
</script>

<style scoped>
.setting-field {
  align-items: center;
  display: grid;
  gap: 30px;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  min-width: 0;
  padding: 18px 0;
}

.setting-field + .setting-field {
  border-top: 1px solid var(--border);
}

.setting-field.dirty {
  background: linear-gradient(90deg, rgba(255, 248, 197, 0.36), transparent 58%);
}

.field-label {
  align-content: start;
  display: grid;
  gap: 5px;
  min-width: 0;
}

.field-label h3 {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 700;
  line-height: 22px;
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

.field-body {
  align-content: center;
  border-left: 1px solid var(--divider);
  display: grid;
  gap: 6px;
  min-width: 0;
  padding-left: 18px;
}

.field-description {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

.field-key {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.field-key code {
  color: var(--text-tertiary);
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.field-key span {
  color: var(--text-tertiary);
  font-size: 11px;
  white-space: nowrap;
}

.field-meta {
  align-items: center;
  color: var(--text-tertiary);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 6px;
  line-height: 20px;
  margin-top: 2px;
  min-width: 0;
}

.meta-chip {
  align-items: center;
  border: 1px solid var(--divider);
  border-radius: 999px;
  display: inline-flex;
  font-size: 11px;
  font-weight: 600;
  gap: 4px;
  line-height: 17px;
  min-height: 19px;
  padding: 0 8px;
  white-space: nowrap;
}

.meta-chip.override {
  background: var(--info-bg);
  border-color: #b9d5e8;
  color: var(--info-fg);
}

.meta-chip.unsaved {
  background: var(--warning-bg);
  border-color: #ead889;
  color: var(--warning-fg);
}

.meta-chip.configured {
  background: var(--success-bg);
  border-color: #b7e8c1;
  color: var(--success-fg);
}

.meta-chip.missing {
  background: var(--warning-bg);
  border-color: #ead889;
  color: var(--warning-fg);
}

.control-shell {
  min-width: 0;
}

.control-shell :deep(.n-input),
.control-shell :deep(.n-input-number) {
  width: 100%;
}

.control-shell :deep(.n-switch) {
  margin-top: 2px;
}

.field-clear-action {
  justify-self: end;
  min-width: 0;
}

@media (max-width: 860px) {
  .setting-field {
    grid-template-columns: 1fr;
  }

  .field-body {
    border-left: 0;
    padding-left: 0;
  }

  .field-clear-action {
    justify-self: start;
  }
}
</style>
