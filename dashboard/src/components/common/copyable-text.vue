<template>
  <span class="copyable">
    <span class="mono text" :title="value || undefined">{{ compactValue }}</span>
    <n-button quaternary size="tiny" @click.stop="copy">
      <template #icon><n-icon :component="Copy" /></template>
    </n-button>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMessage } from 'naive-ui'
import { Copy } from 'lucide-vue-next'

const props = defineProps<{
  value?: string | null
  max?: number
}>()

const message = useMessage()
const compactValue = computed(() => {
  const value = props.value || '-'
  const max = props.max || 18
  if (value.length <= max) return value
  return `${value.slice(0, Math.max(max - 6, 6))}...${value.slice(-6)}`
})

async function copy() {
  if (!props.value) return
  await navigator.clipboard.writeText(props.value)
  message.success('已复制')
}
</script>

<style scoped>
.copyable {
  align-items: center;
  display: inline-flex;
  gap: 2px;
  max-width: 100%;
}

.text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
