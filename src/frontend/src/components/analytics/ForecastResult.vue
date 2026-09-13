<script setup lang="ts">
import { computed,ref,watch } from 'vue'
import type { ForecastingAnalysisResult, SelectedAnalysisPoint } from '../../api/analytics'
import { buildGapAwareData } from '../../utils/timeSeriesGaps'
import AnalysisChart from './AnalysisChart.vue'
const props=defineProps<{result:ForecastingAnalysisResult;points:SelectedAnalysisPoint[]}>();const selected=ref('')
const pointName=(pointId:string)=>props.points.find(point=>point.point_id===pointId)?.point_name||pointId
watch(()=>props.result,()=>{selected.value=props.result.points.find(item=>item.status==='success')?.point_id||''},{immediate:true,deep:true})
const point=computed(()=>props.result.points.find(item=>item.point_id===selected.value))
const option=computed<any>(()=>{
  const p=point.value
  if(!p||p.status!=='success')return{}
  const name=pointName(p.point_id)
  const lower=p.lower
  const upper=p.upper
  return{tooltip:{trigger:'axis'},legend:{top:8},grid:{left:55,right:25,top:48,bottom:45},xAxis:{type:'time'},yAxis:{type:'value',scale:true},dataZoom:[{type:'inside'},{type:'slider'}],series:[{name:`${name}（历史）`,type:'line',showSymbol:false,connectNulls:false,data:buildGapAwareData(p.history_times,p.history_values)},{name:`${name}（回测）`,type:'line',showSymbol:false,lineStyle:{type:'dashed'},data:p.backtest_times.map((t:string,i:number)=>[t,p.backtest_values[i]])},{name:`${name}（预测）`,type:'line',showSymbol:false,data:p.forecast_times.map((t:string,i:number)=>[t,p.forecast_values[i]])},{name:'预测区间下界',type:'line',showSymbol:false,lineStyle:{opacity:.35},data:lower?p.forecast_times.map((t:string,i:number)=>[t,lower[i]]):[]},{name:'预测区间上界',type:'line',showSymbol:false,lineStyle:{opacity:.35},data:upper?p.forecast_times.map((t:string,i:number)=>[t,upper[i]]):[]}]}
})
</script>
<template><div class="forecast-chart"><label class="point-switcher"><span>显示测点</span><select v-model="selected"><option v-for="item in result.points" :key="item.point_id" :value="item.point_id" :disabled="item.status!=='success'">{{pointName(item.point_id)}}{{item.status==='failed'?'（预测失败）':''}}</option></select></label><div class="forecast-canvas"><AnalysisChart v-if="point?.status==='success'" :option="option"/><div v-else class="failed-message">暂无可显示的预测曲线</div></div></div></template>
<style scoped>.forecast-chart{width:100%;height:100%;min-height:330px;display:flex;flex-direction:column}.point-switcher{height:44px;display:flex;align-items:center;gap:8px;flex:none;padding:6px 16px;border-bottom:1px solid #edf1f6;color:#64748b;font-size:10px}.point-switcher select{height:31px;min-width:190px;padding:0 9px;border:1px solid #dbe3ee;border-radius:7px;color:#334155;background:#fff}.forecast-canvas{flex:1;min-height:0}.failed-message{height:100%;display:grid;place-items:center;color:#b91c1c}</style>
