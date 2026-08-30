<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchMyProfile, type MyProfile, type PermissionTreeNode } from '../api/user'

const loading = ref(false)
const error = ref('')
const profile = ref<MyProfile | null>(null)

// 平铺资产树，depth 用于缩进
interface FlatRow { node: PermissionTreeNode; depth: number }
function flattenTree(nodes: PermissionTreeNode[], depth = 0): FlatRow[] {
  return nodes.flatMap(node => [
    { node, depth },
    ...(node.sub_assets ? flattenTree(node.sub_assets, depth + 1) : []),
  ])
}

const typeLabels: Record<string, string> = {
  building: '楼宇', floor: '楼层', room: '房间', terminal: '终端', sensor: '传感器',
}

onMounted(async () => {
  loading.value = true
  try {
    profile.value = await fetchMyProfile()
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="page-content">
    <header class="page-header">
      <div class="header-title">个人页面</div>
      <div class="header-meta" v-if="profile">欢迎，{{ profile.nickname }}</div>
    </header>

    <section class="workspace" v-if="loading">
      <div class="card"><p class="empty">加载中...</p></div>
    </section>

    <section class="workspace" v-else-if="error">
      <div class="card"><p class="error-msg">{{ error }}</p></div>
    </section>

    <section class="workspace" v-else-if="profile">
      <!-- 基本信息 -->
      <div class="card">
        <h2>基本信息</h2>
        <div class="info-grid">
          <div class="info-item"><span class="label">昵称</span><span class="value">{{ profile.nickname }}</span></div>
          <div class="info-item"><span class="label">账号</span><span class="value">{{ profile.account }}</span></div>
          <div class="info-item"><span class="label">角色</span><span class="value">{{ profile.role_name }}</span></div>
        </div>
      </div>

      <!-- 可创建资产类型 -->
      <div class="card">
        <h2>资产创建权限</h2>
        <div class="type-tags" v-if="profile.create_types.length > 0">
          <span class="type-tag" v-for="t in profile.create_types" :key="t">{{ typeLabels[t] || t }}</span>
        </div>
        <p class="empty" v-else>无资产创建权限</p>
      </div>

      <!-- 资产实例权限表 -->
      <div class="card">
        <h2>资产实例权限</h2>
        <div class="table-scroll" v-if="profile.asset_tree.length > 0">
          <table class="perm-table">
            <thead>
              <tr>
                <th>资产名</th>
                <th class="col-perm">查看 (R)</th>
                <th class="col-perm">编辑 (U)</th>
                <th class="col-perm">删除 (D)</th>
                <th class="col-perm">操作 (O)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in flattenTree(profile.asset_tree)" :key="row.node.asset_id">
                <td :style="{ paddingLeft: 16 + row.depth * 24 + 'px' }">{{ row.node.name }}</td>
                <td class="col-perm" :class="row.node.permission.includes('R') ? 'granted' : 'denied'">
                  {{ row.node.permission.includes('R') ? '✓' : '✗' }}
                </td>
                <td class="col-perm" :class="row.node.permission.includes('U') ? 'granted' : 'denied'">
                  {{ row.node.permission.includes('U') ? '✓' : '✗' }}
                </td>
                <td class="col-perm" :class="row.node.permission.includes('D') ? 'granted' : 'denied'">
                  {{ row.node.permission.includes('D') ? '✓' : '✗' }}
                </td>
                <td class="col-perm" :class="row.node.permission.includes('O') ? 'granted' : 'denied'">
                  {{ row.node.permission.includes('O') ? '✓' : '✗' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="empty" v-else>无资产实例权限</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page-content { flex: 1; padding: 28px 32px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px; padding: 20px 24px;
  border-radius: 24px; background: #fff;
  box-shadow: 0 10px 30px rgba(15,23,42,0.06);
}
.header-title { font-size: 22px; font-weight: 700; color: #0f172a; }
.header-meta { font-size: 14px; color: #475569; }

.workspace { display: flex; flex-direction: column; gap: 20px; }

/* 卡片 */
.card {
  padding: 28px 32px; border-radius: 24px; background: #fff;
  box-shadow: 0 10px 30px rgba(15,23,42,0.06);
}
.card h2 { margin: 0 0 20px; font-size: 18px; font-weight: 700; color: #0f172a; }

/* 基本信息 */
.info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.info-item { display: flex; align-items: center; gap: 10px; font-size: 15px; }
.label { color: #64748b; font-weight: 500; white-space: nowrap; }
.value { color: #0f172a; font-weight: 600; }

/* 类型标签 */
.type-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.type-tag {
  padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600;
  background: #dbeafe; color: #1e40af;
}

/* 权限表格 */
.table-scroll { overflow-x: auto; }
.perm-table { width: 100%; border-collapse: collapse; }
.perm-table th, .perm-table td {
  padding: 10px 16px; text-align: left; font-size: 14px;
  border-bottom: 1px solid #e2e8f0;
}
.perm-table thead th { font-weight: 600; color: #475569; background: #f8fafc; white-space: nowrap; }
.perm-table tbody tr:hover { background: #f8fafc; }
.perm-table tbody td { color: #334155; }
.col-perm { text-align: center !important; width: 80px; font-weight: 600; }
.granted { background: #dcfce7; color: #16a34a; }
.denied { background: #fee2e2; color: #dc2626; }

.empty { text-align: center; color: #94a3b8; font-size: 14px; padding: 20px 0; margin: 0; }
.error-msg { text-align: center; color: #dc2626; font-size: 14px; }
</style>
