<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { AnalyticsResult } from '../../api/analytics'
import { respondToAnalysis, type AnalysisInterpretation, type InterpretationConfidence } from '../../api/analysisAgent'
import { notifyError } from '../../utils/notification'

const props = defineProps<{
  visible: boolean
  result: AnalyticsResult | null
  algorithmLabel: string
}>()
const emit = defineEmits<{ close: [] }>()

interface ChatMessage { role: 'user' | 'assistant' | 'system'; content: string }

const report = ref<AnalysisInterpretation | null>(null)
const messages = ref<ChatMessage[]>([])
const conversationId = ref<string | null>(null)
const input = ref('')
const busy = ref(false)
const error = ref('')
const activeAnalysisId = ref<string | null>(null)
const scrollBody = ref<HTMLElement | null>(null)
let controller: AbortController | null = null

const analysisId = computed(() => props.result?.ai_context?.analysis_id || null)
const analysisLabels = { anomaly: '异常检测', clustering: '聚类分析', forecasting: '趋势预测' }
const confidenceLabels: Record<InterpretationConfidence, string> = { high: '高置信度', medium: '中等置信度', low: '低置信度' }

function reset(id: string | null) {
  controller?.abort()
  controller = null
  activeAnalysisId.value = id
  report.value = null
  messages.value = []
  conversationId.value = null
  input.value = ''
  error.value = ''
  busy.value = false
}

async function scrollToEnd() {
  await nextTick()
  if (scrollBody.value) scrollBody.value.scrollTop = scrollBody.value.scrollHeight
}

async function request(message?: string) {
  const id = analysisId.value
  if (!id || busy.value) return
  const expectedId = id
  const question = message?.trim()
  if (message !== undefined && !question) return
  if (question) messages.value.push({ role: 'user', content: question })
  error.value = ''
  busy.value = true
  controller?.abort()
  controller = new AbortController()
  await scrollToEnd()
  try {
    const response = await respondToAnalysis(id, controller.signal, conversationId.value || undefined, question)
    if (analysisId.value !== expectedId) return
    conversationId.value = response.conversation_id
    if (response.conversation_reset) {
      messages.value.push({ role: 'system', content: '原对话已过期，已根据当前分析报告重新建立上下文。' })
    }
    if (response.response_type === 'report') report.value = response.report
    else messages.value.push({ role: 'assistant', content: response.reply })
    input.value = ''
    await scrollToEnd()
  } catch (requestError: any) {
    if (requestError?.name === 'AbortError') return
    error.value = requestError?.message || 'AI分析失败'
    notifyError(error.value, 'AI分析失败')
  } finally {
    if (analysisId.value === expectedId) busy.value = false
  }
}

function send() { void request(input.value) }
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}
function close() {
  controller?.abort()
  emit('close')
}
function escape(event: KeyboardEvent) { if (event.key === 'Escape') close() }

