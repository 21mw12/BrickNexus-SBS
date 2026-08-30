<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import {
  editAccount,
  fetchAccountDetail,
  fetchRoleDetail,
  type RoleInfo,
  type AccountInfo,
  type RoleDetail,
  type AssetPermItem,
} from '../../../api/user'
import { fetchAssetTree, type AssetTreeNode } from '../../../api/asset.ts'

const props = defineProps<{
  visible: boolean
  roleList: RoleInfo[]
  account: AccountInfo | null
}>()

const emit = defineEmits<{
  close: []
  updated: []
}>()

const loading = ref(false)
const fetchLoading = ref(false)
const error = ref('')
const form = reactive({
  account: '',
  password: '',
  nickname: '',
  role_id: '',
})

// ---------- 折叠控制 ----------
const assetPermExpanded = ref(false)
const assetTreeExpanded = ref<Set<string>>(new Set())

// ---------- 资产树 ----------
const assetTree = ref<AssetTreeNode[]>([])
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

// ---------- 资产权限 ----------
// 角色权限（蓝色、不可修改）
const rolePerms = reactive<Record<string, Set<string>>>({})
// 账户权限（可编辑）
const accountPerms = reactive<Record<string, { R: boolean; U: boolean; D: boolean; O: boolean }>>({})

function ensureAccountPerm(assetId: string) {
  if (!accountPerms[assetId]) accountPerms[assetId] = { R: false, U: false, D: false, O: false }
  return accountPerms[assetId]
}

function isRolePerm(assetId: string, key: string): boolean {
  return rolePerms[assetId]?.has(key) ?? false
}

// 从角色权限树递归提取权限集合
function collectRolePerms(nodes: any[]) {
  for (const node of nodes) {
    const set = new Set<string>()
    const p = node.permission || ''
    if (p.includes('R')) set.add('R')
    if (p.includes('U')) set.add('U')
    if (p.includes('D')) set.add('D')
    if (p.includes('O')) set.add('O')
    if (set.size > 0) rolePerms[node.asset_id] = set
    if (node.sub_assets) collectRolePerms(node.sub_assets)
  }
}

// 切换账户权限
function toggleAccountPerm(assetId: string, key: 'R' | 'U' | 'D' | 'O') {
  const p = ensureAccountPerm(assetId)
  p[key] = !p[key]
  // 勾选非 R 权限时自动勾选 R
  if (key !== 'R' && p[key]) p.R = true
  // 取消 R 时清掉所有权限
  if (key === 'R' && !p.R) { p.U = false; p.D = false; p.O = false }
}

// 递归渲染资产树
interface AssetPermRow {
  node: AssetTreeNode
  hasChildren: boolean
  expanded: boolean
  depth: number
  isOperable: boolean
}
function renderAssetNodes(nodes: AssetTreeNode[], depth: number): AssetPermRow[] {
  return nodes.map(node => {
    const hasChildren = (node.sub_assets?.length ?? 0) > 0
    const expanded = assetTreeExpanded.value.has(node.asset_id)
    const assetType = node.asset_type || node.type
    // 优先使用资产类型；在线状态和 depth 用于兼容旧版资产树响应
    const isOperable = assetType
      ? assetType === 'terminal' || assetType === 'sensor'
      : node.is_online !== undefined || depth >= 3
    return [
      { node, hasChildren, expanded, depth, isOperable },
      ...(hasChildren && expanded ? renderAssetNodes(node.sub_assets!, depth + 1) : []),
    ]
  }).flat()
}

