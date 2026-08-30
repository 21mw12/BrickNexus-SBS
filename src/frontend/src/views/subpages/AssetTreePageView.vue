<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { menuConfig, isMenuGroup } from '../../config/menu.ts'
import {
  fetchAssetTree,
  sortAssetTreeForDisplay,
  fetchAssetDetail,
  deleteAsset,
  exportAssets,
  type AssetTreeNode,
  type AssetDetail,
} from '../../api/asset.ts'
import CreateAssetModal from '../modals/asset/CreateAssetModal.vue'
import EditAssetModal from '../modals/asset/EditAssetModal.vue'
import ConfirmModal from '../modals/ConfirmModal.vue'
import RequestMappingModal from '../modals/asset/RequestMappingModal.vue'
import ControlExecutionModal from '../modals/ControlExecutionModal.vue'

const router = useRouter()
const route = useRoute()

// ---------- 同级子页导航 ----------
const siblings = computed(() => {
  for (const entry of menuConfig) {
    if (isMenuGroup(entry)) {
      const match = entry.children.find(c => c.route === route.path)
      if (match) return entry.children
    }
  }
  return []
})

const currentName = computed(() => {
  const sib = siblings.value.find(s => s.route === route.path)
  return sib?.name || ''
})

function goTo(path: string) { router.push(path) }

// ---------- 列标题 ----------
const columnHeaders = ['楼宇', '楼层', '房间', '终端', '传感器']
const columnIcons = [
  '/icon/asset_building_black.png',
  '/icon/asset_floor_black.png',
  '/icon/asset_room_black.png',
  '/icon/asset_terminal_black.png',
  '/icon/asset_sensor_black.png',
]

// ---------- 资产列数据 ----------
const columns = ref<AssetTreeNode[][]>([[], [], [], [], []])
const selectedIndex = ref<number[]>([-1, -1, -1, -1, -1])
const treeLoading = ref(false)

// ---------- 右侧详情 ----------
const detailAsset = ref<AssetDetail | null>(null)
const detailLoading = ref(false)

// ---------- 类型显示名 ----------
const typeLabelMap: Record<string, string> = {
  building: '楼宇', floor: '楼层', room: '房间', terminal: '终端', sensor: '传感器',
}

// ---------- 加载资产树 ----------
async function loadTree() {
  treeLoading.value = true
  try {
    const tree = sortAssetTreeForDisplay(await fetchAssetTree())
    columns.value = [[], [], [], [], []]
    selectedIndex.value = [-1, -1, -1, -1, -1]
    columns.value[0] = tree
    // 默认展开第一个
    if (tree.length > 0) {
      autoExpand(0, 0)
    }
  } catch (e: any) {
    console.error('加载资产树失败', e)
  } finally {
    treeLoading.value = false
  }
}

/** 自动展开：选中 column[i] 第 idx 项，并级联展开子节点 */
function autoExpand(col: number, idx: number) {
  // 清除后续列
  for (let c = col; c < 5; c++) {
    selectedIndex.value[c] = -1
    if (c > col) columns.value[c] = []
  }
  selectedIndex.value[col] = idx
  const colData = columns.value[col]
  if (!colData) return
  const node = colData[idx]
  if (node && node.sub_assets && node.sub_assets.length > 0 && col < 4) {
    columns.value[col + 1] = node.sub_assets
    autoExpand(col + 1, 0)
  }
}

/** 点击资产主体 → 展开子级 */
function handleItemClick(col: number, idx: number) {
  autoExpand(col, idx)
}

/** 点击详情图标 → 查询详细信息 */
async function handleDetailClick(assetId: string) {
  detailLoading.value = true
  try {
    detailAsset.value = await fetchAssetDetail(assetId)
  } catch (e: any) {
    console.error('获取详情失败', e)
  } finally {
    detailLoading.value = false
  }
}

// ---------- 新增弹窗 ----------
const showCreateModal = ref(false)

// ---------- 编辑弹窗 ----------
const showEditModal = ref(false)
const editAssetId = ref('')

