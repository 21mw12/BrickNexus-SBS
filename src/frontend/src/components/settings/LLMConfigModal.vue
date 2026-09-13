<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  createLLMConfig, editLLMConfig, testLLMDraft, testLLMSaved,
  type LLMConfigItem, type LLMConfigPayload, type LLMServiceType, type LLMTestPayload,
} from '../../api/llmSettings'
import { notifyError, notifySuccess } from '../../utils/notification'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  item: LLMConfigItem | null
}>()
const emit = defineEmits<{ close: []; saved: [] }>()

const form = reactive({
  service_name: '', service_type: 'vllm' as LLMServiceType,
  base_url: '', model_name: '', max_tokens: 4096, num_ctx: 8192,
  api_key: '', api_key_mode: 'keep' as 'keep' | 'replace', api_key_configured: false,
})
const errors = reactive<Record<string, string>>({})
const saving = ref(false)
const testing = ref(false)
const isOllama = computed(() => form.service_type === 'ollama')
const title = computed(() => props.mode === 'create' ? '新增模型配置' : '编辑模型配置')

function reset() {
  Object.assign(form, {
    service_name: '', service_type: 'vllm', base_url: '', model_name: '',
    max_tokens: 4096, num_ctx: 8192, api_key: '', api_key_mode: 'keep', api_key_configured: false,
  })
  Object.keys(errors).forEach(key => delete errors[key])
  if (!props.item) return
  const content = props.item.content as any
  Object.assign(form, {
    service_name: props.item.service_name,
    service_type: props.item.service_type,
    base_url: content.base_url || '',
    model_name: content.model_name || '',
    max_tokens: content.max_tokens || 4096,
    num_ctx: content.num_ctx || 8192,
    api_key_configured: !!content.api_key_configured,
  })
}

watch(() => props.visible, visible => { if (visible) reset() })

function clearProviderFields() {
  form.api_key = ''
  form.api_key_mode = props.mode === 'edit' ? 'keep' : 'replace'
  form.api_key_configured = props.mode === 'edit' && props.item?.service_type === form.service_type
    ? !!(props.item.content as any).api_key_configured : false
  form.max_tokens = 4096
  form.num_ctx = 8192
  Object.keys(errors).forEach(key => delete errors[key])
}

function validate() {
  Object.keys(errors).forEach(key => delete errors[key])
  if (!form.service_name.trim()) errors.service_name = '请输入配置名称'
  if (!/^https?:\/\/[^\s]+$/i.test(form.base_url.trim())) errors.base_url = '请输入完整的 HTTP 或 HTTPS 地址'
  if (!form.model_name.trim()) errors.model_name = '请输入模型名称'
  if (isOllama.value) {
    if (!Number.isInteger(Number(form.num_ctx)) || Number(form.num_ctx) < 1) errors.num_ctx = '上下文长度必须为正整数'
  } else {
    if (!Number.isInteger(Number(form.max_tokens)) || Number(form.max_tokens) < 1) errors.max_tokens = '最大输出 Token 必须为正整数'
    const needsKey = props.mode === 'create' || form.api_key_mode === 'replace' || !form.api_key_configured
    if (needsKey && !form.api_key.trim()) errors.api_key = '请输入 API Key'
  }
  return Object.keys(errors).length === 0
}

function testPayload(): LLMTestPayload {
  const content: Record<string, unknown> = {
    base_url: form.base_url.trim(), model_name: form.model_name.trim(), model_type: 'chat',
  }
  if (isOllama.value) content.num_ctx = Number(form.num_ctx)
  else {
    content.max_tokens = Number(form.max_tokens)
    if (form.api_key.trim()) content.api_key = form.api_key.trim()
  }
  return { service_type: form.service_type, content }
}

function savePayload(): LLMConfigPayload {
  return { service_name: form.service_name.trim(), ...testPayload() }
}

async function runTest() {
  if (!validate()) return
  testing.value = true
  try {
    const payload = testPayload()
    const result = props.mode === 'edit' && props.item
      ? await testLLMSaved(props.item.llm_id, payload)
      : await testLLMDraft(payload)
    if (result.connected) notifySuccess(`连接成功，耗时 ${result.latency_ms} ms`, '模型连接测试')
    else notifyError(result.message || '模型服务不可用', '模型连接测试失败')
  } catch (error: any) {
    notifyError(error?.message || '模型连接测试失败', '模型连接测试失败')
  } finally { testing.value = false }
}

