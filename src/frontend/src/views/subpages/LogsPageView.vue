<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { fetchLogs, type LogLevel, type LogQuery, type LogType, type SystemLog } from '../../api/log'

const TYPE_OPTIONS: { value: LogType; label: string }[] = [
  { value: 'rule_action', label: '规则动作日志' },
  { value: 'rule_operation', label: '规则操作日志' },
]
const LEVEL_OPTIONS: { value: LogLevel; label: string }[] = [
  { value: 'DEBUG', label: '调试' }, { value: 'INFO', label: '信息' },
  { value: 'WARNING', label: '警告' }, { value: 'ERROR', label: '错误' },
  { value: 'CRITICAL', label: '严重' },
]
const typeLabels = Object.fromEntries(TYPE_OPTIONS.map(item => [item.value, item.label]))
const levelLabels = Object.fromEntries(LEVEL_OPTIONS.map(item => [item.value, item.label]))

const form = reactive({ type: '', level: '', operator: '', time: '' })
const applied = reactive({ type: '', level: '', operator: '', time: '' })
const logs = ref<SystemLog[]>([])
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const tableArea = ref<HTMLElement | null>(null)
let observer: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null

const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const rangeStart = computed(() => total.value ? (page.value - 1) * pageSize.value + 1 : 0)
const rangeEnd = computed(() => Math.min(page.value * pageSize.value, total.value))
const visiblePages = computed<(number | 'ellipsis-left' | 'ellipsis-right')[]>(() => {
  if (pages.value <= 7) return Array.from({ length: pages.value }, (_, index) => index + 1)
  const values: (number | 'ellipsis-left' | 'ellipsis-right')[] = [1]
  const start = Math.max(2, page.value - 1)
  const end = Math.min(pages.value - 1, page.value + 1)
  if (start > 2) values.push('ellipsis-left')
  for (let current = start; current <= end; current += 1) values.push(current)
  if (end < pages.value - 1) values.push('ellipsis-right')
  values.push(pages.value)
  return values
})

function queryBody(): LogQuery {
  return {
    type: applied.type as LogType || undefined,
    level: applied.level as LogLevel || undefined,
    operator: applied.operator.trim() || undefined,
    time: applied.time || undefined,
  }
}

async function load(targetPage = page.value) {
  loading.value = true
  error.value = ''
  page.value = targetPage
  try {
    const result = await fetchLogs(targetPage, pageSize.value, queryBody())
    logs.value = result.data
    total.value = result.total
    if (targetPage > pages.value) await load(pages.value)
  } catch (e: any) {
    logs.value = []
    total.value = 0
    error.value = e?.message || '日志加载失败'
  } finally { loading.value = false }
}