function handleEdit() {
  if (!detailAsset.value) return
  editAssetId.value = detailAsset.value.asset_id
  showEditModal.value = true
}

// ---------- 请求映射 ----------
const showMappingModal = ref(false)
const showControlModal = ref(false)

// ---------- 删除确认 ----------
const showDeleteModal = ref(false)
const deleteError = ref('')
const deleteLoading = ref(false)

function handleDeleteClick() {
  if (!detailAsset.value) return
  deleteError.value = ''
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!detailAsset.value) return
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await deleteAsset(detailAsset.value.asset_id)
    showDeleteModal.value = false
    detailAsset.value = null
    await loadTree()
  } catch (e: any) {
    deleteError.value = e?.message || '删除失败'
  } finally {
    deleteLoading.value = false
  }
}

// ---------- 导出 ----------
async function handleExport() {
  try { await exportAssets() } catch (e: any) { console.error('导出失败', e) }
}

onMounted(() => { loadTree() })
</script>

<template>
  <main class="page-content">
    <section class="workspace">
      <!-- 同级子页导航 -->
      <nav class="sibling-tabs" v-if="siblings.length > 1">
        <button
          v-for="sib in siblings" :key="sib.route"
          class="sibling-tab" :class="{ active: route.path === sib.route }"
          @click="goTo(sib.route)"
        ><span>{{ sib.name }}</span></button>
      </nav>

      <div class="tree-layout">
        <!-- ========== 左侧：资产树 ========== -->
        <div class="tree-panel">
          <!-- 操作栏 -->
          <div class="tree-toolbar">
            <div class="tree-title-row">
              <h2 class="tree-title">{{ currentName }}</h2>
              <span class="tree-hint">
                点击资产名展开下级
                <span class="hint-sep">|</span>
                点击 <img src="/icon/detailInfo_black.png" class="hint-icon" /> 查看详情
              </span>
            </div>
            <div class="tree-actions">
              <button class="btn btn-success btn-sm" @click="showCreateModal = true">添加资产</button>
              <button class="btn btn-outline btn-sm" @click="handleExport">导出资产</button>
            </div>
          </div>

          <!-- 列视图 -->
          <div class="column-view" v-if="!treeLoading">
            <div class="tree-column" v-for="(col, colIdx) in columns" :key="colIdx">
              <div class="column-header">
                <img :src="columnIcons[colIdx]" class="column-header-icon" alt="" />
                <span>{{ columnHeaders[colIdx] }}</span>
              </div>
              <div class="column-body">
                <div
                  v-for="(item, itemIdx) in col"
                  :key="item.asset_id"
                  class="tree-item"
                  :class="{
                    selected: selectedIndex[colIdx] === itemIdx,
                    'tree-online': item.is_online === true,
                    'tree-offline': item.is_online === false,
                  }"
                >
                  <span class="tree-item-name" @click="handleItemClick(colIdx, itemIdx)">{{ item.name }}</span>
                  <img
                    class="tree-item-detail"
                    :class="{ active: detailAsset?.asset_id === item.asset_id }"
                    src="/icon/detailInfo_black.png"
                    @click.stop="handleDetailClick(item.asset_id)"
                    title="查看详情"
                  />
                </div>
                <div class="column-empty" v-if="col.length === 0 && colIdx === 0">暂无资产</div>
              </div>
            </div>
          </div>
          <div class="empty-state" v-else><p>加载中...</p></div>
        </div>

        <!-- ========== 右侧：资产详情 ========== -->
        <div class="detail-panel">
          <template v-if="detailAsset">
            <h3 class="detail-name">{{ detailAsset.name }}</h3>
            <div class="detail-props">
              <div class="detail-row"><span class="detail-label">资产类型</span><span class="detail-value">{{ typeLabelMap[detailAsset.asset_type] || detailAsset.asset_type }}</span></div>
              <template v-if="detailAsset.number">
                <div class="detail-row"><span class="detail-label">编号</span><span class="detail-value">{{ detailAsset.number }}</span></div>
              </template>
              <template v-if="detailAsset.address">
                <div class="detail-row"><span class="detail-label">地址</span><span class="detail-value">{{ detailAsset.address }}</span></div>
              </template>
              <template v-if="(detailAsset as any).level">
                <div class="detail-row"><span class="detail-label">楼层</span><span class="detail-value">{{ (detailAsset as any).level }}</span></div>
              </template>
              <template v-if="(detailAsset as any).room_purpose">
                <div class="detail-row"><span class="detail-label">房间用途</span><span class="detail-value">{{ (detailAsset as any).room_purpose }}</span></div>
              </template>
              <template v-if="(detailAsset as any).max_current">
                <div class="detail-row"><span class="detail-label">最大电流</span><span class="detail-value">{{ (detailAsset as any).max_current }}</span></div>
              </template>
              <template v-if="(detailAsset as any).manager_name">
                <div class="detail-row"><span class="detail-label">负责人</span><span class="detail-value">{{ (detailAsset as any).manager_name }}</span></div>
              </template>
              <template v-if="(detailAsset as any).model">
                <div class="detail-row"><span class="detail-label">型号</span><span class="detail-value">{{ (detailAsset as any).model }}</span></div>
              </template>
              <template v-if="(detailAsset as any).location">
                <div class="detail-row"><span class="detail-label">位置</span><span class="detail-value">{{ (detailAsset as any).location }}</span></div>
              </template>
              <template v-if="(detailAsset as any).iot_number">
                <div class="detail-row"><span class="detail-label">物联编号</span><span class="detail-value">{{ (detailAsset as any).iot_number }}</span></div>
              </template>
              <template v-if="(detailAsset as any).iot_activate_human">
                <div class="detail-row"><span class="detail-label">激活人</span><span class="detail-value">{{ (detailAsset as any).iot_activate_human }}</span></div>
              </template>
              <template v-if="detailAsset.asset_type === 'sensor'">
                <div class="detail-row" v-if="(detailAsset as any).sensor_type"><span class="detail-label">传感器类型</span><span class="detail-value">{{ (detailAsset as any).sensor_type }}</span></div>
                <div class="detail-row" v-if="(detailAsset as any).model_name"><span class="detail-label">传感器型号</span><span class="detail-value">{{ (detailAsset as any).model_name }}</span></div>
                <div class="detail-points" v-if="(detailAsset as any).points?.length">
                  <span class="detail-label">测点信息</span>
                  <div class="point-tags">
                    <span class="point-tag" v-for="(p, i) in (detailAsset as any).points" :key="i">
                      {{ p.point_name }}<span class="point-unit" v-if="p.point_unit"> ({{ p.point_unit }})</span><span class="point-description" v-if="p.point_description"> · {{ p.point_description }}</span>
                    </span>
                  </div>
                </div>
              </template>
            </div>
            <!-- 资产数量统计 -->
            <div class="detail-counts">
              <div class="detail-row"><span class="detail-label">所含楼层</span><span class="detail-value">{{ detailAsset.floor_count }}</span></div>
              <div class="detail-row"><span class="detail-label">所含房间</span><span class="detail-value">{{ detailAsset.room_count }}</span></div>
              <div class="detail-row"><span class="detail-label">所含终端</span><span class="detail-value">{{ detailAsset.terminal_count }}</span></div>
              <div class="detail-row"><span class="detail-label">所含传感器</span><span class="detail-value">{{ detailAsset.sensor_count }}</span></div>
            </div>
            <!-- 状态区（置底） -->
            <div class="detail-status">
              <div class="detail-row">
                <span class="detail-label">使用状态</span>
                <span class="detail-value" :class="detailAsset.is_use ? 'text-in-use' : 'text-idle'">{{ detailAsset.is_use ? '使用中' : '空闲' }}</span>
              </div>
            </div>
            <div class="detail-actions">
              <button class="btn btn-outline btn-sm" @click="handleEdit">编辑</button>
              <button v-if="detailAsset.asset_type === 'terminal'" class="btn btn-outline btn-sm" @click="showMappingModal = true">请求映射</button>
              <button v-if="detailAsset.asset_type === 'terminal' || detailAsset.asset_type === 'sensor'" class="btn btn-control btn-sm" @click="showControlModal = true">控制</button>
              <button class="btn btn-danger btn-sm" @click="handleDeleteClick">删除</button>
            </div>
          </template>
          <div class="detail-empty" v-else-if="!detailLoading">
            <p>点击资产旁的 <img src="/icon/detailInfo_black.png" class="inline-icon" /> 图标查看详细信息</p>
          </div>
          <div class="detail-empty" v-else>
            <p>加载中...</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 弹窗 -->
    <CreateAssetModal :visible="showCreateModal" @close="showCreateModal = false" @created="loadTree()" />
    <EditAssetModal :visible="showEditModal" :assetId="editAssetId" @close="showEditModal = false" @updated="loadTree(); detailAsset = null" />
    <RequestMappingModal
      :visible="showMappingModal"
      :terminalId="detailAsset?.asset_id ?? ''"
      :terminalName="detailAsset?.name ?? ''"
      @close="showMappingModal = false"
    />
    <ControlExecutionModal
      :visible="showControlModal"
      :asset-id="detailAsset?.asset_id ?? ''"
      :asset-type="detailAsset?.asset_type === 'terminal' ? 'terminal' : 'sensor'"
      :asset-name="detailAsset?.name ?? ''"
      @close="showControlModal = false"
    />
    <ConfirmModal
      :visible="showDeleteModal"
      title="删除资产"
      :message="`确定要删除资产「${detailAsset?.name ?? ''}」吗？此操作不可恢复。`"
      confirmText="删除" :danger="true"
      :error="deleteError"
      :loading="deleteLoading"
      @confirm="confirmDelete"
      @cancel="showDeleteModal = false"
    />
  </main>
