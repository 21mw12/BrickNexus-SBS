<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import type { AnalyticsResult, SelectedAnalysisPoint } from '../../api/analytics'
import AnalysisReportPanel from './AnalysisReportPanel.vue'

const props = defineProps<{
  visible: boolean
  result: AnalyticsResult | null
  points: SelectedAnalysisPoint[]
  algorithmLabel: string
}>()
const emit = defineEmits<{ close: []; ai: [] }>()
const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') emit('close') }
watch(() => props.visible, visible => {
  if (visible) document.addEventListener('keydown', closeOnEscape)
  else document.removeEventListener('keydown', closeOnEscape)
}, { immediate: true })
onBeforeUnmount(() => document.removeEventListener('keydown', closeOnEscape))
</script>

<template>
  <Teleport to="body">
    <div v-if="visible && result" class="report-drawer-overlay" @click.self="emit('close')">
      <aside class="report-drawer" role="dialog" aria-modal="true" aria-label="分析报告">
        <header><div><h2>分析报告</h2><p>分析结论、指标和数据质量</p></div><button type="button" aria-label="关闭分析报告" @click="emit('close')">×</button></header>
        <div class="report-drawer-body"><AnalysisReportPanel :result="result" :points="points" :algorithm-label="algorithmLabel" @ai="emit('ai')" /></div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
*{box-sizing:border-box}.report-drawer-overlay{position:fixed;inset:0;z-index:9000;background:rgba(15,23,42,.28);backdrop-filter:blur(1px)}.report-drawer{position:absolute;top:0;right:0;width:480px;max-width:calc(100vw - 32px);height:100%;display:flex;flex-direction:column;background:#fff;box-shadow:-18px 0 50px rgba(15,23,42,.2);animation:slide-in .2s ease-out}.report-drawer>header{display:flex;align-items:flex-start;justify-content:space-between;flex:none;padding:20px 22px 18px;border-bottom:1px solid #e2e8f0}.report-drawer h2{margin:0 0 5px;color:#172033;font-size:20px;line-height:1.3}.report-drawer header p{margin:0;color:#94a3b8;font-size:12px;line-height:1.5}.report-drawer header button{padding:0;border:0;color:#64748b;background:none;font-size:27px;line-height:1;cursor:pointer}.report-drawer-body{flex:1;min-height:0;overflow:hidden}@keyframes slide-in{from{transform:translateX(30px);opacity:.5}to{transform:translateX(0);opacity:1}}@media(max-width:560px){.report-drawer{width:100%;max-width:100%}.report-drawer>header{padding:18px 20px 16px}}
</style>
