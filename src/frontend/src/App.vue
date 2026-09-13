<script setup lang="ts">
import AppNotificationHost from './components/AppNotificationHost.vue'
</script>

<template>
  <router-view />
  <AppNotificationHost />
</template>

<style>
:root {
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: #102a43;
  background: #f8fafc;
}
html,
body,
#app {
  margin: 0;
  min-height: 100%;
}
button {
  font: inherit;
}
</style>
