<template>
  <article class="source-copy-card" :class="{ featured }">
    <div class="source-copy-head">
      <div class="source-copy-title">
        <strong>{{ label }}</strong>
        <span v-if="description">{{ description }}</span>
      </div>
      <div class="source-copy-actions">
        <n-button size="small" :type="featured ? 'primary' : 'default'" secondary @click="copy">
          <template #icon><n-icon :component="Copy" /></template>
          复制
        </n-button>
        <n-button size="small" quaternary tag="a" :href="value" target="_blank">
          <template #icon><n-icon :component="ExternalLink" /></template>
          打开
        </n-button>
      </div>
    </div>
    <code class="source-copy-value" :title="value">{{ value }}</code>
  </article>
</template>

<script setup lang="ts">
import { useMessage } from 'naive-ui'
import { Copy, ExternalLink } from 'lucide-vue-next'

const props = defineProps<{
  label: string
  value: string
  description?: string
  featured?: boolean
}>()

const message = useMessage()

async function copy() {
  await navigator.clipboard.writeText(props.value)
  message.success('已复制')
}
</script>

<style scoped>
.source-copy-card {
  background: var(--surface);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
}

.source-copy-card.featured {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.08);
}

.source-copy-head {
  align-items: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
  min-width: 0;
}

.source-copy-title {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.source-copy-title strong {
  color: var(--text-primary);
  font-size: 13px;
}

.source-copy-title span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.source-copy-actions {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.source-copy-value {
  background: var(--surface-hover);
  border: 1px solid var(--divider);
  border-radius: 6px;
  color: var(--text-primary);
  display: block;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  min-width: 0;
  overflow: hidden;
  padding: 8px 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .source-copy-head {
    align-items: stretch;
    flex-direction: column;
  }

  .source-copy-actions {
    justify-content: flex-start;
  }
}
</style>
