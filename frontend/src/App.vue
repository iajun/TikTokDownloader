<template>
  <a-config-provider :theme="theme">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

const theme = reactive({
  token: {
    colorPrimary: '#1890ff',
  },
})
</script>

<style>
#app {
  min-height: 100vh;
}
</style>
