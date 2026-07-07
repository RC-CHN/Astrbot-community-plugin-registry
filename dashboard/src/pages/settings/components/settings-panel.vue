<template>
  <section class="settings-section">
    <header class="section-head">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <slot name="extra" />
    </header>

    <div class="settings-groups">
      <div v-for="group in groups" :key="group.title" class="settings-group">
        <header class="group-head">
          <h3>{{ group.title }}</h3>
          <p>{{ group.description }}</p>
        </header>
        <div class="field-list">
          <setting-field
            v-for="item in group.items"
            :key="item.key"
            :item="item"
            :value="getValue(item)"
            :dirty="isDirty(item)"
            :overridden="isOverridden(item)"
            :sensitive-configured="isSensitiveConfigured(item)"
            :loading="isLoading(item)"
            :can-clear="canClear(item)"
            :provider-options="providerOptions"
            @update-value="$emit('update-value', item, $event)"
            @clear="$emit('clear', item)"
          />
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import SettingField from './setting-field.vue'
import type { ConfigItem, ProviderOption, SettingsGroup } from '../types'

withDefaults(
  defineProps<{
    title: string
    description: string
    groups: SettingsGroup[]
    getValue: (item: ConfigItem) => string
    isDirty: (item: ConfigItem) => boolean
    isOverridden: (item: ConfigItem) => boolean
    isSensitiveConfigured: (item: ConfigItem) => boolean
    isLoading: (item: ConfigItem) => boolean
    canClear: (item: ConfigItem) => boolean
    providerOptions?: ProviderOption[]
  }>(),
  {
    providerOptions: () => [],
  },
)

defineEmits<{
  (event: 'update-value', item: ConfigItem, value: string): void
  (event: 'clear', item: ConfigItem): void
}>()
</script>

<style scoped>
.settings-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 0;
  min-width: 0;
  padding: 22px 26px;
}

.section-head {
  align-items: flex-start;
  border-bottom: 1px solid #e5edf5;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  min-width: 0;
  padding-bottom: 16px;
}

.section-head h2 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
  line-height: 26px;
  margin: 0 0 4px;
}

.section-head p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

.settings-groups {
  display: grid;
  margin-top: 16px;
  min-width: 0;
}

.settings-group {
  min-width: 0;
}

.settings-group + .settings-group {
  border-top: 1px solid #e5edf5;
  margin-top: 20px;
  padding-top: 18px;
}

.group-head {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding-bottom: 10px;
}

.group-head h3 {
  color: #202938;
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
  margin: 0;
}

.group-head p {
  color: #7a8696;
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

.field-list {
  border-top: 1px solid #cfd8e3;
  display: grid;
  min-width: 0;
}

@media (max-width: 860px) {
  .section-head {
    display: grid;
  }
}
</style>
