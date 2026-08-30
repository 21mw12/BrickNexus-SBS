<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { fetchAssetDetail, fetchAssetPage, editAsset, type EditAssetPayload, type AssetInfo } from '../../../api/asset.ts'
import RequestMappingModal from './RequestMappingModal.vue'

const props = defineProps<{
  visible: boolean
  assetId: string
}>()

const emit = defineEmits<{
  close: []
  updated: []
}>()

const loading = ref(false)
const fetching = ref(false)
const error = ref('')
const showMappingModal = ref(false)

// ---------- 资产类型显示名 ----------
const typeLabelMap: Record<string, string> = {
  building: '楼宇',
  floor: '楼层',
  room: '房间',
  terminal: '终端',
  sensor: '传感器',
}

/**
 * 每种资产类型对应的表单字段
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
  // sensor: 传感器型号创建后不可修改，无额外字段
}

const isUseOptions = [
  { label: '使用中', value: true },
  { label: '空闲', value: false },
]

/**
 * 子类型 → 父类型映射（building 没有父资产）
 */
const parentTypeMap: Record<string, string | null> = {
  building: null,
  floor: 'building',
  room: 'floor',
  terminal: 'room',
  sensor: 'terminal',
}

const needsParent = computed(() => {
  return parentTypeMap[form.asset_type] !== null
})

// ---------- 表单 ----------
const form = reactive<Record<string, any>>({
  asset_type: '',
  name: '',
  is_use: true,
  is_use_all: false,
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
  model_id: '',
})

// 传感器只读信息
const sensorReadonly = reactive<{ sensor_type?: string; model_name?: string; points?: { point_name: string; point_unit: string; point_description?: string | null }[] }>({})

const currentExtraFields = computed(() => {
  return typeExtraFields[form.asset_type] || []
})

// 清除所有类型特有字段
function clearExtraFields() {
  for (const fields of Object.values(typeExtraFields)) {
    for (const f of fields) {
      form[f.key] = ''
    }
  }
}

// ---------- 父资产下拉 ----------
const parentCandidates = ref<AssetInfo[]>([])
const parentSearch = ref('')
const parentDropdownOpen = ref(false)

const filteredParentCandidates = computed(() => {
  if (!parentSearch.value) return parentCandidates.value
  const keyword = parentSearch.value.toLowerCase()
  return parentCandidates.value.filter(a =>
    a.name.toLowerCase().includes(keyword)
  )
})

async function loadParentCandidates() {
  const parentType = parentTypeMap[form.asset_type]
  if (!parentType) {
    parentCandidates.value = []
    return
  }
  try {
    const result = await fetchAssetPage(1, 999, { asset_type: parentType })
    parentCandidates.value = result.data
  } catch (e) {
    parentCandidates.value = []
  }
}

function selectParent(asset: AssetInfo) {
  form.asset_id_parent = asset.id
  parentSearch.value = asset.name
  parentDropdownOpen.value = false
}

function toggleParentDropdown() {
  parentDropdownOpen.value = !parentDropdownOpen.value
}

function closeParentDropdown() {
  setTimeout(() => {
    parentDropdownOpen.value = false
    if (form.asset_id_parent) {
      const selected = parentCandidates.value.find(a => a.id === form.asset_id_parent)
      if (selected && parentSearch.value !== selected.name) {
        parentSearch.value = selected.name
      }
    }
  }, 150)
}

// 每次打开弹窗时加载详情
watch(() => props.visible, async (v) => {
  if (v && props.assetId) {
    fetching.value = true
    error.value = ''
    clearExtraFields()
    form.asset_id_parent = ''
    parentSearch.value = ''
    try {
      const detail = await fetchAssetDetail(props.assetId)
      form.asset_type = detail.asset_type
      form.name = detail.name
      form.is_use = detail.is_use
      form.number = detail.number || ''
      form.address = detail.address || ''
      form.level = (detail as any).level || ''
      form.room_purpose = (detail as any).room_purpose || ''
      form.max_current = (detail as any).max_current || ''
      form.manager_name = (detail as any).manager_name || ''
      form.model = (detail as any).model || ''
      form.location = (detail as any).location || ''
      form.iot_number = (detail as any).iot_number || ''
      form.iot_activate_human = (detail as any).iot_activate_human || ''
      form.model_id = (detail as any).model_id || ''

      // 传感器只读信息
      sensorReadonly.sensor_type = (detail as any).sensor_type
      sensorReadonly.model_name = (detail as any).model_name
      sensorReadonly.points = (detail as any).points || []

      // 加载父资产列表并预选当前父资产
      form.asset_id_parent = detail.asset_id_parent || ''
      parentSearch.value = detail.asset_parent_name || ''
      await loadParentCandidates()
    } catch (e: any) {
      error.value = e?.message || '获取资产详情失败'
    } finally {
      fetching.value = false
    }
  }
})

