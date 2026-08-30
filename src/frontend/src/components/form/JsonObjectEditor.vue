<script setup lang="ts">
import { ref, watch } from 'vue'
const props = withDefaults(defineProps<{ modelValue: string; title: string; rows?: number; hint?: string }>(), { rows: 5 })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const error = ref('')
function format() {
  try {
    const value = JSON.parse(props.modelValue || '{}')
    if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('必须是 JSON 对象')
    emit('update:modelValue', JSON.stringify(value, null, 2)); error.value = ''
  } catch (e: any) { error.value = e?.message === '必须是 JSON 对象' ? e.message : 'JSON 格式不正确' }
}
watch(() => props.modelValue, () => { if (error.value) error.value = '' })
</script>
<template>
  <label class="json-editor"><span class="json-head"><b>{{title}}</b><small v-if="hint">{{hint}}</small><button type="button" @click="format">格式化</button></span><textarea :value="modelValue" :rows="rows" spellcheck="false" :class="{invalid:error}" @input="emit('update:modelValue',($event.target as HTMLTextAreaElement).value)" @blur="format"></textarea><small v-if="error" class="json-error">{{error}}</small></label>
</template>
<style scoped>
.json-editor{display:flex!important;flex-direction:column!important;gap:7px!important}.json-head{display:flex!important;align-items:center;gap:7px;color:#334155!important}.json-head b{font-size:12px}.json-head small{color:#94a3b8!important;font-size:10px!important;font-weight:400}.json-head button{margin-left:auto;height:27px;padding:0 9px;border:1px solid #bfdbfe;border-radius:6px;color:#2563eb;background:#eff6ff}.json-editor textarea{width:100%;font:11px/1.55 ui-monospace,monospace}.json-editor textarea.invalid{border-color:#ef4444!important;box-shadow:0 0 0 3px rgba(239,68,68,.1)!important}.json-error{color:#dc2626!important}
</style>
