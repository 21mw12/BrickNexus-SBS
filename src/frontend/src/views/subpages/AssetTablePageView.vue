<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { menuConfig, isMenuGroup } from '../../config/menu.ts'
import { fetchAssetPage, deleteAsset, exportAssets, type AssetInfo } from '../../api/asset.ts'
import CreateAssetModal from '../modals/asset/CreateAssetModal.vue'
import EditAssetModal from '../modals/asset/EditAssetModal.vue'
import ConfirmModal from '../modals/ConfirmModal.vue'
import ControlExecutionModal from '../modals/ControlExecutionModal.vue'

const router = useRouter()
const route = useRoute()

// ---------- 资产类型配置 ----------
const assetTypeOptions = [
  { label: '楼宇', value: 'building' },
  { label: '楼层', value: 'floor' },
  { label: '房间', value: 'room' },
  { label: '终端', value: 'terminal' },
  { label: '传感器', value: 'sensor' },
]

/**
 * 每种资产类型对应的附加查询字段
 */
const typeExtraFields: Record<string, { key: string; label: string; placeholder: string }[]> = {
  building: [
    { key: 'number', label: '楼宇编号', placeholder: '请输入楼宇编号' },
    { key: 'address', label: '地址', placeholder: '请输入地址' },
  ],
  floor: [
    { key: 'level', label: '楼层', placeholder: '请输入楼层' },
  ],
  room: [
    { key: 'number', label: '房间编号', placeholder: '请输入房间编号' },
    { key: 'room_purpose', label: '房间用途', placeholder: '请输入房间用途' },
    { key: 'max_current', label: '最大电流', placeholder: '请输入最大电流' },
    { key: 'manager_name', label: '负责人', placeholder: '请输入负责人' },
  ],
  terminal: [
    { key: 'number', label: '终端编号', placeholder: '请输入终端编号' },
    { key: 'model', label: '型号', placeholder: '请输入型号' },
    { key: 'location', label: '位置', placeholder: '请输入位置' },
    { key: 'iot_number', label: '物联编号', placeholder: '请输入物联编号' },
    { key: 'iot_activate_human', label: '激活人', placeholder: '请输入激活人' },
  ],
  sensor: [
    { key: 'model', label: '型号', placeholder: '请输入型号' },
    { key: 'sensor_type', label: '传感器类型', placeholder: '请输入传感器类型' },
  ],
}

const usageStatusOptions = [
  { label: '全部', value: undefined },
  { label: '使用中', value: true },
  { label: '空闲', value: false },
]

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

// ---------- 查询表单 ----------
const queryForm = reactive<Record<string, any>>({
  name: '',
  is_use: undefined as boolean | undefined,
  is_online: undefined as boolean | undefined,
  asset_type: '',
  // 类型特有字段，初始置空
  number: '',
  address: '',
  level: '',
  room_purpose: '',
  max_current: '',
  manager_name: '',
  model: '',
  location: '',
  iot_number: '',
  iot_activate_human: '',
  sensor_type: '',
})

// 当前资产类型对应的额外字段列表
const currentExtraFields = computed(() => {
  return typeExtraFields[queryForm.asset_type] || []
})

// 切换资产类型时，清除所有类型特有字段
watch(() => queryForm.asset_type, () => {
  queryForm.number = ''
  queryForm.address = ''
  queryForm.level = ''
  queryForm.room_purpose = ''
  queryForm.max_current = ''
  queryForm.manager_name = ''
  queryForm.model = ''
  queryForm.location = ''
  queryForm.iot_number = ''
  queryForm.iot_activate_human = ''
  queryForm.sensor_type = ''
  queryForm.is_online = undefined
})

// ---------- 资产列表 ----------
const assets = ref<AssetInfo[]>([])
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
    // 构建查询参数，过滤空值
    const query: Record<string, any> = {}
    if (queryForm.name) query.name = queryForm.name
    if (queryForm.is_use !== undefined) query.is_use = queryForm.is_use
    if (queryForm.is_online !== undefined && (queryForm.asset_type === 'terminal' || queryForm.asset_type === 'sensor')) query.is_online = queryForm.is_online
    if (queryForm.asset_type) query.asset_type = queryForm.asset_type

    // 附加类型特有字段
    for (const field of currentExtraFields.value) {
      const val = queryForm[field.key]
      if (val) query[field.key] = val
    }

    const result = await fetchAssetPage(page, pageSize.value, query)
    assets.value = result.data
    total.value = result.total
  } catch (e: any) {
    console.error('获取资产列表失败', e)
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
  queryForm.name = ''
  queryForm.is_use = undefined
  queryForm.is_online = undefined
  queryForm.asset_type = ''
  // asset_type 的 watch 会自动清除类型特有字段
}

