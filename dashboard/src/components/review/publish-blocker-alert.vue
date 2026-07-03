<template>
  <n-alert v-if="blockers.length" type="warning" :bordered="false">
    <div>当前版本不能发布</div>
    <ul>
      <li v-for="item in blockers" :key="item">{{ item }}</li>
    </ul>
  </n-alert>
</template>

<script setup lang="ts">
defineProps<{
  blockers: string[]
}>()
</script>

<style scoped>
ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
</style>
