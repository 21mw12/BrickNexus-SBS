<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import DataSectionTabs from '../../components/data/DataSectionTabs.vue'
import HistoricalPointSelector from '../../components/data/HistoricalPointSelector.vue'
import TimeRangeQueryBar, { type TimeRangeValue } from '../../components/data/TimeRangeQueryBar.vue'
import AnalysisConfigPanel, { type AnalysisConfigValue } from '../../components/analytics/AnalysisConfigPanel.vue'
import AnalysisReportDrawer from '../../components/analytics/AnalysisReportDrawer.vue'
import AnalysisAgentDialog from '../../components/analytics/AnalysisAgentDialog.vue'
import AnomalyResult from '../../components/analytics/AnomalyResult.vue'
import ClusteringResult from '../../components/analytics/ClusteringResult.vue'
import ForecastResult from '../../components/analytics/ForecastResult.vue'
import { fetchAnalyticsAlgorithms, runAnalytics, type Aggregation, type AlgorithmCatalog, type AnalysisType, type AnalyticsResult, type MissingStrategy, type SelectedAnalysisPoint } from '../../api/analytics'
import { notifyError } from '../../utils/notification'
import { loadDataPageContext, storeDataPageContext } from '../../utils/dataPageContext'

const pad=(value:number)=>String(value).padStart(2,'0');const format=(date:Date)=>`${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:00`
const end=new Date();end.setMinutes(Math.floor(end.getMinutes()/15)*15,0,0);const start=new Date(end.getTime()-24*60*60*1000)
const savedContext=loadDataPageContext()
const range=ref<TimeRangeValue>(savedContext?.range||{start_time:format(start),end_time:format(end),sample_count:500})
const points=ref<SelectedAnalysisPoint[]>(savedContext?.points||[]), catalog=ref<AlgorithmCatalog>({anomaly:[],clustering:[],forecasting:[]}),analysisType=ref<AnalysisType>('anomaly'),algorithm=ref('robust_zscore'),mode=ref<'per_point'|'joint'>('per_point'),parameters=ref<Record<string,unknown>>({})
const aggregation=ref<Aggregation>('mean'),missingStrategy=ref<MissingStrategy>('interpolate'),maxGap=ref(3),result=ref<AnalyticsResult|null>(null),busy=ref(false),configOpen=ref(false),reportOpen=ref(false),agentOpen=ref(false)
const specs=computed(()=>catalog.value[analysisType.value]||[])
const currentSpec=computed(()=>specs.value.find(item=>item.name===algorithm.value))
const analysisTypeLabel:Record<AnalysisType,string>={anomaly:'异常检测',clustering:'聚类分析',forecasting:'趋势预测'}
const configurationLabel=computed(()=>`${analysisTypeLabel[analysisType.value]} · ${currentSpec.value?.label||'默认算法'}`)
function resetAlgorithm(){configOpen.value=false;const spec=specs.value[0];if(!spec)return;algorithm.value=spec.name;mode.value=spec.modes[0]||'per_point';parameters.value=Object.fromEntries(spec.parameters.map(item=>[item.name,item.default]))}
watch([analysisType,points,range,algorithm,mode,parameters,aggregation,missingStrategy,maxGap],()=>{result.value=null;reportOpen.value=false;agentOpen.value=false},{deep:true})
watch([points,range],()=>storeDataPageContext(range.value,points.value),{deep:true})
function validate(){if(!points.value.length)return '请至少选择一个测点';if((analysisType.value==='clustering'||mode.value==='joint')&&points.value.length<2)return '当前分析至少需要两个测点';if(range.value.sample_count<100||range.value.sample_count>1000)return '时间桶数量必须为100～1000';return ''}
function applyConfig(value:AnalysisConfigValue){analysisType.value=value.analysisType;algorithm.value=value.algorithm;mode.value=value.mode;parameters.value=value.parameters;aggregation.value=value.aggregation;missingStrategy.value=value.missingStrategy;maxGap.value=value.maxGap;configOpen.value=false}
async function run(){
  const error=validate()
  if(error){notifyError(error);return}
  result.value=null
  reportOpen.value=false
  busy.value=true
  try{
    result.value=await runAnalytics({analysis_type:analysisType.value,point_ids:points.value.map(item=>item.point_id),...range.value,preprocessing:{aggregation:aggregation.value,missing_strategy:missingStrategy.value,max_gap:maxGap.value},algorithm:{name:algorithm.value,mode:mode.value,parameters:parameters.value}})
    reportOpen.value=true
  }catch(e:any){
    notifyError(e?.message||'智能分析失败')
  }finally{
    busy.value=false
  }
}
onMounted(async()=>{try{catalog.value=await fetchAnalyticsAlgorithms();resetAlgorithm()}catch(e:any){notifyError(e?.message||'加载算法目录失败')}})
</script>

