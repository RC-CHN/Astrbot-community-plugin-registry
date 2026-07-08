<template>
  <n-alert v-if="message" type="error" :bordered="false" class="api-error-alert">
    {{ message }}
  </n-alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  error: unknown
}>()

const message = computed(() => (props.error ? getErrorMessage(props.error) : ''))
</script>

<style scoped>
.api-error-alert {
  white-space: pre-line;
}
</style>
