<script setup lang="ts">
import { computed } from 'vue'
import { getCurrentUser } from '../../api/auth'

const user = getCurrentUser() || { nickname: '游客' }
const nickname = computed(() => user.nickname || '游客')
</script>

<template>
  <main class="page-content">
    <header class="page-header">
      <div class="header-title">设备管理</div>
      <div class="header-meta">欢迎，{{ nickname }}</div>
    </header>
    <section class="workspace">
      <div class="child-page">
        <h2>设备管理</h2>
        <p>设备列表、状态监控、远程控制等功能。</p>
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