function search() {
  Object.assign(applied, form)
  load(1)
}
function reset() {
  Object.assign(form, { type: '', level: '', operator: '', time: '' })
  Object.assign(applied, form)
  load(1)
}
function adjustPageSize() {
  if (!tableArea.value) return
  // 表头固定占 44px，每一条日志占 52px；分页区域位于列表外部，不参与计算。
  const availableHeight = tableArea.value.clientHeight
  const next = Math.max(3, Math.min(50, Math.floor((availableHeight - 44) / 52)))
  if (next !== pageSize.value) { pageSize.value = next; load(1) }
}
function scheduleResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(adjustPageSize, 120)
}
function formatTime(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

onMounted(async () => {
  await nextTick()
  adjustPageSize()
  if (!loading.value) await load(1)
  observer = new ResizeObserver(scheduleResize)
  if (tableArea.value) observer.observe(tableArea.value)
  window.addEventListener('resize', scheduleResize)
})
onBeforeUnmount(() => { observer?.disconnect(); window.removeEventListener('resize', scheduleResize); if (resizeTimer) clearTimeout(resizeTimer) })
</script>

<template>
  <main class="logs-page">
    <section class="content-card">
      <header class="card-header">
        <div><h2>系统日志</h2><p>查看规则运行产生的动作日志及管理操作记录</p></div>
        <span class="total-chip">共 {{ total }} 条</span>
      </header>

      <form class="toolbar" @submit.prevent="search">
        <label><span>日志类型</span><select v-model="form.type"><option value="">全部类型</option><option v-for="item in TYPE_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <label><span>日志等级</span><select v-model="form.level"><option value="">全部等级</option><option v-for="item in LEVEL_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <label><span>操作人</span><input v-model="form.operator" maxlength="100" placeholder="昵称或 SYSTEM"></label>
        <label><span>日志日期</span><input v-model="form.time" type="date"></label>
        <div class="toolbar-actions"><button type="button" class="secondary" @click="reset">重置</button><button class="primary">查询日志</button></div>
      </form>

      <div v-if="error" class="alert">{{ error }} <button @click="load(page)">重新加载</button></div>
      <div ref="tableArea" class="table-area">
        <table>
          <thead><tr><th class="time-col">时间</th><th class="type-col">类型</th><th class="level-col">等级</th><th class="operator-col">操作人</th><th>日志内容</th></tr></thead>
          <tbody>
            <tr v-for="item in logs" :key="item.id">
              <td class="time-cell">{{ formatTime(item.time) }}</td>
              <td><span class="type-tag">{{ typeLabels[item.type] || item.type }}</span></td>
              <td><span class="level-tag" :class="item.level.toLowerCase()"><i></i>{{ levelLabels[item.level] || item.level }}</span></td>
              <td><span class="operator" :class="{ system: item.operator === 'SYSTEM' }">{{ item.operator || '—' }}</span></td>
              <td><div class="content-text" :title="item.content">{{ item.content || '—' }}</div></td>
            </tr>
            <tr v-if="!loading && !logs.length"><td colspan="5"><div class="empty"><span>⌕</span><strong>暂无日志记录</strong><small>请调整筛选条件后重新查询</small></div></td></tr>
          </tbody>
        </table>
        <div v-if="loading" class="loading">正在加载日志...</div>
      </div>

      <footer class="pagination">
        <span class="pagination-info">显示 {{ rangeStart }}–{{ rangeEnd }} 条，共 {{ total }} 条 · {{ pages }} 页</span>
        <div class="page-buttons">
          <button class="page-btn" :disabled="page <= 1 || loading" title="首页" @click="load(1)">«</button>
          <button class="page-btn" :disabled="page <= 1 || loading" title="上一页" @click="load(page - 1)">‹</button>
          <template v-for="item in visiblePages" :key="item">
            <span v-if="typeof item !== 'number'" class="page-ellipsis">…</span>
            <button v-else class="page-btn" :class="{ active: item === page }" :disabled="loading" @click="load(item)">{{ item }}</button>
          </template>
          <button class="page-btn" :disabled="page >= pages || loading" title="下一页" @click="load(page + 1)">›</button>
          <button class="page-btn" :disabled="page >= pages || loading" title="末页" @click="load(pages)">»</button>
        </div>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.logs-page{height:100%;min-height:0;padding:20px 24px;box-sizing:border-box;background:#f5f7fb;color:#26324b}.content-card{height:100%;min-height:0;display:flex;flex-direction:column;background:#fff;border:1px solid #e8edf5;border-radius:12px;box-shadow:0 3px 14px rgba(39,72,122,.06);overflow:hidden}.card-header{display:flex;align-items:center;justify-content:space-between;flex:none;padding:20px 24px 15px;border-bottom:1px solid #edf1f7}.card-header h2{margin:0;font-size:20px;color:#202b42}.card-header p{margin:6px 0 0;font-size:13px;color:#8b96aa}.total-chip{padding:6px 12px;border-radius:16px;color:#3975df;background:#edf4ff;font-size:13px}.toolbar{display:flex;align-items:flex-end;flex:none;gap:14px;padding:16px 24px;background:#fbfcfe;border-bottom:1px solid #edf1f7}.toolbar label{display:flex;flex-direction:column;gap:6px;min-width:150px}.toolbar label:nth-child(3){min-width:180px}.toolbar span{font-size:12px;color:#68758c}.toolbar input,.toolbar select{height:36px;padding:0 10px;border:1px solid #dce3ed;border-radius:6px;background:#fff;color:#34415a;box-sizing:border-box;outline:none}.toolbar input:focus,.toolbar select:focus{border-color:#4887ed;box-shadow:0 0 0 2px rgba(72,135,237,.1)}.toolbar-actions{display:flex;gap:8px;margin-left:auto}.toolbar button,.pagination button,.alert button{height:36px;padding:0 17px;border:1px solid #d8e0ec;border-radius:6px;background:#fff;color:#526078;cursor:pointer}.toolbar .primary{border-color:#397dec;background:#397dec;color:#fff}.toolbar button:hover:not(:disabled),.pagination button:hover:not(:disabled){border-color:#397dec;color:#397dec}.toolbar .primary:hover{color:#fff;background:#2e70db}.alert{flex:none;margin:12px 24px 0;padding:10px 14px;border-radius:7px;background:#fff1f1;color:#c94646;font-size:13px}.alert button{height:auto;margin-left:8px;padding:0;border:0;background:none;color:#397dec}.table-area{position:relative;flex:1;min-height:0;margin:14px 24px 0;overflow:hidden;border:1px solid #e8edf4;border-radius:8px}table{width:100%;border-collapse:collapse;table-layout:fixed}th{height:44px;padding:0 14px;background:#f6f8fb;text-align:left;color:#66738a;font-size:12px;font-weight:600}td{height:51px;padding:0 14px;border-top:1px solid #edf1f6;color:#3d4960;font-size:13px}.time-col{width:178px}.type-col{width:130px}.level-col{width:105px}.operator-col{width:125px}.time-cell{color:#69758a;font-variant-numeric:tabular-nums}.type-tag{display:inline-block;padding:4px 9px;border-radius:4px;background:#eef4fc;color:#49719f}.level-tag{display:inline-flex;align-items:center;gap:6px;font-weight:600}.level-tag i{width:7px;height:7px;border-radius:50%;background:#8b96a8}.level-tag.info{color:#3478df}.level-tag.info i{background:#4b8ced}.level-tag.warning{color:#c78112}.level-tag.warning i{background:#e7a62d}.level-tag.error{color:#d34b4b}.level-tag.error i{background:#e85b5b}.level-tag.critical{color:#a82f60}.level-tag.critical i{background:#bd376d}.level-tag.debug{color:#738096}.operator{font-weight:500}.operator.system{color:#6b55c5}.content-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#38455c}.loading{position:absolute;inset:44px 0 0;display:grid;place-items:center;background:rgba(255,255,255,.75);color:#6580aa}.empty{height:210px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:7px;color:#a0aabb}.empty span{font-size:30px}.empty strong{font-size:14px;color:#66738a}.empty small{font-size:12px}.pagination{height:58px;flex:none;display:flex;align-items:center;justify-content:flex-end;gap:4px;padding:0 24px;border-top:1px solid #edf1f6;background:#fff;color:#8490a4;font-size:12px}.pagination-info{margin-right:12px}.page-buttons{display:flex;align-items:center;gap:4px}.pagination .page-btn{display:grid;place-items:center;min-width:34px;height:34px;padding:0 8px;border-radius:6px}.pagination .page-btn.active{border-color:#397dec;background:#397dec;color:#fff}.pagination .page-btn.active:hover{color:#fff;background:#2e70db}.pagination button:disabled{opacity:.45;cursor:not-allowed}.page-ellipsis{display:grid;place-items:center;width:28px;height:34px;color:#8490a4}
@media(max-width:1000px){.toolbar{flex-wrap:wrap}.toolbar-actions{margin-left:0}.logs-page{padding:14px}.time-col{width:150px}.operator-col{width:100px}}
.logs-page{height:calc(100vh - 40px);overflow:hidden}
</style>