// ---------- 提交 ----------
async function confirm() {
  error.value = ''

  // 非楼宇类型必须选择父资产
  if (needsParent.value && !form.asset_id_parent) {
    error.value = '请选择父资产'
    return
  }

  loading.value = true
  try {
    const payload: EditAssetPayload = {
      name: form.name,
      is_use: form.is_use,
      asset_type: form.asset_type,
    }

    if (form.is_use_all) payload.is_use_all = true

    if (form.asset_id_parent) payload.asset_id_parent = form.asset_id_parent

    // 附加类型特有字段（排除空字符串）
    function setIf(k: string) {
      const v = form[k]
      if (v !== '' && v !== undefined && v !== null) (payload as unknown as Record<string, unknown>)[k] = v
    }
    const t = form.asset_type
    if (t === 'building') { setIf('number'); setIf('address') }
    else if (t === 'floor') { setIf('level') }
    else if (t === 'room') { setIf('number'); setIf('room_purpose'); setIf('max_current'); setIf('manager_name') }
    else if (t === 'terminal') { setIf('number'); setIf('model'); setIf('location'); setIf('iot_number'); setIf('iot_activate_human') }
    // sensor: 传感器型号创建后不可修改，无额外字段

    await editAsset(props.assetId, payload)
    emit('updated')
    emit('close')
  } catch (e: any) {
    error.value = e?.message || '修改失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" v-if="visible" @click.self="emit('close')">
    <div class="modal-card form-modal">
      <div class="modal-header">
        <h3>编辑资产</h3>
      </div>

      <!-- 加载中 -->
      <div class="modal-body" v-if="fetching">
        <p class="loading-text">加载资产信息...</p>
      </div>

      <div class="modal-body form-grid" v-else>
        <!-- 1. 资产类型（只读） -->
        <div class="field form-span-2">
          <label class="field-label">资产类型</label>
          <div class="readonly-field">{{ typeLabelMap[form.asset_type] || form.asset_type }}</div>
        </div>

        <!-- 2. 父资产（楼宇无父资产，其他类型需选择） -->
        <div class="field form-span-2" v-if="needsParent">
          <label class="field-label">父资产 <span class="required">*</span></label>
          <div class="parent-select">
            <div class="parent-search-row" @click="toggleParentDropdown">
              <input
                v-model="parentSearch"
                type="text"
                placeholder="搜索父资产名称..."
                class="parent-search-input"
                @focus="parentDropdownOpen = true"
                @blur="closeParentDropdown"
              />
              <span class="parent-arrow" :class="{ open: parentDropdownOpen }">▾</span>
            </div>
            <div class="parent-dropdown" v-if="parentDropdownOpen">
              <div
                v-for="candidate in filteredParentCandidates"
                :key="candidate.id"
                class="parent-option"
                :class="{ selected: candidate.id === form.asset_id_parent }"
                @mousedown.prevent="selectParent(candidate)"
              >
                <span>{{ candidate.name }}</span>
                <span class="parent-option-type">{{ candidate.type }}</span>
              </div>
              <div class="parent-empty" v-if="filteredParentCandidates.length === 0">
                无匹配资产
              </div>
            </div>
          </div>
        </div>

        <!-- 3. 资产名 -->
        <div class="field">
          <label class="field-label">资产名 <span class="required">*</span></label>
          <input
            v-model="form.name"
            type="text"
            placeholder="请输入资产名"
            class="field-input"
          />
        </div>

        <!-- 3. 使用状态 -->
        <div class="field">
          <label class="field-label">使用状态</label>
          <div class="use-row">
            <select v-model="form.is_use" class="field-select use-select">
              <option
                v-for="opt in isUseOptions"
                :key="String(opt.value)"
                :value="opt.value"
              >{{ opt.label }}</option>
            </select>
            <label class="perm-check use-check">
              <input type="checkbox" v-model="form.is_use_all" />
              <span>同时应用到所有子资产</span>
            </label>
          </div>
        </div>

        <!-- 4. 类型特有字段 -->
        <div class="field" v-for="field in currentExtraFields" :key="field.key">
          <label class="field-label">{{ field.label }}</label>
          <input
            v-model="form[field.key]"
            type="text"
            :placeholder="field.placeholder"
            class="field-input"
          />
        </div>

        <!-- 5. 传感器只读信息 -->
        <template v-if="form.asset_type === 'sensor'">
          <div class="field">
            <label class="field-label">传感器类型</label>
            <div class="readonly-value">{{ sensorReadonly.sensor_type || '-' }}</div>
          </div>
          <div class="field">
            <label class="field-label">传感器型号</label>
            <div class="readonly-value">{{ sensorReadonly.model_name || '-' }}</div>
          </div>
          <div class="field form-span-2" v-if="sensorReadonly.points?.length">
            <label class="field-label">测点信息</label>
            <div class="point-tags">
              <span class="point-tag" v-for="(p, i) in sensorReadonly.points" :key="i">
                {{ p.point_name }}<span class="point-unit" v-if="p.point_unit"> ({{ p.point_unit }})</span><span v-if="p.point_description"> · {{ p.point_description }}</span>
              </span>
            </div>
          </div>
        </template>

        <div class="modal-error form-span-2" v-if="error">{{ error }}</div>
      </div>
      <div class="modal-footer" v-if="!fetching">
        <button v-if="form.asset_type === 'terminal'" class="btn btn-outline" @click="showMappingModal = true">请求映射</button>
        <button class="btn btn-outline" style="margin-left:auto" @click="emit('close')" :disabled="loading">取消</button>
        <button class="btn btn-primary" @click="confirm" :disabled="loading">
          {{ loading ? '保存中...' : '确认' }}
        </button>
      </div>
      <RequestMappingModal
        :visible="showMappingModal"
        :terminalId="props.assetId"
        :terminalName="form.name"
        @close="showMappingModal = false"
      />
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: 520px;
  max-width: 90vw;
  max-height: 85vh;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px 0;
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.modal-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.form-modal { width: 760px; max-height: 90vh; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 16px; }
.form-grid .field { min-width: 0; }
.form-span-2 { grid-column: span 2; }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
  .form-span-2 { grid-column: span 1; }
}

.loading-text {
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
  padding: 24px 0;
  margin: 0;
}

.modal-error {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 13px;
  line-height: 1.5;
}

.modal-footer {
  padding: 0 24px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

/* ---------- 表单 ---------- */
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

.required {
  color: #dc2626;
}

.field-input {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.field-input::placeholder {
  color: #94a3b8;
}

.field-select {
  height: 38px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

/* ---------- 父资产选择器 ---------- */
.parent-select {
  position: relative;
}

.parent-search-row {
  display: flex;
  align-items: center;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.parent-search-row:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.parent-search-input {
  flex: 1;
  height: 38px;
  padding: 0 12px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: transparent;
  outline: none;
}

.parent-search-input::placeholder {
  color: #94a3b8;
}

.parent-arrow {
  flex-shrink: 0;
  width: 32px;
  height: 38px;
  display: grid;
  place-items: center;
  font-size: 12px;
  color: #94a3b8;
  transition: transform 0.2s ease;
}

.parent-arrow.open {
  transform: rotate(180deg);
}

.parent-dropdown {
  position: absolute;
  top: 42px;
  left: 0;
  right: 0;
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  z-index: 10;
}

.parent-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  font-size: 14px;
  color: #334155;
  cursor: pointer;
  transition: background 0.15s ease;
}

.parent-option:hover {
  background: #f1f5f9;
}

.parent-option.selected {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}

.parent-option-type {
  font-size: 12px;
  color: #94a3b8;
}

.parent-empty {
  padding: 12px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

/* ---------- 只读字段 ---------- */
.readonly-field {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #64748b;
  background: #f8fafc;
  display: flex;
  align-items: center;
}

/* 使用状态行 */
.use-row { display: flex; align-items: center; gap: 16px; }
.use-select { flex: 0 0 120px; }
.use-check { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #475569; cursor: pointer; }
.use-check input[type="checkbox"] { width: 15px; height: 15px; accent-color: #3b82f6; cursor: pointer; }

/* 只读值 & 测点标签 */
.readonly-value { padding: 10px 12px; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0; font-size: 14px; color: #334155; }
.point-tags { display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0; }
.point-tag {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 3px 10px; border-radius: 6px; font-size: 12px;
  background: #f8fafc; border: 1px solid #e2e8f0; color: #334155;
}
.point-tag .point-unit { font-size: 11px; color: #94a3b8; }

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
</style>
