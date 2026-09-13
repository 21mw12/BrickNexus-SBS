<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  activateLLMConfig, deactivateLLMConfig, deleteLLMConfig, fetchLLMConfig,
  fetchLLMConfigs, testLLMSaved, type LLMConfigItem, type LLMServiceType,
} from '../../api/llmSettings'
import LLMConfigModal from '../../components/settings/LLMConfigModal.vue'
import ConfirmModal from '../modals/ConfirmModal.vue'
import { notifyError, notifyRetryableError, notifySuccess } from '../../utils/notification'

const rows = ref<LLMConfigItem[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const filters = reactive({ service_name: '', service_type: '' as '' | LLMServiceType, is_use: '' as '' | 'true' | 'false' })
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

async function load(target = page.value) {
  loading.value = true
  page.value = target
  try {
    const result = await fetchLLMConfigs(target, pageSize, {
      service_name: filters.service_name.trim() || undefined,
      service_type: filters.service_type || undefined,
      is_use: filters.is_use === '' ? undefined : filters.is_use === 'true',
    })
    rows.value = result.items
    total.value = result.total
    if (rows.value.length === 0 && target > 1) await load(target - 1)
  } catch (error: any) {
    rows.value = []
    total.value = 0
    notifyRetryableError(error?.message || '模型配置加载失败', () => void load(target), '模型配置加载失败')
  } finally { loading.value = false }
}

function resetFilters() {
  Object.assign(filters, { service_name: '', service_type: '', is_use: '' })
  void load(1)
}

const editorVisible = ref(false)
const editorMode = ref<'create' | 'edit'>('create')
const editorItem = ref<LLMConfigItem | null>(null)
function openCreate() { editorMode.value = 'create'; editorItem.value = null; editorVisible.value = true }
async function openEdit(row: LLMConfigItem) {
  try {
    editorItem.value = await fetchLLMConfig(row.llm_id)
    editorMode.value = 'edit'
    editorVisible.value = true
  } catch (error: any) { notifyError(error?.message || '模型配置详情加载失败') }
}
async function editorSaved() { editorVisible.value = false; await load(page.value) }

const testingIds = ref(new Set<string>())
async function testRow(row: LLMConfigItem) {
  if (testingIds.value.has(row.llm_id)) return
  testingIds.value = new Set(testingIds.value).add(row.llm_id)
  try {
    const result = await testLLMSaved(row.llm_id)
    if (result.connected) notifySuccess(`连接成功，耗时 ${result.latency_ms} ms`, `${row.service_name} · 连接测试`)
    else notifyError(result.message || '模型服务不可用', `${row.service_name} · 连接失败`)
  } catch (error: any) { notifyError(error?.message || '连接测试失败', `${row.service_name} · 连接失败`) }
  finally { const next = new Set(testingIds.value); next.delete(row.llm_id); testingIds.value = next }
}

type ConfirmKind = 'activate' | 'deactivate' | 'delete'
const confirmState = reactive<{ kind: ConfirmKind; row: LLMConfigItem | null }>({ kind: 'activate', row: null })
const actionLoading = ref(false)
const confirmTitle = computed(() => ({ activate: '激活模型', deactivate: '停用模型', delete: '删除模型' })[confirmState.kind])
const confirmMessage = computed(() => {
  const name = confirmState.row?.service_name || ''
  if (confirmState.kind === 'activate') return `激活「${name}」前会先测试连接；成功后当前活动模型将被停用。`
  if (confirmState.kind === 'deactivate') return `确定停用「${name}」吗？停用后规则自然语言助手将暂时不可用。`
  return `确定删除「${name}」吗？删除后无法恢复。`
})
function ask(kind: ConfirmKind, row: LLMConfigItem) { confirmState.kind = kind; confirmState.row = row }
async function confirmAction() {
  const row = confirmState.row
  if (!row) return
  actionLoading.value = true
  try {
    if (confirmState.kind === 'activate') {
      const result = await activateLLMConfig(row.llm_id)
      notifySuccess(`模型已激活，连接耗时 ${result.test.latency_ms} ms`)
    } else if (confirmState.kind === 'deactivate') {
      await deactivateLLMConfig(row.llm_id); notifySuccess('模型已停用')
    } else {
      await deleteLLMConfig(row.llm_id); notifySuccess('模型配置已删除')
    }
    confirmState.row = null
    await load(page.value)
  } catch (error: any) { notifyError(error?.message || `${confirmTitle.value}失败`) }
  finally { actionLoading.value = false }
}

function providerLabel(type: LLMServiceType) { return ({ vllm: 'vLLM', ollama: 'Ollama', deepseek: 'DeepSeek' })[type] }
function params(row: LLMConfigItem) {
  const content = row.content as any
  return row.service_type === 'ollama' ? `上下文 ${content.num_ctx}` : `最大输出 ${content.max_tokens}`
}
function dateTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false }) }