function toggleAssetExpand(id: string) {
  const next = new Set(assetTreeExpanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  assetTreeExpanded.value = next
}

// ---------- 打开时加载 ----------
watch(() => props.visible, async (v) => {
  if (v && props.account) {
    form.account = props.account.account
    form.nickname = props.account.nickname
    form.password = ''
    const matched = props.roleList.find(r => r.name === props.account?.role_name)
    form.role_id = matched?.role_id ?? ''

    // 重置权限状态
    Object.keys(rolePerms).forEach(k => delete rolePerms[k])
    Object.keys(accountPerms).forEach(k => delete accountPerms[k])
    assetPermExpanded.value = false
    assetTreeExpanded.value = new Set()
    error.value = ''
    fetchLoading.value = true

    try {
      // 并行加载账号详情、角色详情、资产树
      const [acctDetail, roleDetail, assets] = await Promise.all([
        fetchAccountDetail(props.account.user_id),
        fetchRoleDetail(matched?.role_id ?? ''),
        fetchAssetTree(),
      ])

      assetTree.value = assets
      parentMap.value = {}
      childrenMap.value = {}
      buildMaps(assets)

      // 填入角色权限（蓝色不可改）
      if (roleDetail.asset_permission?.part_asset_id) {
        collectRolePerms(roleDetail.asset_permission.part_asset_id)
      }

      // 填入账户权限（可编辑）
      if (acctDetail.asset_permissions) {
        for (const item of acctDetail.asset_permissions) {
          const p = ensureAccountPerm(item.asset_id)
          if (item.perm_retrieve) p.R = true
          if (item.perm_update) p.U = true
          if (item.perm_delete) p.D = true
          if (item.perm_operate) p.O = true
        }
      }

      // 自动展开有权限的节点
      const expandSet = new Set<string>()
      const allIds = new Set([...Object.keys(rolePerms), ...Object.keys(accountPerms)])
      for (const id of allIds) {
        expandSet.add(id)
        let parent = parentMap.value[id]
        while (parent) { expandSet.add(parent); parent = parentMap.value[parent] }
      }
      assetTreeExpanded.value = expandSet
    } catch (e: any) {
      error.value = e?.message || '加载账号信息失败'
    } finally {
      fetchLoading.value = false
    }
  }
})

// ---------- 提交 ----------
async function confirm() {
  if (!props.account) return
  error.value = ''
  loading.value = true
  try {
    // 构建账户级资产权限（平铺列表）
    const asset_permissions: AssetPermItem[] = []
    for (const [assetId, p] of Object.entries(accountPerms)) {
      if (p.R || p.U || p.D || p.O) {
        asset_permissions.push({
          asset_id: assetId,
          perm_retrieve: p.R,
          perm_update: p.U,
          perm_delete: p.D,
          perm_operate: p.O,
        })
      }
    }

    await editAccount(props.account.user_id, {
      account: form.account,
      password: form.password,
      nickname: form.nickname,
      role_id: form.role_id,
      asset_permissions,
    })
    emit('updated')
    emit('close')
  } catch (e: any) {
    error.value = e?.message || '编辑失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" v-if="visible" @click.self="emit('close')">
    <div class="modal-card form-modal">
      <div class="modal-header"><h3>编辑账号</h3></div>

      <div class="modal-body" v-if="fetchLoading"><p class="hint">加载账号信息...</p></div>

      <div class="modal-body form-grid" v-else>
        <div class="field">
          <label class="field-label">账号名</label>
          <input v-model="form.account" type="text" placeholder="请输入账号名" class="field-input" />
        </div>
        <div class="field">
          <label class="field-label">昵称</label>
          <input v-model="form.nickname" type="text" placeholder="请输入昵称" class="field-input" />
        </div>
        <div class="field">
          <label class="field-label">密码</label>
          <input v-model="form.password" type="password" placeholder="请输入新密码" class="field-input" />
        </div>
        <div class="field">
          <label class="field-label">所属角色</label>
          <select v-model="form.role_id" class="field-select modal-select">
            <option value="" disabled>请选择角色</option>
            <option v-for="role in roleList" :key="role.role_id" :value="role.role_id">{{ role.name }}</option>
          </select>
        </div>

        <!-- 资产权限（折叠） -->
        <div class="field form-span-2">
          <div class="section-header" @click="assetPermExpanded = !assetPermExpanded">
            <span class="section-toggle">{{ assetPermExpanded ? '▾' : '▸' }}</span>
            <label class="field-label" style="cursor:pointer">资产实例权限</label>
            <span class="perm-legend"><span class="legend-dot legend-role"></span> 角色权限</span>
          </div>
          <div v-if="assetPermExpanded">
            <div class="perm-grid perm-grid-asset">
              <div class="perm-grid-header perm-grid-header-asset">
                <span class="perm-grid-label">资产名</span>
                <span class="perm-grid-col">查看</span>
                <span class="perm-grid-col">编辑</span>
                <span class="perm-grid-col">删除</span>
                <span class="perm-grid-col">操作</span>
              </div>
              <template v-for="row in renderAssetNodes(assetTree, 0)" :key="row.node.asset_id">
                <div class="perm-grid-row perm-grid-row-asset">
                  <span class="perm-grid-label" :style="{ paddingLeft: 8 + row.depth * 18 + 'px' }">
                    <span v-if="row.hasChildren" class="tree-toggle" @click="toggleAssetExpand(row.node.asset_id)">{{ row.expanded ? '▾' : '▸' }}</span>
                    <span v-else class="tree-toggle tree-toggle-empty"></span>
                    {{ row.node.name }}
                  </span>
                  <!-- R -->
                  <label class="perm-check">
                    <input type="checkbox"
                      :checked="isRolePerm(row.node.asset_id, 'R') || (accountPerms[row.node.asset_id]?.R ?? false)"
                      :disabled="isRolePerm(row.node.asset_id, 'R')"
                      :class="{ 'cb-role': isRolePerm(row.node.asset_id, 'R') }"
                      @change="toggleAccountPerm(row.node.asset_id, 'R')" />
                  </label>
                  <!-- U -->
                  <label class="perm-check">
                    <input type="checkbox"
                      :checked="isRolePerm(row.node.asset_id, 'U') || (accountPerms[row.node.asset_id]?.U ?? false)"
                      :disabled="isRolePerm(row.node.asset_id, 'U')"
                      :class="{ 'cb-role': isRolePerm(row.node.asset_id, 'U') }"
                      @change="toggleAccountPerm(row.node.asset_id, 'U')" />
                  </label>
                  <!-- D -->
                  <label class="perm-check">
                    <input type="checkbox"
                      :checked="isRolePerm(row.node.asset_id, 'D') || (accountPerms[row.node.asset_id]?.D ?? false)"
                      :disabled="isRolePerm(row.node.asset_id, 'D')"
                      :class="{ 'cb-role': isRolePerm(row.node.asset_id, 'D') }"
                      @change="toggleAccountPerm(row.node.asset_id, 'D')" />
                  </label>
                  <!-- O -->
                  <label class="perm-check" v-if="row.isOperable">
                    <input type="checkbox"
                      :checked="isRolePerm(row.node.asset_id, 'O') || (accountPerms[row.node.asset_id]?.O ?? false)"
                      :disabled="isRolePerm(row.node.asset_id, 'O')"
                      :class="{ 'cb-role': isRolePerm(row.node.asset_id, 'O') }"
                      @change="toggleAccountPerm(row.node.asset_id, 'O')" />
                  </label>
                  <span class="perm-grid-col" v-else></span>
                </div>
              </template>
              <p class="hint" v-if="assetTree.length === 0" style="grid-column:1/-1">加载中...</p>
            </div>
          </div>
        </div>

        <div class="modal-error form-span-2" v-if="error">{{ error }}</div>
      </div>
      <div class="modal-footer" v-if="!fetchLoading">
        <button class="btn btn-outline" @click="emit('close')" :disabled="loading">取消</button>
        <button class="btn btn-primary" @click="confirm" :disabled="loading">
          {{ loading ? '保存中...' : '保存' }}
        </button>
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

.modal-select { width: 100%; }

/* 折叠标题 */
.section-header { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
.section-toggle { font-size: 12px; color: #64748b; width: 16px; }

/* 图例 */
.perm-legend { font-size: 11px; color: #64748b; margin-left: auto; display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.legend-role { background: #3b82f6; }

/* 权限网格 */
.perm-grid { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.perm-grid-header, .perm-grid-row { display: grid; align-items: center; padding: 6px 12px; font-size: 13px; }
.perm-grid-header { background: #f8fafc; color: #64748b; font-weight: 600; }
.perm-grid-row { border-top: 1px solid #f1f5f9; }
.perm-grid-label { color: #334155; display: flex; align-items: center; gap: 4px; }
.perm-grid-col { text-align: center; }

.perm-grid-asset { max-height: 260px; overflow-y: auto; }
.perm-grid-header-asset { grid-template-columns: 1fr 60px 60px 60px 60px; position: sticky; top: 0; z-index: 1; }
.perm-grid-row-asset { grid-template-columns: 1fr 60px 60px 60px 60px; }

.perm-check { display: flex; align-items: center; justify-content: center; cursor: pointer; }
.perm-check input[type="checkbox"] { width: 16px; height: 16px; accent-color: #3b82f6; cursor: pointer; }
.perm-check input[type="checkbox"]:disabled { cursor: not-allowed; }
.perm-check input.cb-role { accent-color: #3b82f6; }

/* 树 */
.tree-toggle { width: 18px; height: 18px; display: grid; place-items: center; cursor: pointer; font-size: 11px; color: #94a3b8; flex-shrink: 0; }
.tree-toggle:hover { color: #475569; }
.tree-toggle-empty { cursor: default; }
.hint { padding: 12px; text-align: center; color: #94a3b8; font-size: 13px; margin: 0; }

/* 表单 */
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: #475569; }
.field-input, .field-select { height: 38px; padding: 0 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; color: #0f172a; background: #fff; outline: none; transition: border-color .2s ease, box-shadow .2s ease; }
.field-input:focus, .field-select:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.12); }
.field-input::placeholder { color: #94a3b8; }

/* 按钮 */
.btn { height: 38px; padding: 0 20px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background .2s ease; white-space: nowrap; }
.btn-outline { background: #f1f5f9; color: #475569; }
.btn-outline:hover { background: #e2e8f0; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
</style>
