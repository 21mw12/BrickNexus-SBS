<script setup lang="ts">
import { ref, watch } from 'vue'

type HeaderRow = { key: string; value: string }
const props = defineProps<{ modelValue: string; title?: string; hint?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const rows = ref<HeaderRow[]>([])
const error = ref('')
let syncing = false

function read(value: string) {
  try {
    const parsed = JSON.parse(value || '{}')
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error()
    rows.value = Object.entries(parsed).map(([key, item]) => ({ key, value: String(item) }))
    if (!rows.value.length) rows.value = [{ key: '', value: '' }]
    error.value = ''
  } catch {
    rows.value = [{ key: '', value: '' }]
    error.value = '请求头数据格式异常，请重新配置'
  }
}
function commit() {
  const result: Record<string, string> = {}
  error.value = ''
  for (const row of rows.value) {
    const key = row.key.trim()
    if (!key && !row.value.trim()) continue
    if (!key) { error.value = '请求头名称不能为空'; return }
    if (key in result) { error.value = `请求头「${key}」重复`; return }
    result[key] = row.value
  }
  syncing = true
  emit('update:modelValue', JSON.stringify(result, null, 2))
}
function add() { rows.value.push({ key: '', value: '' }) }
function remove(index: number) { rows.value.splice(index, 1); if (!rows.value.length) add(); commit() }
watch(() => props.modelValue, value => { if (syncing) { syncing = false; return } read(value) }, { immediate: true })
</script>

<template>
  <div class="header-editor">
    <div class="editor-head"><span>{{ title || '请求 Header' }}</span><small v-if="hint">{{ hint }}</small><button type="button" @click="add">＋ 添加一行</button></div>
    <div class="header-table">
      <div class="table-head"><span>Header 名称</span><span>Header 值</span><span>操作</span></div>
      <div v-for="(row,index) in rows" :key="index" class="header-row">
        <input v-model="row.key" placeholder="例如 Authorization" @input="commit">
        <input v-model="row.value" placeholder="例如 Bearer token" @input="commit">
        <button type="button" title="删除" @click="remove(index)">删除</button>
      </div>
    </div>
    <small v-if="error" class="editor-error">{{ error }}</small>
  </div>
</template>

<style scoped>
.header-editor,.header-editor *{box-sizing:border-box}.header-editor{min-width:0;width:100%;display:flex;flex-direction:column;gap:8px}.editor-head{min-width:0;display:flex;align-items:center;gap:8px;color:#334155;font-size:12px;font-weight:600}.editor-head small{min-width:0;color:#94a3b8;font-size:10px;font-weight:400}.editor-head button{flex:none;margin-left:auto;height:30px;padding:0 10px;border:1px solid #bfdbfe;border-radius:7px;color:#2563eb;background:#eff6ff}.header-table{min-width:0;width:100%;overflow:hidden;border:1px solid #d8e0eb;border-radius:9px;background:#fff}.table-head,.header-row{min-width:0;width:100%;display:grid;grid-template-columns:minmax(0,2fr) minmax(0,3fr) 72px;gap:10px;align-items:center;padding:7px 9px}.table-head>* ,.header-row>*{min-width:0}.table-head{color:#64748b;background:#f8fafc;font-size:10px}.table-head span:last-child{text-align:center}.header-row{border-top:1px solid #edf1f6}.header-row input{display:block;width:100%!important;max-width:100%;height:35px!important;min-height:35px!important;padding:0 9px!important;border:1px solid #d8e0eb!important;border-radius:7px!important}.header-row button{width:100%;height:30px;padding:0 6px;border:0;border-radius:6px;color:#dc2626;background:#fef2f2;white-space:nowrap}.editor-error{color:#dc2626!important}@media(max-width:600px){.table-head{display:none}.header-row{grid-template-columns:minmax(0,1fr) 60px;gap:7px}.header-row input:nth-child(2){grid-column:1}.header-row button{grid-column:2;grid-row:1/3}.editor-head{flex-wrap:wrap}.editor-head small{flex-basis:100%;order:3}.editor-head button{margin-left:auto}}
</style>