onMounted(() => void load(1))
</script>

<template>
  <main class="page-content">
    <section class="workspace">
      <header class="page-head">
        <div><h1>大语言模型</h1><p>管理规则自然语言助手使用的聊天模型连接</p></div>
        <button class="primary create" @click="openCreate">＋ 新增模型</button>
      </header>
      <section class="card">
        <form class="toolbar" @submit.prevent="load(1)">
          <label>配置名称<input v-model="filters.service_name" maxlength="50" placeholder="搜索名称"></label>
          <label>服务类型<select v-model="filters.service_type"><option value="">全部</option><option value="vllm">vLLM</option><option value="ollama">Ollama</option><option value="deepseek">DeepSeek</option></select></label>
          <label>激活状态<select v-model="filters.is_use"><option value="">全部</option><option value="true">已激活</option><option value="false">未激活</option></select></label>
          <div class="toolbar-actions"><button type="button" @click="resetFilters">重置</button><button class="primary">查询</button></div>
        </form>
        <div class="table-wrap">
          <table>
            <thead><tr><th>配置名称</th><th>服务</th><th>模型</th><th>Base URL</th><th>参数</th><th>密钥</th><th>状态</th><th>创建时间</th><th class="operation">操作</th></tr></thead>
            <tbody>
              <tr v-for="row in rows" :key="row.llm_id">
                <td><strong>{{ row.service_name }}</strong></td>
                <td><span class="provider" :class="row.service_type">{{ providerLabel(row.service_type) }}</span></td>
                <td>{{ row.content.model_name }}</td>
                <td class="url" :title="row.content.base_url">{{ row.content.base_url }}</td>
                <td>{{ params(row) }}</td>
                <td>{{ row.service_type === 'ollama' ? '不需要' : ((row.content as any).api_key_configured ? '已配置' : '未配置') }}</td>
                <td><span class="status" :class="{ active: row.is_use }">{{ row.is_use ? '已激活' : '未激活' }}</span></td>
                <td>{{ dateTime(row.created_at) }}</td>
                <td class="actions">
                  <button :disabled="testingIds.has(row.llm_id)" @click="testRow(row)">{{ testingIds.has(row.llm_id) ? '测试中' : '测试' }}</button>
                  <button @click="openEdit(row)">编辑</button>
                  <button v-if="row.is_use" class="warning" @click="ask('deactivate', row)">停用</button>
                  <button v-else class="activate" @click="ask('activate', row)">激活</button>
                  <button class="danger" :disabled="row.is_use" :title="row.is_use ? '请先停用或切换模型' : ''" @click="ask('delete', row)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="loading" class="state">正在加载...</div>
          <div v-else-if="!rows.length" class="state">暂无模型配置</div>
        </div>
        <footer v-if="total" class="pagination">
          <span>共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</span>
          <div><button :disabled="page <= 1 || loading" @click="load(page - 1)">上一页</button><button :disabled="page >= pages || loading" @click="load(page + 1)">下一页</button></div>
        </footer>
      </section>
    </section>
    <LLMConfigModal :visible="editorVisible" :mode="editorMode" :item="editorItem" @close="editorVisible = false" @saved="editorSaved" />
    <ConfirmModal :visible="!!confirmState.row" :title="confirmTitle" :message="confirmMessage" :confirm-text="confirmState.kind === 'delete' ? '删除' : '确认'" :danger="confirmState.kind !== 'activate'" :loading="actionLoading" @confirm="confirmAction" @cancel="confirmState.row = null" />
  </main>
