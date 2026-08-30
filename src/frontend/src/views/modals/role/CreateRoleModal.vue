<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { createRole, fetchPageTree, type PageTreeNode } from '../../../api/user'
import { fetchAssetTree, type AssetTreeNode } from '../../../api/asset.ts'
import type { AssetTypePermission } from '../../../api/user'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; created: [] }>()

const loading = ref(false)
const error = ref('')
const form = reactive({ name: '', describe: '' })

// ---------- 折叠控制 ----------
const pagePermExpanded = ref(false)
const assetPermExpanded = ref(false)
const assetTreeExpanded = ref<Set<string>>(new Set())
function toggleAssetExpand(id: string) {
  const next = new Set(assetTreeExpanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  assetTreeExpanded.value = next
}

// ---------- 页面权限 ----------
const pageTree = ref<PageTreeNode[]>([])
const selectedPageIds = ref<Set<string>>(new Set())
const pageCollapsed = ref<Set<string>>(new Set())

function collectDescendantPageIds(node: PageTreeNode): string[] {
  const ids = [node.page_id]
  if (node.sub_pages) for (const c of node.sub_pages) ids.push(...collectDescendantPageIds(c))
  return ids
}
/** 判断节点自身是否被选中（与子节点状态无关） */
function isPageNodeChecked(node: PageTreeNode): boolean {
  return selectedPageIds.value.has(node.page_id)
}
/**
 * 切换节点：以节点自身状态为准决定勾选还是取消，
 * 同时级联操作所有子孙节点（勾选父节点 → 勾选所有子节点，反之亦然）
 */
function togglePageNode(node: PageTreeNode) {
  const ids = collectDescendantPageIds(node)
  const thisChecked = selectedPageIds.value.has(node.page_id)
  const next = new Set(selectedPageIds.value)
  if (thisChecked) {
    ids.forEach(id => next.delete(id))
  } else {
    ids.forEach(id => next.add(id))
  }
  selectedPageIds.value = next
}
function isPageCollapsed(node: PageTreeNode) { return pageCollapsed.value.has(node.page_id) }
function togglePageCollapse(node: PageTreeNode) {
  const next = new Set(pageCollapsed.value)
  next.has(node.page_id) ? next.delete(node.page_id) : next.add(node.page_id)
  pageCollapsed.value = next
}

// ---------- 资产类型权限 ----------
const assetTypes = ['building', 'floor', 'room', 'terminal', 'sensor'] as const
type AssetTypeKey = (typeof assetTypes)[number]
const assetTypeLabels: Record<string, string> = {
  building: '楼宇', floor: '楼层', room: '房间', terminal: '终端', sensor: '传感器',
}
const assetTypePerms = reactive<Record<AssetTypeKey, { C: boolean }>>({
  building: { C: false },
  floor: { C: false },
  room: { C: false },
  terminal: { C: false },
  sensor: { C: false },
})

// ---------- 资产树权限 ----------
const assetTree = ref<AssetTreeNode[]>([])
const assetIdPerms = reactive<Record<string, { U: boolean; R: boolean; D: boolean; O: boolean }>>({})

function ensureAssetPerm(assetId: string) {
  if (!assetIdPerms[assetId]) {
    assetIdPerms[assetId] = { U: false, R: false, D: false, O: false }
  }
  return assetIdPerms[assetId]
}

// ---------- 权限自动校准 ----------
const parentMap = ref<Record<string, string>>({})
const childrenMap = ref<Record<string, string[]>>({})

function buildMaps(nodes: AssetTreeNode[], parentId?: string) {
  for (const node of nodes) {
    if (parentId) {
      parentMap.value[node.asset_id] = parentId
      if (!childrenMap.value[parentId]) childrenMap.value[parentId] = []
      childrenMap.value[parentId].push(node.asset_id)
    }
    if (node.sub_assets) buildMaps(node.sub_assets, node.asset_id)
  }
}

/** 查看权限向上传递：勾选 R → 祖先全部勾选 R */
function propagateRUpward(assetId: string) {
  let current = parentMap.value[assetId]
  while (current) {
    ensureAssetPerm(current).R = true
    current = parentMap.value[current]
  }
}

/** 查看权限向下传递：取消 R → 后代全部取消 R（及 U/O） */
function propagateRDownward(assetId: string) {
  const children = childrenMap.value[assetId]
  if (!children) return
  for (const childId of children) {
    const p = ensureAssetPerm(childId)
    p.R = false; p.U = false; p.D = false; p.O = false
    propagateRDownward(childId)
  }
}

function onAssetPermChange(assetId: string, key: 'R' | 'U' | 'D' | 'O') {
  const perm = ensureAssetPerm(assetId)
  if (key === 'R') {
    // 取消 R → 清掉该节点的所有权限，并向下传递
    if (!perm.R) { perm.U = false; perm.D = false; perm.O = false; propagateRDownward(assetId) }
    // 勾选 R → 向上传递
    else { propagateRUpward(assetId) }
  } else {
    // 勾选 U / D / O → 自动勾 R，并向上传递
    if (perm[key]) { perm.R = true; propagateRUpward(assetId) }
    // 取消 U / D / O → 仅该节点取消，不做额外处理
  }
}

// ---------- 打开时加载 ----------
watch(() => props.visible, async (v) => {
  if (v) {
    form.name = ''; form.describe = ''
    selectedPageIds.value = new Set()
    pageCollapsed.value = new Set()
    pagePermExpanded.value = false
    assetPermExpanded.value = false
    assetTreeExpanded.value = new Set()
    for (const t of assetTypes) assetTypePerms[t] = { C: false }
    Object.keys(assetIdPerms).forEach(k => delete assetIdPerms[k])
    error.value = ''
    try {
      const [pages, assets] = await Promise.all([fetchPageTree(), fetchAssetTree()])
      pageTree.value = pages
      assetTree.value = assets
      parentMap.value = {}
      childrenMap.value = {}
      buildMaps(assets)
    } catch (e: any) {
      error.value = e?.message || '加载数据失败'
    }
  }
})

// ---------- 提交 ----------
async function confirm() {
  error.value = ''
  loading.value = true
  try {
    const part_asset_type: AssetTypePermission[] = []
    for (const t of assetTypes) {
      const p = assetTypePerms[t]
      if (p.C) part_asset_type.push({ type: t, permission: 'C' })
    }
    const part_asset_id: { asset_id: string; permission: string }[] = []
    for (const [assetId, p] of Object.entries(assetIdPerms)) {
      let perm = ''
      if (p.U) perm += 'U'
      if (p.R) perm += 'R'
      if (p.D) perm += 'D'
      if (p.O) perm += 'O'
      if (perm) part_asset_id.push({ asset_id: assetId, permission: perm })
    }

    await createRole({
      name: form.name,
      describe: form.describe || undefined,
      page_ids: selectedPageIds.value.size > 0 ? [...selectedPageIds.value] : undefined,
      asset_permission: (part_asset_type.length || part_asset_id.length)
        ? { part_asset_type: part_asset_type.length ? part_asset_type : undefined, part_asset_id: part_asset_id.length ? part_asset_id : undefined }
        : undefined,
    })
    emit('created')
    emit('close')
  } catch (e: any) {
    error.value = e?.message || '创建失败'
  } finally {
    loading.value = false
  }
}

// ---------- 递归渲染资产树 ----------
interface AssetPermRow {
  node: AssetTreeNode
  hasChildren: boolean
  expanded: boolean
  perm: { U: boolean; R: boolean; D: boolean; O: boolean }
  depth: number
  isOperable: boolean
}
function renderAssetNodes(nodes: AssetTreeNode[], depth: number): AssetPermRow[] {
  return nodes.map(node => {
    const assetType = node.asset_type || node.type
    // 优先使用资产类型；在线状态和 depth 用于兼容旧版资产树响应
    const isOperable = assetType
      ? assetType === 'terminal' || assetType === 'sensor'
      : node.is_online !== undefined || depth >= 3
    const hasChildren = (node.sub_assets?.length ?? 0) > 0
    const expanded = assetTreeExpanded.value.has(node.asset_id)
    const perm = ensureAssetPerm(node.asset_id)
    return [
      { node, hasChildren, expanded, perm, depth, isOperable },
      ...(hasChildren && expanded ? renderAssetNodes(node.sub_assets!, depth + 1) : []),
    ]
  }).flat()
}
</script>

<template>
  <div class="modal-overlay" v-if="visible" @click.self="emit('close')">
    <div class="modal-card form-modal">
      <div class="modal-header"><h3>新增角色</h3></div>
      <div class="modal-body form-grid">
        <div class="field">
          <label class="field-label">角色名 <span class="required">*</span></label>
          <input v-model="form.name" type="text" placeholder="请输入角色名" class="field-input" />
        </div>
        <div class="field">
          <label class="field-label">角色描述</label>
          <input v-model="form.describe" type="text" placeholder="请输入角色描述" class="field-input" />
        </div>

        <!-- 页面权限（折叠） -->
        <div class="field form-span-2">
          <div class="section-header" @click="pagePermExpanded = !pagePermExpanded">
            <span class="section-toggle">{{ pagePermExpanded ? '▾' : '▸' }}</span>
            <label class="field-label" style="cursor:pointer">页面权限</label>
          </div>
          <div class="tree-panel" v-if="pagePermExpanded">
            <template v-for="node in pageTree" :key="node.page_id">
              <div class="tree-node tree-parent">
                <span class="tree-toggle" @click="togglePageCollapse(node)">{{ isPageCollapsed(node) ? '▸' : '▾' }}</span>
                <label class="tree-label"><input type="checkbox" :checked="isPageNodeChecked(node)" @change="togglePageNode(node)" />{{ node.name }}</label>
              </div>
              <template v-if="node.sub_pages && !isPageCollapsed(node)">
                <div v-for="child in node.sub_pages" :key="child.page_id" class="tree-node tree-child">
                  <span class="tree-toggle tree-toggle-empty"></span>
                  <label class="tree-label"><input type="checkbox" :checked="selectedPageIds.has(child.page_id)" @change="togglePageNode(child)" />{{ child.name }}</label>
                </div>
              </template>
            </template>
            <p class="tree-hint" v-if="pageTree.length === 0">加载中...</p>
          </div>
        </div>

        <!-- 资产权限（折叠） -->
        <div class="field form-span-2">
          <div class="section-header" @click="assetPermExpanded = !assetPermExpanded">
            <span class="section-toggle">{{ assetPermExpanded ? '▾' : '▸' }}</span>
            <label class="field-label" style="cursor:pointer">资产权限</label>
          </div>
          <div v-if="assetPermExpanded">
            <!-- 资产类型权限 -->
            <div class="perm-subtitle">资产类型权限（创建）</div>
            <div class="perm-grid perm-grid-type">
              <div class="perm-grid-header perm-grid-header-type">
                <span class="perm-grid-label"></span>
                <span class="perm-grid-col">创建</span>
              </div>
              <div class="perm-grid-row perm-grid-row-type" v-for="t in assetTypes" :key="t">
                <span class="perm-grid-label">{{ assetTypeLabels[t] }}</span>
                <label class="perm-check"><input type="checkbox" v-model="assetTypePerms[t].C" /></label>
              </div>
            </div>

            <!-- 资产树权限 -->
            <div class="perm-subtitle" style="margin-top:12px">资产实例权限（查看 / 编辑 / 删除 / 操作）</div>
            <div class="perm-grid perm-grid-asset">
              <div class="perm-grid-header perm-grid-header-asset">
                <span class="perm-grid-label">资产名</span>
                <span class="perm-grid-col">查看</span>
                <span class="perm-grid-col">编辑</span>
                <span class="perm-grid-col">删除</span>
                <span class="perm-grid-col">操作</span>
              </div>
              <template v-for="row in renderAssetNodes(assetTree, 0)" :key="row.node.asset_id">
                <div class="perm-grid-row perm-grid-row-asset" :class="{ 'row-parent': row.depth === 0 }">
                  <span class="perm-grid-label" :style="{ paddingLeft: 8 + row.depth * 18 + 'px' }">
                    <span v-if="row.hasChildren" class="tree-toggle" @click="toggleAssetExpand(row.node.asset_id)">{{ row.expanded ? '▾' : '▸' }}</span>
                    <span v-else class="tree-toggle tree-toggle-empty"></span>
                    {{ row.node.name }}
                  </span>
                  <label class="perm-check"><input type="checkbox" v-model="row.perm.R" @change="onAssetPermChange(row.node.asset_id, 'R')" /></label>
                  <label class="perm-check"><input type="checkbox" v-model="row.perm.U" @change="onAssetPermChange(row.node.asset_id, 'U')" /></label>
                  <label class="perm-check"><input type="checkbox" v-model="row.perm.D" @change="onAssetPermChange(row.node.asset_id, 'D')" /></label>
                  <label class="perm-check" v-if="row.isOperable"><input type="checkbox" v-model="row.perm.O" @change="onAssetPermChange(row.node.asset_id, 'O')" /></label>
                  <span class="perm-grid-col" v-else></span>
                </div>
              </template>
              <p class="tree-hint" v-if="assetTree.length === 0" style="grid-column:1/-1">加载中...</p>
            </div>
          </div>
        </div>

        <div class="modal-error form-span-2" v-if="error">{{ error }}</div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" @click="emit('close')" :disabled="loading">取消</button>
        <button class="btn btn-primary" @click="confirm" :disabled="loading">{{ loading ? '创建中...' : '确认' }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-card { width: 620px; max-width: 90vw; max-height: 85vh; background: #fff; border-radius: 16px; box-shadow: 0 20px 60px rgba(15,23,42,0.18); overflow: hidden; display: flex; flex-direction: column; }
.modal-header { padding: 20px 24px 0; flex-shrink: 0; }
.modal-header h3 { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; }
.modal-body { padding: 20px 24px; display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
.modal-error { padding: 10px 14px; border-radius: 8px; background: #fef2f2; color: #dc2626; font-size: 13px; }
.modal-footer { padding: 0 24px 20px; display: flex; justify-content: flex-end; gap: 8px; flex-shrink: 0; }

.form-modal { width: 760px; max-height: 90vh; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 16px; }
.form-grid .field { min-width: 0; }
.form-span-2 { grid-column: span 2; }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
  .form-span-2 { grid-column: span 1; }
}

/* 折叠标题 */
.section-header { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
.section-toggle { font-size: 12px; color: #64748b; width: 16px; }
.perm-subtitle { font-size: 12px; color: #94a3b8; margin-bottom: 6px; }

/* 权限网格 */
.perm-grid { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.perm-grid-header, .perm-grid-row { display: grid; align-items: center; padding: 6px 12px; font-size: 13px; }
.perm-grid-header { background: #f8fafc; color: #64748b; font-weight: 600; }
.perm-grid-row { border-top: 1px solid #f1f5f9; }
.perm-grid-label { color: #334155; display: flex; align-items: center; gap: 4px; }
.perm-grid-col { text-align: center; }

/* 资产类型权限网格 */
.perm-grid-type { }
.perm-grid-header-type { grid-template-columns: 1fr 60px; }
.perm-grid-row-type { grid-template-columns: 1fr 60px; }

/* 资产树权限网格 */
.perm-grid-asset { max-height: 260px; overflow-y: auto; }
.perm-grid-header-asset { grid-template-columns: 1fr 60px 60px 60px 60px; position: sticky; top: 0; z-index: 1; }
.perm-grid-row-asset { grid-template-columns: 1fr 60px 60px 60px 60px; }
.perm-grid-row-asset.row-parent .perm-grid-label { font-weight: 600; }
.perm-check { display: flex; align-items: center; justify-content: center; gap: 3px; cursor: pointer; }
.perm-check input[type="checkbox"] { width: 15px; height: 15px; accent-color: #3b82f6; cursor: pointer; }

/* 页面树 */
.tree-panel { border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px 0; max-height: 220px; overflow-y: auto; }
.tree-node { display: flex; align-items: center; padding: 3px 8px; min-height: 30px; gap: 2px; }
.tree-parent { font-weight: 600; }
.tree-toggle { width: 18px; height: 18px; display: grid; place-items: center; cursor: pointer; font-size: 11px; color: #94a3b8; flex-shrink: 0; }
.tree-toggle:hover { color: #475569; }
.tree-toggle-empty { cursor: default; }
.tree-label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 14px; color: #334155; }
.tree-label input[type="checkbox"] { width: 16px; height: 16px; accent-color: #3b82f6; cursor: pointer; }
.tree-hint { padding: 12px; text-align: center; color: #94a3b8; font-size: 13px; margin: 0; }

/* 表单 */
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: #475569; }
.required { color: #dc2626; }
.field-input { height: 38px; padding: 0 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; color: #0f172a; background: #fff; outline: none; transition: border-color .2s ease, box-shadow .2s ease; }
.field-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.12); }
.field-input::placeholder { color: #94a3b8; }

/* 按钮 */
.btn { height: 38px; padding: 0 20px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background .2s ease; white-space: nowrap; }
.btn-outline { background: #f1f5f9; color: #475569; }
.btn-outline:hover { background: #e2e8f0; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
</style>