async function save() {
  if (!validate()) return
  saving.value = true
  try {
    const payload = savePayload()
    if (props.mode === 'edit' && props.item) await editLLMConfig(props.item.llm_id, payload)
    else await createLLMConfig(payload)
    notifySuccess(props.mode === 'create' ? '模型配置已新增' : '模型配置已更新')
    emit('saved')
  } catch (error: any) {
    notifyError(error?.message || '模型配置保存失败')
  } finally { saving.value = false }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="overlay" @click.self="!saving && !testing && emit('close')">
      <form class="modal" @submit.prevent="save">
        <header>
          <div><h2>{{ title }}</h2><p>配置聊天模型连接参数，保存后可在列表中激活。</p></div>
          <button type="button" aria-label="关闭" :disabled="saving || testing" @click="emit('close')">×</button>
        </header>
        <section class="body">
          <label>
            <span>配置名称 <b>*</b></span>
            <input v-model="form.service_name" maxlength="50" placeholder="例如：本地 Qwen">
            <small v-if="errors.service_name" class="field-error">{{ errors.service_name }}</small>
          </label>
          <label>
            <span>服务类型 <b>*</b></span>
            <select v-model="form.service_type" @change="clearProviderFields">
              <option value="vllm">vLLM</option><option value="ollama">Ollama</option><option value="deepseek">DeepSeek</option>
            </select>
          </label>
          <label class="wide">
            <span>Base URL <b>*</b></span>
            <input v-model="form.base_url" maxlength="500" :placeholder="isOllama ? 'http://127.0.0.1:11434' : 'https://example.com/v1'">
            <small v-if="errors.base_url" class="field-error">{{ errors.base_url }}</small>
            <small v-else class="hint">{{ isOllama ? '填写 Ollama 服务根地址，不需要添加 /api。' : '填写兼容 Chat Completions 的 API 根地址。' }}</small>
          </label>
          <label>
            <span>模型名称 <b>*</b></span>
            <input v-model="form.model_name" maxlength="200" placeholder="模型服务中的实际名称">
            <small v-if="errors.model_name" class="field-error">{{ errors.model_name }}</small>
          </label>
          <label><span>模型类型</span><input value="chat" disabled></label>
          <label v-if="isOllama">
            <span>上下文长度 <b>*</b></span>
            <input v-model.number="form.num_ctx" type="number" min="1" max="1048576">
            <small v-if="errors.num_ctx" class="field-error">{{ errors.num_ctx }}</small>
          </label>
          <template v-else>
            <label>
              <span>最大输出 Token <b>*</b></span>
              <input v-model.number="form.max_tokens" type="number" min="1" max="1048576">
              <small v-if="errors.max_tokens" class="field-error">{{ errors.max_tokens }}</small>
            </label>
            <div v-if="mode === 'edit' && form.api_key_configured" class="wide secret-mode">
              <span>API Key <b>*</b></span>
              <div><label><input v-model="form.api_key_mode" type="radio" value="keep">保留已配置密钥</label><label><input v-model="form.api_key_mode" type="radio" value="replace">设置新密钥</label></div>
            </div>
            <label v-if="mode === 'create' || form.api_key_mode === 'replace' || !form.api_key_configured" class="wide">
              <span>API Key <b>*</b></span>
              <input v-model="form.api_key" type="password" maxlength="4096" autocomplete="new-password" placeholder="密钥只会加密保存，不会再次显示">
              <small v-if="errors.api_key" class="field-error">{{ errors.api_key }}</small>
            </label>
          </template>
        </section>
        <footer>
          <button type="button" :disabled="saving || testing" @click="emit('close')">取消</button>
          <button type="button" class="test" :disabled="saving || testing" @click="runTest">{{ testing ? '测试中...' : '测试连接' }}</button>
          <button class="primary" :disabled="saving || testing">{{ saving ? '保存中...' : '保存' }}</button>
        </footer>
      </form>
    </div>
  </Teleport>
</template>

<style scoped>
*{box-sizing:border-box}.overlay{position:fixed;inset:0;z-index:1100;display:grid;place-items:center;background:rgba(15,23,42,.48)}.modal{width:660px;max-width:94vw;max-height:92vh;display:flex;flex-direction:column;border-radius:16px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.24);overflow:hidden}.modal header{display:flex;align-items:flex-start;justify-content:space-between;padding:20px 22px;border-bottom:1px solid #e2e8f0}.modal h2{margin:0 0 5px;color:#0f172a;font-size:19px}.modal header p{margin:0;color:#94a3b8;font-size:11px}.modal header button{padding:0;border:0;color:#64748b;background:none;font-size:24px;cursor:pointer}.body{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:20px 22px;overflow:auto}.body>label,.secret-mode{display:flex;flex-direction:column;gap:6px;color:#475569;font-size:12px;font-weight:600}.body span b{color:#dc2626}.body input,.body select{width:100%;height:38px;padding:0 11px;border:1px solid #cbd5e1;border-radius:8px;color:#334155;background:#fff;outline:none}.body input:focus,.body select:focus{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.11)}.body input:disabled{color:#94a3b8;background:#f1f5f9}.wide{grid-column:1/-1}.hint{color:#94a3b8;font-size:10px;font-weight:400}.field-error{color:#dc2626;font-size:10px;font-weight:500}.secret-mode>div{display:flex;gap:18px;padding:11px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc}.secret-mode label{display:flex;align-items:center;gap:7px;font-weight:400}.secret-mode input{width:auto;height:auto}.modal footer{display:flex;justify-content:flex-end;gap:8px;padding:14px 22px;border-top:1px solid #e2e8f0}.modal footer button{height:36px;padding:0 17px;border:0;border-radius:8px;color:#475569;background:#f1f5f9;cursor:pointer}.modal footer .test{color:#2563eb;background:#eff6ff}.modal footer .primary{color:#fff;background:#3b82f6}.modal footer button:disabled{opacity:.5;cursor:not-allowed}@media(max-width:650px){.body{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