// ---------- 资产类型显示名映射 ----------
const typeLabelMap: Record<string, string> = {
  building: '楼宇',
  floor: '楼层',
  room: '房间',
  terminal: '终端',
  sensor: '传感器',
}

function typeLabel(type: string): string {
  return typeLabelMap[type] || type
}

// ---------- 新增弹窗 ----------
const showCreateModal = ref(false)

function handleCreate() {
  showCreateModal.value = true
}

// ---------- 编辑弹窗 ----------
const showEditModal = ref(false)
const editAssetId = ref('')
const controlTarget = ref<AssetInfo | null>(null)

function handleEdit(row: AssetInfo) {
  editAssetId.value = row.id
  showEditModal.value = true
}

// ---------- 删除确认 ----------
const showDeleteModal = ref(false)
const deleteTarget = ref<AssetInfo | null>(null)
const deleteError = ref('')
const deleteLoading = ref(false)

function handleDelete(row: AssetInfo) {
  deleteTarget.value = row
  deleteError.value = ''
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await deleteAsset(deleteTarget.value.id)
    showDeleteModal.value = false
    search()
  } catch (e: any) {
    deleteError.value = e?.message || '删除失败'
  } finally {
    deleteLoading.value = false
  }
}

// ---------- 导出 ----------
async function handleExport() {
  try {
    await exportAssets()
  } catch (e: any) {
    console.error('导出失败', e)
  }
}

// ---------- 生命周期 ----------
onMounted(async () => { await nextTick(); adjustPageSize(); if (!loading.value) search(); tableResizeObserver = new ResizeObserver(schedulePageSize); if (tableArea.value) tableResizeObserver.observe(tableArea.value) })
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
            <div class="toolbar-row">
              <div class="toolbar-left">
                <div class="field">
                  <label class="field-label">资产名</label>
                  <input
                    v-model="queryForm.name"
                    type="text"
                    placeholder="请输入资产名"
                    class="field-input"
                    @keyup.enter="search()"
                  />
                </div>
                <div class="field">
                  <label class="field-label">使用状态</label>
                  <select v-model="queryForm.is_use" class="field-select">
                    <option
                      v-for="opt in usageStatusOptions"
                      :key="String(opt.value)"
                      :value="opt.value"
                    >{{ opt.label }}</option>
                  </select>
                </div>
                <div class="field">
                  <label class="field-label">资产类型</label>
                  <select v-model="queryForm.asset_type" class="field-select">
                    <option value="">全部</option>
                    <option
                      v-for="opt in assetTypeOptions"
                      :key="opt.value"
                      :value="opt.value"
                    >{{ opt.label }}</option>
                  </select>
                </div>
                <div class="field" v-if="queryForm.asset_type === 'terminal' || queryForm.asset_type === 'sensor'">
                  <label class="field-label">在线状态</label>
                  <select v-model="queryForm.is_online" class="field-select">
                    <option :value="undefined">全部</option>
                    <option :value="true">在线</option>
                    <option :value="false">离线</option>
                  </select>
                </div>
              </div>
              <div class="toolbar-right">
                <button class="btn btn-primary" @click="search()">查询</button>
                <button class="btn btn-success" @click="handleCreate">新增</button>
                <button class="btn btn-outline" @click="handleExport">导出</button>
              </div>
            </div>
            <!-- 类型特有字段（在选择资产类型后出现，独占第二行） -->
            <div class="toolbar-row" v-if="currentExtraFields.length > 0">
              <div class="toolbar-left">
                <div class="field" v-for="field in currentExtraFields" :key="field.key">
                  <label class="field-label">{{ field.label }}</label>
                  <input
                    v-model="queryForm[field.key]"
                    type="text"
                    :placeholder="field.placeholder"
                    class="field-input field-input-extra"
                    @keyup.enter="search()"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 表格滚动区 -->
          <div ref="tableArea" class="table-scroll">
            <table class="data-table" v-if="assets.length > 0">
            <thead>
              <tr>
                <th>资产名</th>
                <th>资产类型</th>
                <th>所含楼层数量</th>
                <th>所含房间数量</th>
                <th>所含终端数量</th>
                <th>所含传感器数量</th>
                <th>使用状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in assets" :key="row.id">
                <td>
                  {{ row.name }}
                  <span v-if="row.type === 'terminal' || row.type === 'sensor'" class="online-dot" :class="row.is_online ? 'dot-online' : 'dot-offline'" :title="row.is_online ? '在线' : '离线'"></span>
                </td>
                <td>{{ typeLabel(row.type) }}</td>
                <td>{{ row.floor_count }}</td>
                <td>{{ row.room_count }}</td>
                <td>{{ row.terminal_count }}</td>
                <td>{{ row.sensor_count }}</td>
                <td>
                  <span
                    class="status-tag"
                    :class="row.is_use ? 'status-in-use' : 'status-idle'"
                  >{{ row.is_use ? '使用中' : '空闲' }}</span>
                </td>
                <td class="actions-cell">
                  <button class="action-btn" @click="handleEdit(row)">编辑</button>
                  <button v-if="row.type === 'terminal' || row.type === 'sensor'" class="action-btn action-control" @click="controlTarget = row">控制</button>
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
          <div class="empty-state" v-else-if="assets.length === 0">
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

    <!-- 新增资产弹窗 -->
    <CreateAssetModal
      :visible="showCreateModal"
      @close="showCreateModal = false"
      @created="search()"
    />

    <!-- 编辑资产弹窗 -->
    <EditAssetModal
      :visible="showEditModal"
      :assetId="editAssetId"
      @close="showEditModal = false"
      @updated="search()"
    />
    <ControlExecutionModal
      :visible="!!controlTarget"
      :asset-id="controlTarget?.id ?? ''"
      :asset-type="controlTarget?.type === 'terminal' ? 'terminal' : 'sensor'"
      :asset-name="controlTarget?.name ?? ''"
      @close="controlTarget = null"
    />

    <!-- 删除确认弹窗 -->
    <ConfirmModal
      :visible="showDeleteModal"
      title="删除资产"
      :message="`确定要删除资产「${deleteTarget?.name ?? ''}」吗？此操作不可恢复。`"
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
  padding: 20px 28px;
  overflow: hidden;
}
.workspace {
  height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
}