watch(analysisId, id => { if (id !== activeAnalysisId.value) reset(id) }, { immediate: true })
watch(() => props.visible, visible => {
  if (visible) {
    document.addEventListener('keydown', escape)
    if (analysisId.value && !report.value && !busy.value) void request()
  } else {
    document.removeEventListener('keydown', escape)
    controller?.abort()
  }
}, { immediate: true })
onBeforeUnmount(() => { document.removeEventListener('keydown', escape); controller?.abort() })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible && result" class="analysis-agent-overlay" @click.self="close">
      <section class="analysis-agent-dialog" role="dialog" aria-modal="true" aria-label="AI分析">
        <header>
          <div><h2>AI 分析</h2><p>{{ analysisLabels[result.analysis_type] }} · {{ algorithmLabel || result.algorithm }} · {{ result.range.start_time }} 至 {{ result.range.actual_end_time }}</p></div>
          <button type="button" aria-label="关闭AI分析" @click="close">×</button>
        </header>

        <div ref="scrollBody" class="analysis-agent-body">
          <div v-if="busy && !report" class="agent-loading"><span></span><b>正在解读分析报告</b><p>AI只会使用当前报告的精简摘要，不会重新读取或修改数据。</p></div>
          <div v-else-if="error && !report" class="agent-error"><b>暂时无法生成解读</b><p>{{ error }}</p><button type="button" @click="request()">重新尝试</button></div>

          <template v-if="report">
            <section class="agent-overview"><h3>总体概述</h3><p>{{ report.overview }}</p></section>

            <section v-if="report.findings.length" class="agent-section">
              <h3>关键发现</h3>
              <article v-for="(item,index) in report.findings" :key="`finding-${index}`" class="interpretation-card">
                <header><b>{{ item.title }}</b><span :class="item.confidence">{{ confidenceLabels[item.confidence] }}</span></header>
                <p>{{ item.statement }}</p>
                <ul v-if="item.evidence.length"><li v-for="evidence in item.evidence" :key="evidence">{{ evidence }}</li></ul>
              </article>
            </section>

            <section v-if="report.inferences.length" class="agent-section">
              <h3>可以推导的内容</h3>
              <article v-for="(item,index) in report.inferences" :key="`inference-${index}`" class="interpretation-card inference">
                <header><b>{{ item.title }}</b><span :class="item.confidence">{{ confidenceLabels[item.confidence] }}</span></header>
                <p>{{ item.statement }}</p>
                <ul v-if="item.evidence.length"><li v-for="evidence in item.evidence" :key="evidence">依据：{{ evidence }}</li></ul>
              </article>
            </section>

            <div class="agent-list-grid">
              <section v-if="report.cautions.length" class="agent-list-card caution"><h3>需要注意</h3><ul><li v-for="item in report.cautions" :key="item">{{ item }}</li></ul></section>
              <section v-if="report.recommended_checks.length" class="agent-list-card checks"><h3>建议核查</h3><ul><li v-for="item in report.recommended_checks" :key="item">{{ item }}</li></ul></section>
            </div>
            <section v-if="report.limitations.length" class="agent-limitations"><h3>分析局限</h3><ul><li v-for="item in report.limitations" :key="item">{{ item }}</li></ul></section>
          </template>

          <section v-if="messages.length" class="agent-conversation" aria-label="追问记录">
            <article v-for="(message,index) in messages" :key="index" :class="['agent-message',message.role]"><b>{{ message.role === 'user' ? '你' : message.role === 'assistant' ? 'AI' : '提示' }}</b><p>{{ message.content }}</p></article>
          </section>
          <div v-if="busy && report" class="answer-loading"><span></span>正在回答...</div>
        </div>

        <footer>
          <p>AI解读仅供辅助判断，请以原始数据和确定性指标为准。</p>
          <div><textarea v-model="input" :disabled="busy || !report" maxlength="2000" rows="2" placeholder="针对当前报告继续提问，Enter发送，Shift+Enter换行" @keydown="keydown"></textarea><button type="button" :disabled="busy || !report || !input.trim()" @click="send">{{ busy ? '分析中' : '发送' }}</button></div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