</template>

<style scoped>
*{box-sizing:border-box}.page-content{flex:1;min-width:0;padding:20px 28px;overflow:hidden;color:#172033}.workspace{height:calc(100vh - 40px);min-height:0;display:flex;flex-direction:column}.page-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.page-head h1{margin:0 0 4px;color:#0f172a;font-size:22px}.page-head p{margin:0;color:#94a3b8;font-size:12px}.primary{border:0!important;color:#fff!important;background:#3b82f6!important}.create{height:36px;padding:0 16px;border-radius:8px;font-weight:600;cursor:pointer}.card{flex:1;min-height:0;display:flex;flex-direction:column;border-radius:16px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.06);overflow:hidden}.toolbar{display:flex;align-items:flex-end;gap:12px;padding:16px 20px;border-bottom:1px solid #e2e8f0;background:#fbfcfe}.toolbar label{display:flex;flex-direction:column;gap:5px;color:#64748b;font-size:11px}.toolbar input,.toolbar select{width:180px;height:35px;padding:0 10px;border:1px solid #cbd5e1;border-radius:7px;color:#334155;background:#fff;outline:none}.toolbar input:focus,.toolbar select:focus{border-color:#3b82f6}.toolbar-actions{display:flex;gap:7px;margin-left:auto}.toolbar-actions button{height:35px;padding:0 15px;border:0;border-radius:7px;color:#475569;background:#f1f5f9;cursor:pointer}.table-wrap{position:relative;flex:1;min-height:0;margin:14px 20px 0;overflow:auto;border:1px solid #e2e8f0;border-radius:9px}table{width:100%;min-width:1120px;border-collapse:collapse;table-layout:fixed}th,td{height:49px;padding:0 12px;border-bottom:1px solid #edf1f6;text-align:left;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}th{height:42px;color:#64748b;background:#f8fafc}th:nth-child(1){width:135px}th:nth-child(2){width:90px}th:nth-child(3){width:140px}th:nth-child(4){width:190px}th:nth-child(5){width:115px}th:nth-child(6){width:75px}th:nth-child(7){width:85px}th:nth-child(8){width:150px}.operation{width:250px}tbody tr:hover{background:#f8fafc}.provider,.status{display:inline-flex;padding:4px 8px;border-radius:6px;font-size:10px}.provider.vllm{color:#6d28d9;background:#ede9fe}.provider.ollama{color:#0369a1;background:#e0f2fe}.provider.deepseek{color:#1d4ed8;background:#dbeafe}.status{color:#64748b;background:#f1f5f9}.status.active{color:#047857;background:#d1fae5}.url{color:#64748b}.actions{display:flex;align-items:center;gap:5px;overflow:visible}.actions button{padding:5px 8px;border:0;border-radius:6px;color:#2563eb;background:#eff6ff;font-size:11px;cursor:pointer}.actions .activate{color:#047857;background:#ecfdf5}.actions .warning{color:#b45309;background:#fffbeb}.actions .danger{color:#dc2626;background:#fef2f2}.actions button:disabled{opacity:.38;cursor:not-allowed}.state{position:absolute;inset:43px 0 0;display:grid;place-items:center;color:#94a3b8;background:rgba(255,255,255,.88)}.pagination{height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;color:#94a3b8;font-size:11px}.pagination div{display:flex;gap:7px}.pagination button{height:31px;padding:0 12px;border:1px solid #e2e8f0;border-radius:6px;color:#475569;background:#fff;cursor:pointer}.pagination button:disabled{opacity:.4}@media(max-width:850px){.page-content{padding:14px;overflow:auto}.workspace{height:auto;min-height:calc(100vh - 28px)}.page-head{align-items:flex-start}.toolbar{flex-wrap:wrap}.toolbar-actions{margin-left:0}.card{min-height:650px}}
</style>
