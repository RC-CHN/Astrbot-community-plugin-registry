<template>
  <div class="page-toolbar">
    <slot />
  </div>
</template>

<style scoped>
.page-toolbar {
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--divider);
  border-radius: 8px;
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
}
</style>