*{box-sizing:border-box}.analysis-agent-overlay{position:fixed;inset:0;z-index:10050;display:grid;place-items:center;padding:20px;background:rgba(15,23,42,.52);backdrop-filter:blur(2px)}.analysis-agent-dialog{width:780px;max-width:calc(100vw - 40px);height:min(760px,86vh);display:flex;flex-direction:column;border:1px solid rgba(255,255,255,.75);border-radius:18px;background:#fff;box-shadow:0 28px 80px rgba(15,23,42,.3);overflow:hidden}.analysis-agent-dialog>header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex:none;padding:20px 24px 17px;border-bottom:1px solid #e2e8f0}.analysis-agent-dialog>header h2{margin:0 0 5px;color:#0f172a;font-size:20px}.analysis-agent-dialog>header p{margin:0;color:#8492a6;font-size:12px;line-height:1.5}.analysis-agent-dialog>header button{padding:0;border:0;color:#64748b;background:none;font-size:27px;line-height:1;cursor:pointer}.analysis-agent-body{flex:1;min-height:0;padding:20px 24px;overflow-y:auto;color:#475569;background:#fbfcfe}.agent-loading,.agent-error{min-height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.agent-loading span,.answer-loading span{width:24px;height:24px;border:3px solid #dbeafe;border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite}.agent-loading b,.agent-error b{margin-top:12px;color:#334155;font-size:15px}.agent-loading p,.agent-error p{max-width:460px;margin:7px 0;color:#94a3b8;font-size:12px;line-height:1.6}.agent-error button{height:34px;margin-top:10px;padding:0 15px;border:0;border-radius:8px;color:#fff;background:#3b82f6;cursor:pointer}.agent-overview,.agent-section,.agent-limitations{margin-bottom:16px;padding:16px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}.agent-overview{border-color:#bfdbfe;background:#eff6ff}.analysis-agent-body h3{margin:0 0 10px;color:#334155;font-size:14px}.agent-overview p,.interpretation-card p,.agent-message p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.7}.interpretation-card{padding:13px 0;border-top:1px dashed #dbe3ee}.interpretation-card:first-of-type{padding-top:0;border-top:0}.interpretation-card:last-child{padding-bottom:0}.interpretation-card>header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}.interpretation-card header b{color:#334155;font-size:13px}.interpretation-card header span{flex:none;padding:3px 7px;border-radius:99px;font-size:10px}.interpretation-card header .high{color:#166534;background:#dcfce7}.interpretation-card header .medium{color:#92400e;background:#fef3c7}.interpretation-card header .low{color:#64748b;background:#f1f5f9}.interpretation-card ul,.agent-list-card ul,.agent-limitations ul{margin:8px 0 0;padding-left:20px;color:#64748b;font-size:12px;line-height:1.65}.interpretation-card.inference{padding-left:10px;border-left:3px solid #c4b5fd}.agent-list-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}.agent-list-card{padding:15px;border-radius:12px}.agent-list-card.caution{border:1px solid #fde68a;background:#fffbeb}.agent-list-card.checks{border:1px solid #bbf7d0;background:#f0fdf4}.agent-limitations{color:#64748b;background:#f8fafc}.agent-conversation{display:flex;flex-direction:column;gap:11px;margin-top:20px;padding-top:18px;border-top:1px solid #e2e8f0}.agent-message{max-width:84%;padding:11px 13px;border-radius:12px;background:#fff;box-shadow:0 1px 4px rgba(15,23,42,.07)}.agent-message.user{align-self:flex-end;color:#fff;background:#3b82f6}.agent-message.system{align-self:center;max-width:100%;color:#92400e;background:#fffbeb}.agent-message b{display:block;margin-bottom:4px;font-size:10px;opacity:.72}.agent-message p{font-size:12px}.answer-loading{display:flex;align-items:center;gap:8px;margin-top:12px;color:#64748b;font-size:12px}.answer-loading span{width:16px;height:16px;border-width:2px}.analysis-agent-dialog>footer{flex:none;padding:13px 20px 16px;border-top:1px solid #e2e8f0;background:#fff}.analysis-agent-dialog>footer>p{margin:0 0 8px;color:#94a3b8;font-size:10px}.analysis-agent-dialog>footer>div{display:flex;align-items:flex-end;gap:10px}.analysis-agent-dialog textarea{flex:1;min-height:58px;max-height:120px;padding:10px 12px;resize:vertical;border:1px solid #cbd5e1;border-radius:10px;color:#334155;font:inherit;font-size:12px;line-height:1.5;outline:none}.analysis-agent-dialog textarea:focus{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.11)}.analysis-agent-dialog footer button{height:38px;padding:0 18px;border:0;border-radius:9px;color:#fff;background:#3b82f6;font-weight:650;cursor:pointer}.analysis-agent-dialog footer button:disabled{opacity:.5;cursor:not-allowed}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:760px){.analysis-agent-overlay{padding:8px}.analysis-agent-dialog{width:100%;max-width:100%;height:calc(100vh - 16px);border-radius:14px}.analysis-agent-dialog>header{padding:17px 18px 14px}.analysis-agent-body{padding:16px}.agent-list-grid{grid-template-columns:1fr}.agent-message{max-width:92%}.analysis-agent-dialog>footer{padding:11px 14px 14px}}
</style>