</template>

<style scoped>
.page-content { flex: 1; padding: 28px 32px; overflow: hidden; }
.workspace { height: calc(100vh - 132px); display: flex; flex-direction: column; }

/* ---------- 同级子页标签栏 ---------- */
.sibling-tabs {
  display: flex; gap: 4px; margin-bottom: 24px; padding: 4px;
  border-radius: 14px; background: #fff;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05); flex-shrink: 0;
}
.sibling-tab {
  display: flex; align-items: center; gap: 8px; padding: 10px 20px;
  border: none; border-radius: 10px; background: transparent;
  color: #64748b; font-size: 14px; font-weight: 500; cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}
.sibling-tab:hover { background: #f1f5f9; color: #334155; }
.sibling-tab.active { background: #3b82f6; color: #fff; }

/* ---------- 左右布局 ---------- */
.tree-layout {
  flex: 1; display: flex; gap: 20px; min-height: 0; overflow: hidden;
}

/* ---------- 左侧资产树面板 ---------- */
.tree-panel {
  flex: 1; min-width: 0; background: #fff; border-radius: 16px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
  display: flex; flex-direction: column; overflow: hidden;
}
.tree-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #e2e8f0; flex-shrink: 0;
}
.tree-title-row { display: flex; align-items: baseline; gap: 14px; }
.tree-title { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; white-space: nowrap; }
.tree-actions { display: flex; gap: 8px; }

/* ---------- 操作提示 ---------- */
.tree-hint {
  font-size: 12px; color: #94a3b8; white-space: nowrap;
}
.hint-sep { margin: 0 4px; color: #cbd5e1; }
.hint-icon { width: 14px; height: 14px; vertical-align: middle; opacity: 0.5; }

/* ---------- 列视图 ---------- */
.column-view {
  flex: 1; display: flex; gap: 0; overflow-x: auto; overflow-y: hidden; min-height: 0;
}
.tree-column {
  flex: 1; min-width: 180px; max-width: 260px;
  border-right: 1px solid #e2e8f0; display: flex; flex-direction: column;
}
.tree-column:last-child { border-right: none; }
.column-header {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 10px 16px; font-size: 13px; font-weight: 600; color: #64748b;
  background: #f8fafc; border-bottom: 1px solid #e2e8f0; flex-shrink: 0;
}
.column-header-icon {
  width: 18px; height: 18px; opacity: 0.5; flex-shrink: 0;
}
.column-body { flex: 1; overflow-y: auto; padding: 4px 0; }
.tree-item {
  display: flex; align-items: center; padding: 8px 12px 8px 16px;
  cursor: pointer; transition: background 0.15s ease;
  border-left: 3px solid transparent;
}
.tree-item:hover { background: #f1f5f9; }
.tree-item.selected { background: #eff6ff; border-left-color: #3b82f6; }
.tree-online { background: #f0fdf4 !important; }
.tree-online:hover { background: #dcfce7 !important; }
.tree-online.selected { background: #bbf7d0 !important; border-left-color: #16a34a; }
.tree-offline { background: #fef2f2 !important; }
.tree-offline:hover { background: #fee2e2 !important; }
.tree-offline.selected { background: #fecaca !important; border-left-color: #dc2626; }
.tree-item-name {
  flex: 1; font-size: 14px; color: #334155; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.tree-item-detail {
  flex-shrink: 0; width: 18px; height: 18px; padding: 3px;
  border-radius: 4px; opacity: 0.4; cursor: pointer;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.tree-item-detail:hover { opacity: 0.7; background: #e2e8f0; }
.tree-item-detail.active { opacity: 1; background: #dbeafe; }
.column-empty {
  padding: 24px 16px; text-align: center; font-size: 13px; color: #94a3b8;
}

/* ---------- 右侧详情面板 ---------- */
.detail-panel {
  width: 300px; flex-shrink: 0; background: #fff; border-radius: 16px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
  display: flex; flex-direction: column; overflow-y: auto; padding: 28px 24px;
}
.detail-name {
  margin: 0 0 24px; font-size: 20px; font-weight: 700; color: #0f172a; text-align: center;
}
.detail-props { display: flex; flex-direction: column; gap: 0; }
.detail-points {
  display: flex; flex-direction: column; gap: 6px; padding: 8px 0;
}
.point-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.point-tag {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 3px 10px; border-radius: 6px; font-size: 12px;
  background: #f8fafc; border: 1px solid #e2e8f0; color: #334155;
}
.point-tag .point-unit { font-size: 11px; color: #94a3b8; }
.point-tag .point-description { color: #64748b; font-size: 11px; }

.detail-counts {
  margin-top: 12px; padding-top: 12px; border-top: 1px solid #e2e8f0;
}
.detail-status {
  margin-top: 12px; padding-top: 12px; border-top: 1px solid #e2e8f0;
}
.detail-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 1px solid #f1f5f9;
}
.detail-label { font-size: 13px; color: #94a3b8; }
.detail-value { font-size: 14px; color: #334155; font-weight: 500; }
.text-online { color: #065f46 !important; }
.text-offline { color: #991b1b !important; }
.text-in-use { color: #1e40af !important; }
.text-idle { color: #92400e !important; }
.inline-icon { width: 16px; height: 16px; vertical-align: middle; opacity: 0.6; }
.detail-actions {
  display: flex; gap: 8px; margin-top: 20px; padding-top: 16px;
  border-top: 1px solid #e2e8f0; justify-content: center;
}
.detail-empty {
  flex: 1; display: grid; place-items: center;
  font-size: 14px; color: #94a3b8; text-align: center; padding: 24px;
}

/* ---------- 按钮 ---------- */
.btn {
  height: 38px; padding: 0 20px; border: none; border-radius: 8px;
  font-size: 14px; font-weight: 600; cursor: pointer;
  transition: background 0.2s ease; white-space: nowrap;
}
.btn-sm { height: 32px; padding: 0 14px; font-size: 13px; }
.btn-outline { background: #f1f5f9; color: #475569; }
.btn-outline:hover { background: #e2e8f0; }
.btn-control { color: #2563eb; background: #eff6ff; border: 1px solid #bfdbfe; }
.btn-control:hover { background: #dbeafe; }
.btn-success { background: #10b981; color: #fff; }
.btn-success:hover { background: #059669; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-danger:hover { background: #b91c1c; }

/* ---------- 空状态 ---------- */
.empty-state {
  flex: 1; display: grid; place-items: center; color: #94a3b8; font-size: 14px;
}
</style>
