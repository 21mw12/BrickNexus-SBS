<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { getCurrentUser } from '../../api/auth'

const route = useRoute()
const user = getCurrentUser() || { nickname: '游客' }
const nickname = computed(() => user.nickname || '游客')
const title = computed(() => (route.meta.title as string) || '子页面')
</script>

<template>
  <main class="page-content">
    <header class="page-header">
      <div class="header-title">{{ title }}</div>
      <div class="header-meta">欢迎，{{ nickname }}</div>
    </header>
    <section class="workspace">
      <div class="child-page">
        <h2>{{ title }}</h2>
        <p>此处为 {{ title }} 的详细内容区域。</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page-content {
  flex: 1;
  padding: 28px 32px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 20px 24px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}
.header-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}
.header-meta {
  font-size: 14px;
  color: #475569;
}
.workspace {
  min-height: calc(100vh - 132px);
}
.child-page h2 {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}
.child-page p {
  color: #64748b;
  margin: 0;
}
</style>
