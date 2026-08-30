<script setup lang="ts">
import { ref, watch } from 'vue'
import { executeControl, fetchControlPage, type ControlAssetType, type ControlListItem, type ExecuteControlResult } from '../../api/control'
import JsonTreeViewer from './asset/JsonTreeViewer.vue'

const props = defineProps<{ visible: boolean; assetId: string; assetType: ControlAssetType; assetName: string }>()
const emit = defineEmits<{ close: [] }>()
const controls = ref<ControlListItem[]>([])
const loading = ref(false)
const error = ref('')
const executingId = ref('')
const result = ref<ExecuteControlResult | null>(null)
const executedControlName = ref('')

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

async function loadControls() {
  if (!props.assetId) return
  loading.value = true
  error.value = ''
  controls.value = []
  result.value = null
  try {
    const first = await fetchControlPage(1, 100, { status: true, asset_type: props.assetType, asset_id: props.assetId })
    controls.value = first.data
    const pages = Math.ceil(first.total / 100)
    if (pages > 1) {
      const rest = await Promise.all(Array.from({ length: pages - 1 }, (_, index) => fetchControlPage(index + 2, 100, { status: true, asset_type: props.assetType, asset_id: props.assetId })))
      controls.value.push(...rest.flatMap(item => item.data))
    }
  } catch (e: any) {
    error.value = e?.message || '加载可控制项失败'
  } finally {
    loading.value = false
  }
}

async function execute(item: ControlListItem) {
  executingId.value = item.control_id
  executedControlName.value = item.name
  error.value = ''
  result.value = null
  try {
    result.value = await executeControl(item.control_id)
  } catch (e: any) {
    error.value = e?.message || '执行控制失败'
  } finally {
    executingId.value = ''
  }
}

watch(() => props.visible, visible => { if (visible) void loadControls() })
</script>

<template>
  <div v-if="visible" class="control-overlay" @click.self="emit('close')">
    <section class="control-modal">
      <header>
        <div><h2>控制 {{ assetName }}</h2><p>{{ assetType === 'terminal' ? '终端' : '传感器' }} · 仅显示已启用的控制项目</p></div>
        <button type="button" @click="emit('close')">×</button>
      </header>
      <div class="control-body">
        <div v-if="loading" class="control-state">正在加载可控制项...</div>
        <div v-else-if="error" class="control-error">{{ error }}<button type="button" @click="loadControls">重新加载</button></div>
        <div v-else-if="!controls.length" class="control-empty"><span>⌁</span><b>该资产没有可控制项</b><small>请先在控制管理中创建并启用 Control</small></div>
        <template v-else>
          <div class="control-list">
            <div v-for="item in controls" :key="item.control_id" class="control-item">
              <span>{{ item.name }}</span>
              <button type="button" :disabled="!!executingId" @click="execute(item)">{{ executingId === item.control_id ? '执行中...' : '执行控制' }}</button>
            </div>
          </div>
          <div v-if="result" class="execution-result">
            <div class="result-summary">
              <span class="result-icon" :class="{ success: result.success }">{{ result.success ? '✓' : '!' }}</span>
              <div><b>{{ result.success ? '控制执行成功' : '控制执行失败' }}</b><small>{{ executedControlName }}</small></div>
              <time><small>执行时间</small>{{ formatTime(result.executed_at) }}</time>
            </div>
            <div class="result-json"><div class="json-title">执行结果</div><JsonTreeViewer :data="result.result" :depth="0" /></div>
          </div>
        </template>
      </div>
      <footer><button type="button" @click="emit('close')">关闭</button></footer>
    </section>
  </div>
</template>

<style scoped>
*{box-sizing:border-box}.control-overlay{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;background:rgba(15,23,42,.5)}.control-modal{width:720px;max-width:94vw;max-height:90vh;display:flex;flex-direction:column;overflow:hidden;border-radius:18px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.25)}.control-modal>header{position:relative;display:flex;align-items:center;justify-content:space-between;padding:21px 24px;border-bottom:1px solid #e2e8f0;background:linear-gradient(135deg,#f8fbff,#fff)}.control-modal>header:before{content:'';position:absolute;left:0;top:19px;bottom:19px;width:4px;border-radius:0 4px 4px 0;background:#3b82f6}.control-modal h2{margin:0 0 4px;color:#0f172a;font-size:19px}.control-modal header p{margin:0;color:#94a3b8;font-size:11px}.control-modal header>button{width:34px;height:34px;border:0;border-radius:9px;color:#64748b;background:#f1f5f9;font-size:22px}.control-body{min-height:250px;padding:20px 22px;overflow:auto;background:#f8fafc}.control-state{min-height:210px;display:grid;place-items:center;color:#64748b}.control-error{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;border-radius:8px;color:#b91c1c;background:#fef2f2;font-size:12px}.control-error button{border:0;color:#2563eb;background:transparent}.control-empty{min-height:230px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:7px;color:#94a3b8}.control-empty span{font-size:34px}.control-empty b{color:#475569;font-size:14px}.control-empty small{font-size:11px}.control-list{display:flex;flex-direction:column;gap:8px}.control-item{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:11px 13px;border:1px solid #e2e8f0;border-radius:9px;background:#fff}.control-item span{overflow:hidden;color:#334155;font-size:13px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.control-item button{flex:none;height:32px;padding:0 13px;border:1px solid #bfdbfe;border-radius:7px;color:#2563eb;background:#eff6ff}.control-item button:disabled{opacity:.5}.execution-result{margin-top:16px;overflow:hidden;border:1px solid #dbeafe;border-radius:11px;background:#fff}.result-summary{display:grid;grid-template-columns:38px minmax(0,1fr) auto;align-items:center;gap:10px;padding:13px 15px;border-bottom:1px solid #e2e8f0;background:#f8fbff}.result-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:50%;color:#b45309;background:#fef3c7;font-weight:700}.result-icon.success{color:#047857;background:#d1fae5}.result-summary div{display:flex;flex-direction:column;gap:3px}.result-summary b{color:#1e293b;font-size:13px}.result-summary small{color:#94a3b8;font-size:10px}.result-summary time{display:flex;align-items:flex-end;flex-direction:column;gap:3px;color:#475569;font-size:11px}.json-title{margin-bottom:8px;color:#475569;font-size:11px;font-weight:700}.result-json{max-height:300px;padding:13px 15px;overflow:auto}.control-modal>footer{display:flex;justify-content:flex-end;padding:14px 22px;border-top:1px solid #e2e8f0}.control-modal>footer button{height:36px;padding:0 18px;border:1px solid #e2e8f0;border-radius:7px;color:#475569;background:#f8fafc}@media(max-width:600px){.result-summary{grid-template-columns:38px 1fr}.result-summary time{grid-column:1/-1;align-items:flex-start}.control-body{padding:14px}}
</style>