<template><main class="page-content"><section class="workspace"><DataSectionTabs/><header class="page-head"><h1>智能分析</h1><p>对历史测点数据执行异常检测、运行状态聚类和趋势预测</p></header><div class="layout"><section class="main-card"><TimeRangeQueryBar v-model="range" :busy="busy" :configuration-label="configurationLabel" report-label="分析报告" :report-disabled="!result" :report-count="result?.warnings.length||0" @configure="configOpen=true" @submit="run" @report="reportOpen=true"/><div class="result-area"><div v-if="busy" class="empty"><span class="spinner"></span><b>正在执行智能分析</b></div><div v-else-if="!result" class="empty"><b>等待分析</b><p>选择测点、时间范围和分析方案后开始计算</p></div><AnomalyResult v-else-if="result.analysis_type==='anomaly'" :result="result.result" :points="points"/><ClusteringResult v-else-if="result.analysis_type==='clustering'" :result="result.result" :points="points"/><ForecastResult v-else :result="result.result" :points="points"/></div></section><HistoricalPointSelector v-model="points"/></div><AnalysisConfigPanel :visible="configOpen" :catalog="catalog" :analysis-type="analysisType" :algorithm="algorithm" :mode="mode" :parameters="parameters" :aggregation="aggregation" :missing-strategy="missingStrategy" :max-gap="maxGap" @close="configOpen=false" @apply="applyConfig"/><AnalysisReportDrawer :visible="reportOpen" :result="result" :points="points" :algorithm-label="currentSpec?.label||result?.algorithm||''" @close="reportOpen=false" @ai="agentOpen=true"/><AnalysisAgentDialog :visible="agentOpen" :result="result" :algorithm-label="currentSpec?.label||result?.algorithm||''" @close="agentOpen=false"/></section></main></template>

<style scoped>
*{box-sizing:border-box}.page-content{flex:1;min-width:0;padding:28px 32px;overflow:hidden;color:#172033}.workspace{height:calc(100vh - 56px);display:flex;flex-direction:column;min-height:0}.page-head{margin-bottom:15px;flex:none}.page-head h1{margin:0 0 5px;font-size:24px}.page-head p{margin:0;color:#8492a6;font-size:13px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;flex:1;min-height:0}.main-card{min-height:0;display:flex;flex-direction:column;border:1px solid #e6ebf2;border-radius:14px;background:#fff;box-shadow:0 5px 18px rgba(15,23,42,.045);overflow:hidden}.result-area{position:relative;flex:1;min-height:330px;overflow:hidden}.result-area>:not(.empty){height:100%}.empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#94a3b8}.empty b{color:#475569}.empty p{font-size:12px}.spinner{width:25px;height:25px;margin-bottom:10px;border:3px solid #dbeafe;border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1100px){.layout{grid-template-columns:minmax(0,1fr) 285px}}@media(max-width:760px){.page-content{padding:14px;overflow:auto}.workspace{height:auto}.layout{grid-template-columns:1fr}.main-card{min-height:700px}.result-area{min-height:560px}}
</style>
