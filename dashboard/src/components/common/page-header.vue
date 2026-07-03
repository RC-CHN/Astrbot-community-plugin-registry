<template>
  <div class="page-header">
    <div>
      <div class="page-title-row">
        <h1>{{ title }}</h1>
        <slot name="status" />
      </div>
      <p v-if="description" class="muted">{{ description }}</p>
    </div>
    <div class="page-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style scoped>
.page-header {
  align-items: flex-start;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title-row {
  align-items: center;
  display: flex;
  gap: 10px;
}

h1 {
  font-size: 20px;
  line-height: 28px;
  margin: 0;
}

p {
  margin: 4px 0 0;
}

.page-actions {
  align-items: center;
  display: flex;
  gap: 8px;
}
</style>
