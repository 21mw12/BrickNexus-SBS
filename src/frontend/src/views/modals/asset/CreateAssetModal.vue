<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { createAsset, fetchAssetPage, type CreateAssetPayload, type AssetInfo } from '../../../api/asset.ts'
import { fetchSensorModelPage, type SensorModelInfo } from '../../../api/sensorModel.ts'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  created: []
}>()

const loading = ref(false)
const error = ref('')

// ---------- 资产类型配置 ----------
const assetTypeOptions = [
  { label: '楼宇', value: 'building' },
  { label: '楼层', value: 'floor' },
  { label: '房间', value: 'room' },
  { label: '终端', value: 'terminal' },
  { label: '传感器', value: 'sensor' },
]

/**
 * 每种资产类型对应的表单字段
 */
const typeExtraFields: Record<string, { key: string; label: string; placeholder?: string; required?: boolean }[]> = {
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
    { key: 'model_id', label: '传感器型号', required: true },
  ],
}

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

const isUseOptions = [
  { label: '使用中', value: true },
  { label: '空闲', value: false },
]

// ---------- 表单 ----------
const form = reactive<Record<string, any>>({
  asset_type: 'building',
  asset_id_parent: '',
  name: '',
  is_use: true,
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

const currentExtraFields = computed(() => {
  return typeExtraFields[form.asset_type] || []
})

/** 当前类型是否需要选择父资产 */
const needsParent = computed(() => {
  return parentTypeMap[form.asset_type] !== null
})

// 切换资产类型时，清除类型特有字段并重新加载父资产列表
watch(() => form.asset_type, () => {
  form.asset_id_parent = ''
  parentSearch.value = ''
  for (const fields of Object.values(typeExtraFields)) {
    for (const f of fields) {
      form[f.key] = ''
    }
  }
  loadParentCandidates()
})

// ---------- 传感器型号下拉 ----------
const sensorModels = ref<SensorModelInfo[]>([])

async function loadSensorModels() {
  try {
    const result = await fetchSensorModelPage(1, 200)
    sensorModels.value = result.data
  } catch { /* ignore */ }
}

// 弹窗打开时预加载型号列表
watch(() => props.visible, (v) => {
  if (v) loadSensorModels()
})

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
  // 延迟关闭以允许点击选项
  setTimeout(() => {
    parentDropdownOpen.value = false
    // 如果搜索文本与已选资产不匹配，恢复显示
    if (form.asset_id_parent) {
      const selected = parentCandidates.value.find(a => a.id === form.asset_id_parent)
      if (selected && parentSearch.value !== selected.name) {
        parentSearch.value = selected.name
      }
    }
  }, 150)
}

// 每次打开弹窗时重置表单并加载父资产
watch(() => props.visible, async (v) => {
  if (v) {
    form.asset_type = 'building'
    form.asset_id_parent = ''
    form.name = ''
    form.is_use = true
    parentSearch.value = ''
    for (const fields of Object.values(typeExtraFields)) {
      for (const f of fields) {
        form[f.key] = ''
      }
    }
    error.value = ''
    await loadParentCandidates()
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
    const payload: CreateAssetPayload = {
      name: form.name,
      is_use: form.is_use,
      asset_type: form.asset_type,
    }

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
    else if (t === 'sensor') { setIf('model_id') }

    await createAsset(payload)
    emit('created')
    emit('close')
  } catch (e: any) {
    error.value = e?.message || '创建失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" v-if="visible" @click.self="emit('close')">
    <div class="modal-card form-modal">
      <div class="modal-header">
        <h3>新增资产</h3>
      </div>
      <div class="modal-body form-grid">
        <!-- 1. 资产类型 -->
        <div class="field form-span-2">
          <label class="field-label">资产类型 <span class="required">*</span></label>
          <select v-model="form.asset_type" class="field-select">
            <option
              v-for="opt in assetTypeOptions"
              :key="opt.value"
              :value="opt.value"
            >{{ opt.label }}</option>
          </select>
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

        <!-- 4. 使用状态 -->
        <div class="field">
          <label class="field-label">使用状态</label>
          <select v-model="form.is_use" class="field-select">
            <option
              v-for="opt in isUseOptions"
              :key="String(opt.value)"
              :value="opt.value"
            >{{ opt.label }}</option>
          </select>
        </div>

        <!-- 5. 类型特有字段 -->
        <template v-for="field in currentExtraFields" :key="field.key">
          <!-- model_id → 传感器型号下拉（必选） -->
          <div class="field" v-if="field.key === 'model_id'">
            <label class="field-label">{{ field.label }} <span class="required">*</span></label>
            <select v-model="form.model_id" class="field-select" required>
              <option value="" disabled>请选择传感器型号</option>
              <option v-for="m in sensorModels" :key="m.model_id" :value="m.model_id">
                {{ m.sensor_type || '-' }} - {{ m.model_name || m.model_id }}
              </option>
            </select>
          </div>
          <!-- 其他字段 → 文本输入 -->
          <div class="field" v-else>
            <label class="field-label">{{ field.label }}</label>
            <input v-model="form[field.key]" type="text" :placeholder="field.placeholder" class="field-input" />
          </div>
        </template>

        <div class="modal-error form-span-2" v-if="error">{{ error }}</div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" @click="emit('close')" :disabled="loading">取消</button>
        <button class="btn btn-primary" @click="confirm" :disabled="loading">
          {{ loading ? '创建中...' : '确认' }}
        </button>
      </div>
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
