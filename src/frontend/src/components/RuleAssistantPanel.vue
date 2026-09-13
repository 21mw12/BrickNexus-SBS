<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
export interface AssistantMessage { role: 'user' | 'assistant'; content: string }
const props = defineProps<{ busy: boolean; messages: AssistantMessage[]; canUndo: boolean; disabled: boolean }>()
const emit = defineEmits<{ send: [message: string]; undo: []; reset: [] }>()
const message = ref('')
const history = ref<HTMLElement | null>(null)
watch(() => props.messages.length, async () => {
  await nextTick()
  if (history.value) history.value.scrollTop = history.value.scrollHeight
})
function send() {
  const value = message.value.trim()
  if (!value) return
  emit('send', value)
  message.value = ''
}
</script>

<template>
  <section class="rule-assistant">
    <div class="assistant-heading"><strong>自然语言配置</strong><span>支持连续调整，当前表单始终优先</span><button type="button" :disabled="busy || disabled" @click="emit('reset')">新对话</button></div>
    <div ref="history" class="assistant-history">
      <div v-if="!messages.length" class="assistant-empty"><b>AI</b><span>描述你想创建或调整的规则，我会填写右侧表单内容。你仍可手动修改后继续对话。</span></div>
      <div v-for="(item,index) in messages" :key="index" class="assistant-message" :class="item.role"><b>{{item.role==='user'?'你':'AI'}}</b><span>{{item.content}}</span></div>
    </div>
    <textarea v-model="message" :disabled="busy || disabled" maxlength="6000" rows="2" placeholder="例如：阈值改成1000，持续十分钟后发送邮件" aria-label="规则配置需求" @keydown.ctrl.enter.prevent="send"></textarea>
    <div class="assistant-actions">
      <button type="button" :disabled="busy || disabled || !canUndo" @click="emit('undo')">撤销本次填充</button>
      <button type="button" class="send" :disabled="busy || disabled || !message.trim()" @click="send">{{ busy ? '正在生成…' : '发送' }}</button>
    </div>
  </section>
</template>

<style scoped>
.rule-assistant{min-width:0;min-height:0;height:100%;display:flex;flex-direction:column;padding:18px;background:#f8fafc;border-left:1px solid #e2e8f0}.assistant-heading{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin-bottom:12px;color:#334155;font-size:14px}.assistant-heading strong{font-size:15px}.assistant-heading span{order:3;width:100%;color:#94a3b8;font-size:11px;line-height:1.5}.assistant-heading button{margin-left:auto;border:0;background:transparent;color:#2563eb;cursor:pointer}.assistant-history{flex:1;min-height:0;overflow:auto;margin-bottom:12px;padding:10px;background:#fff;border:1px solid #e2e8f0;border-radius:10px}.assistant-empty,.assistant-message{display:flex;gap:8px;margin:7px 0;font-size:12px;line-height:1.65;color:#475569}.assistant-empty{margin:0;color:#94a3b8}.assistant-empty b,.assistant-message b{flex:0 0 24px;color:#2563eb}.assistant-message.user b{color:#64748b}.assistant-empty span,.assistant-message span{white-space:pre-wrap;overflow-wrap:anywhere}.rule-assistant textarea{box-sizing:border-box;width:100%;min-height:92px;max-height:130px;resize:none;padding:10px 11px;border:1px solid #cbd5e1;border-radius:9px;font:inherit;font-size:12px;line-height:1.55;background:white;color:#334155;outline:none}.rule-assistant textarea:focus{border-color:#60a5fa;box-shadow:0 0 0 3px #dbeafe}.assistant-actions{display:flex;justify-content:space-between;gap:8px;margin-top:9px}.assistant-actions button{padding:7px 11px;border:1px solid #cbd5e1;border-radius:7px;background:white;color:#475569;cursor:pointer}.assistant-actions .send{margin-left:auto;background:#2563eb;color:white;border-color:#2563eb}.assistant-actions button:disabled,.assistant-heading button:disabled{opacity:.5;cursor:not-allowed}@media(max-width:800px){.rule-assistant{padding:12px 16px;border-top:1px solid #e2e8f0;border-left:0}.assistant-heading{margin-bottom:7px}.assistant-history{margin-bottom:7px}.rule-assistant textarea{min-height:64px}}
</style>
