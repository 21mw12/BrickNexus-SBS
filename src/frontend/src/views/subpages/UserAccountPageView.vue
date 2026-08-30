<script setup lang="ts">
import { ref, reactive, computed, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { menuConfig, isMenuGroup } from '../../config/menu'
import { fetchRoles, fetchAccounts, deleteAccount, resetPassword, type RoleInfo, type AccountInfo } from '../../api/user'
import CreateAccountModal from '../modals/account/CreateAccountModal.vue'
import EditAccountModal from '../modals/account/EditAccountModal.vue'
import ConfirmModal from '../modals/ConfirmModal.vue'

const router = useRouter()
const route = useRoute()

// ---------- 同级子页导航 ----------
const siblings = computed(() => {
  for (const entry of menuConfig) {
    if (isMenuGroup(entry)) {
      const match = entry.children.find(c => c.route === route.path)
      if (match) {
        return entry.children
      }
    }
  }
  return []
})

const currentName = computed(() => {
  const sib = siblings.value.find(s => s.route === route.path)
  return sib?.name || ''
})

function goTo(path: string) {
  router.push(path)
}

// ---------- 角色列表 ----------
const roleList = ref<RoleInfo[]>([])

async function loadRoles() {
  try {
    roleList.value = await fetchRoles()
  } catch (e) {
    console.error('获取角色列表失败', e)
  }
}

// ---------- 查询表单 ----------
const queryForm = reactive({
  account: '',
  role_id: '',
})

// ---------- 账号列表 ----------
const accounts = ref<AccountInfo[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const tableArea = ref<HTMLElement | null>(null)
let tableResizeObserver: ResizeObserver | null = null
let tableResizeTimer: ReturnType<typeof setTimeout> | null = null
const total = ref(0)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function search(page = 1) {
  loading.value = true
  currentPage.value = page
  try {
    const result = await fetchAccounts(page, pageSize.value, {
      account: queryForm.account || undefined,
      role_id: queryForm.role_id || undefined,
    })
    accounts.value = result.data
    total.value = result.total
  } catch (e) {
    console.error('查询账号失败', e)
  } finally {
    loading.value = false
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  search(page)
}

function adjustPageSize() {
  if (!tableArea.value) return
  const nextSize = Math.max(3, Math.min(50, Math.floor((tableArea.value.clientHeight - 44) / 49)))
  if (nextSize !== pageSize.value) { pageSize.value = nextSize; search(1) }
}
function schedulePageSize() { if (tableResizeTimer) clearTimeout(tableResizeTimer); tableResizeTimer = setTimeout(adjustPageSize, 120) }

function clearForm() {
  queryForm.account = ''
  queryForm.role_id = ''
}

// ---------- 新增弹窗 ----------
const showCreateModal = ref(false)

// ---------- 删除确认 ----------
const showDeleteModal = ref(false)
const deleteTarget = ref<AccountInfo | null>(null)
const deleteError = ref('')
const deleteLoading = ref(false)

function handleDelete(row: AccountInfo) {
  deleteTarget.value = row
  deleteError.value = ''
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await deleteAccount(deleteTarget.value.user_id)
    showDeleteModal.value = false
    search()
  } catch (e: any) {
    deleteError.value = e?.message || '删除失败'
  } finally {
    deleteLoading.value = false
  }
}

// ---------- 编辑弹窗 ----------
const showEditModal = ref(false)
const editTarget = ref<AccountInfo | null>(null)

function handleEdit(row: AccountInfo) {
  editTarget.value = row
  showEditModal.value = true
}

// ---------- 重置密码 ----------
const showResetPwdModal = ref(false)
const resetPwdTarget = ref<AccountInfo | null>(null)
const resetPwdError = ref('')
const resetPwdLoading = ref(false)

function handleResetPassword(row: AccountInfo) {
  resetPwdTarget.value = row
  resetPwdError.value = ''
  showResetPwdModal.value = true
}

async function confirmResetPassword() {
  if (!resetPwdTarget.value) return
  resetPwdError.value = ''
  resetPwdLoading.value = true
  try {
    await resetPassword(resetPwdTarget.value.user_id)
    showResetPwdModal.value = false
  } catch (e: any) {
    resetPwdError.value = e?.message || '重置密码失败'
  } finally {
    resetPwdLoading.value = false
  }
}

// ---------- 操作按钮 ----------

// ---------- 生命周期 ----------
onMounted(async () => { loadRoles(); await nextTick(); adjustPageSize(); if (!loading.value) search(); tableResizeObserver = new ResizeObserver(schedulePageSize); if (tableArea.value) tableResizeObserver.observe(tableArea.value) })
onBeforeUnmount(() => { tableResizeObserver?.disconnect(); if (tableResizeTimer) clearTimeout(tableResizeTimer) })
</script>

<template>
  <main class="page-content">
    <section class="workspace">
      <!-- 同级子页导航 -->
      <nav class="sibling-tabs" v-if="siblings.length > 1">
        <button
          v-for="sib in siblings"
          :key="sib.route"
          class="sibling-tab"
          :class="{ active: route.path === sib.route }"
          @click="goTo(sib.route)"
        >
          <img v-if="sib.icon" :src="sib.icon" class="sibling-tab-icon" alt="" />
          <span>{{ sib.name }}</span>
        </button>
      </nav>

      <!-- 页面内容 -->
      <div class="page-body">
        <div class="content-card">
          <!-- 标题 -->
          <div class="card-header">
            <h2>{{ currentName }}</h2>
          </div>

          <!-- 查询 / 操作栏 -->
          <div class="toolbar">
            <div class="toolbar-left">
              <div class="field">
                <label class="field-label">账户名称</label>
                <input
                  v-model="queryForm.account"
                  type="text"
                  placeholder="请输入账户名称"
                  class="field-input"
                  @keyup.enter="search()"
                />
              </div>
              <div class="field">
                <label class="field-label">所属角色</label>
                <select v-model="queryForm.role_id" class="field-select">
                  <option value="">全部</option>
                  <option
                    v-for="role in roleList"
                    :key="role.role_id"
                    :value="role.role_id"
                  >
                    {{ role.name }}
                  </option>
                </select>
              </div>
            </div>
            <div class="toolbar-right">
              <button class="btn btn-outline" @click="clearForm">清空</button>
              <button class="btn btn-primary" @click="search()">查询</button>
              <button class="btn btn-success" @click="showCreateModal = true">新增</button>
            </div>
          </div>

          <!-- 数据表格 -->
          <div ref="tableArea" class="table-area">
          <table class="data-table" v-if="accounts.length > 0">
            <thead>
              <tr>
                <th>账号名</th>
                <th>昵称</th>
                <th>所属角色</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in accounts" :key="row.user_id">
                <td>{{ row.account }}</td>
                <td>{{ row.nickname }}</td>
                <td>{{ row.role_name }}</td>
                <td class="actions-cell">
                  <button class="action-btn" @click="handleResetPassword(row)">重置密码</button>
                  <button class="action-btn" @click="handleEdit(row)">编辑</button>
                  <button class="action-btn action-danger" @click="handleDelete(row)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 加载中 -->
          <div class="empty-state" v-if="loading">
            <p>加载中...</p>
          </div>

          <!-- 空状态 -->
          <div class="empty-state" v-else-if="accounts.length === 0">
            <p>暂无数据</p>
          </div>
          </div>

          <!-- 分页 -->
          <div class="pagination" v-if="total > 0">
            <span class="pagination-info">共 {{ total }} 条 · {{ totalPages }} 页</span>
            <button
              class="page-btn"
              :disabled="currentPage <= 1"
              @click="goToPage(1)"
              title="首页"
            >«</button>
            <button
              class="page-btn"
              :disabled="currentPage <= 1"
              @click="goToPage(currentPage - 1)"
              title="上一页"
            >‹</button>
            <button
              v-for="p in totalPages"
              :key="p"
              class="page-btn"
              :class="{ active: p === currentPage }"
              @click="goToPage(p)"
            >{{ p }}</button>
            <button
              class="page-btn"
              :disabled="currentPage >= totalPages"
              @click="goToPage(currentPage + 1)"
              title="下一页"
            >›</button>
            <button
              class="page-btn"
              :disabled="currentPage >= totalPages"
              @click="goToPage(totalPages)"
              title="末页"
            >»</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 新增账号弹窗 -->
    <CreateAccountModal
      :visible="showCreateModal"
      :roleList="roleList"
      @close="showCreateModal = false"
      @created="search()"
    />

    <!-- 编辑账号弹窗 -->
    <EditAccountModal
      :visible="showEditModal"
      :roleList="roleList"
      :account="editTarget"
      @close="showEditModal = false"
      @updated="search()"
    />

    <!-- 重置密码确认弹窗 -->
    <ConfirmModal
      :visible="showResetPwdModal"
      title="重置密码"
      :message="`确定要重置账号「${resetPwdTarget?.account ?? ''}」的密码吗？`"
      confirmText="重置"
      :danger="true"
      :error="resetPwdError"
      :loading="resetPwdLoading"
      @confirm="confirmResetPassword"
      @cancel="showResetPwdModal = false"
    />

    <!-- 删除确认弹窗 -->
    <ConfirmModal
      :visible="showDeleteModal"
      title="删除账号"
      :message="`确定要删除账号「${deleteTarget?.account ?? ''}」吗？此操作不可恢复。`"
      confirmText="删除"
      :danger="true"
      :error="deleteError"
      :loading="deleteLoading"
      @confirm="confirmDelete"
      @cancel="showDeleteModal = false"
    />
  </main>
</template>

<style scoped>
.page-content {
  flex: 1;
  padding: 28px 32px;
}
.workspace {
  min-height: calc(100vh - 132px);
}
.page-content { padding: 20px 28px; overflow: hidden; }
.workspace { height: calc(100vh - 40px); min-height: 0; display: flex; flex-direction: column; }
.sibling-tabs { flex-shrink: 0; margin-bottom: 16px; }

/* ---------- 同级子页标签栏 ---------- */
.sibling-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  padding: 4px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
}

.sibling-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.sibling-tab:hover {
  background: #f1f5f9;
  color: #334155;
}

.sibling-tab.active {
  background: #3b82f6;
  color: #fff;
}

.sibling-tab-icon {
  width: 18px;
  height: 18px;
}

/* ---------- 页面内容 ---------- */
.page-body {
  min-height: calc(100vh - 260px);
}

.content-card {
  padding: 32px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.page-body { flex: 1; min-height: 0; }
.content-card { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.table-area { flex: 1; min-height: 0; overflow: hidden; }
.pagination { position: relative; z-index: 2; min-height: 54px; flex-shrink: 0; background: #fff; }

.card-header {
  margin-bottom: 24px;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

/* ---------- 工具栏 ---------- */
.toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e2e8f0;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.field-input,
.field-select {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  min-width: 180px;
}

.field-input:focus,
.field-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.field-input::placeholder {
  color: #94a3b8;
}

/* ---------- 按钮 ---------- */
.btn {
  height: 38px;
  padding: 0 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, opacity 0.2s ease;
  white-space: nowrap;
}

.btn-outline {
  background: #f1f5f9;
  color: #475569;
}

.btn-outline:hover {
  background: #e2e8f0;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}

.btn-primary:hover {
  background: #2563eb;
}

.btn-success {
  background: #10b981;
  color: #fff;
}

.btn-success:hover {
  background: #059669;
}

/* ---------- 表格 ---------- */
.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 12px 16px;
  text-align: left;
  font-size: 14px;
  border-bottom: 1px solid #e2e8f0;
}

.data-table thead th {
  font-weight: 600;
  color: #475569;
  background: #f8fafc;
  white-space: nowrap;
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.data-table tbody td {
  color: #334155;
}

/* ---------- 操作按钮 ---------- */
.actions-cell {
  display: flex;
  gap: 8px;
}

.action-btn {
  height: 32px;
  padding: 0 14px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  white-space: nowrap;
}

.action-btn:hover {
  background: #f1f5f9;
  border-color: #94a3b8;
  color: #0f172a;
}

.action-danger:hover {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #dc2626;
}

/* ---------- 空状态 ---------- */
.empty-state {
  padding: 48px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

/* ---------- 分页 ---------- */
.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.pagination-info {
  margin-right: 12px;
  font-size: 13px;
  color: #94a3b8;
}

.page-btn {
  min-width: 34px;
  height: 34px;
  padding: 0 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  display: grid;
  place-items: center;
}

.page-btn:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #94a3b8;
}

.page-btn.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
}

.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

</style>