/* ---------- 同级子页标签栏 ---------- */
.sibling-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  padding: 4px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
  flex-shrink: 0;
}

.sibling-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
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

/* ---------- 页面内容 ---------- */
.page-body {
  flex: 1;
  min-height: 0;
}

.content-card {
  padding: 20px 24px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
}
.content-card { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.table-scroll { flex: 1; min-height: 0; }

.card-header {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

/* ---------- 工具栏 ---------- */
.toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.toolbar-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
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
  gap: 4px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.field-input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  min-width: 200px;
}

.field-input-extra {
  min-width: 160px;
}

.field-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.field-input::placeholder {
  color: #94a3b8;
}

.field-select {
  height: 34px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  min-width: 140px;
}

.field-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

/* ---------- 按钮 ---------- */
.btn {
  height: 34px;
  padding: 0 18px;
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

/* ---------- 表格区 ---------- */
.table-scroll {
  /* 自动高度，不撑开空白 */
}

/* 自适应分页：数据严格截止在分页栏上方，不产生内部滚动条。 */
.table-scroll { overflow: hidden; }
.pagination { position: relative; z-index: 2; min-height: 54px; background: #fff; }

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

/* ---------- 状态标签 ---------- */
.status-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

/* 在线状态圆点 */
.online-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-left: 6px; vertical-align: middle; }
.dot-online { background: #22c55e; }
.dot-offline { background: #ef4444; }

.status-in-use {
  background: #dbeafe;
  color: #1e40af;
}

.status-idle {
  background: #fef3c7;
  color: #92400e;
}

/* ---------- 操作按钮 ---------- */
.actions-cell {
  display: flex;
  gap: 8px;
}

.action-btn {
  height: 28px;
  padding: 0 12px;
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

.action-control { color: #2563eb; border-color: #bfdbfe; background: #eff6ff; }
.action-control:hover { color: #1d4ed8; border-color: #93c5fd; background: #dbeafe; }

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
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
  flex-shrink: 0;
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
