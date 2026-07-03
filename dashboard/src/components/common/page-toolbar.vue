<template>
  <div class="page-toolbar">
    <slot />
  </div>
</template>

<style scoped>
.page-toolbar {
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow-sm);
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
}
</style>
