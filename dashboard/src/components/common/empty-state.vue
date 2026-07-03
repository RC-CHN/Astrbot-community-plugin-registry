<template>
  <n-empty :description="description">
    <template v-if="$slots.action" #extra>
      <slot name="action" />
    </template>
  </n-empty>
</template>

<script setup lang="ts">
defineProps<{
  description: string
}>()
</script>
