<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isMenuGroup, menuConfig } from '../../config/menu'

const route = useRoute()
const router = useRouter()
const siblings = computed(() => {
  for (const entry of menuConfig) if (isMenuGroup(entry) && entry.children.some(item => item.route === route.path)) return entry.children
  return []
})
</script>

<template><nav class="data-tabs"><button v-for="item in siblings" :key="item.route" :class="{active:route.path===item.route}" @click="router.push(item.route)">{{item.name}}</button></nav></template>

<style scoped>
.data-tabs{display:flex;gap:4px;padding:4px;margin-bottom:18px;border-radius:14px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.05);flex-shrink:0;overflow-x:auto}.data-tabs button{padding:10px 20px;border:0;border-radius:10px;background:transparent;color:#64748b;font-size:14px;cursor:pointer;white-space:nowrap}.data-tabs button:hover{background:#f1f5f9}.data-tabs button.active{color:#fff;background:#3b82f6}
</style>
