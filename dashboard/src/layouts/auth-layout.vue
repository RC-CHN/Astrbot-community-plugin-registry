<template>
  <main class="auth-layout">
    <router-view />
  </main>
</template>

<style scoped>
.auth-layout {
  align-items: center;
  background: var(--page-bg);
  display: flex;
  min-height: 100vh;
  padding: 24px;
  justify-content: center;
}
</style>
