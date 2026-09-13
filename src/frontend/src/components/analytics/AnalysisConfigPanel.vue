<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Aggregation, AlgorithmCatalog, AnalysisType, MissingStrategy } from '../../api/analytics'

export interface AnalysisConfigValue {
  analysisType: AnalysisType
  algorithm: string
  mode: 'per_point' | 'joint'
  parameters: Record<string, unknown>
  aggregation: Aggregation
  missingStrategy: MissingStrategy
  maxGap: number
}

const props=defineProps<{
  visible:boolean
  catalog:AlgorithmCatalog
  analysisType:AnalysisType
  algorithm:string
  mode:'per_point'|'joint'
  parameters:Record<string,unknown>
  aggregation:Aggregation
  missingStrategy:MissingStrategy
  maxGap:number
}>()
const emit=defineEmits<{close:[];apply:[value:AnalysisConfigValue]}>()
const activeTab=ref<'analysis'|'processing'>('analysis')
const draftAnalysisType=ref<AnalysisType>('anomaly')
const draftAlgorithm=ref('')
const draftMode=ref<'per_point'|'joint'>('per_point')
const draftParameters=ref<Record<string,unknown>>({})
const draftAggregation=ref<Aggregation>('mean')
const draftMissingStrategy=ref<MissingStrategy>('interpolate')
const draftMaxGap=ref(3)
const currentSpecs=computed(()=>props.catalog[draftAnalysisType.value]||[])
const current=computed(()=>currentSpecs.value.find(item=>item.name===draftAlgorithm.value))
const analysisTypes:Array<{value:AnalysisType;label:string;description:string}>=[
  {value:'anomaly',label:'异常检测',description:'识别明显偏离正常水平的时间桶'},
  {value:'clustering',label:'聚类分析',description:'发现多测点常见的组合运行状态'},
  {value:'forecasting',label:'趋势预测',description:'根据历史变化粗略预测未来数据'},
]
const parameterHelp:Record<string,string>={
  threshold:'超过该稳健分数的数据会被标记为异常。数值越大，判断越严格，检出的异常通常越少。',
  baseline:'决定异常基线使用整个时间范围，还是随时间移动的局部历史窗口。',
  window_size:'参与滚动基线或移动平均计算的历史时间桶数量；窗口越大，结果通常越平滑。',
  direction:'决定只检测偏高、只检测偏低，还是同时检测两个方向的异常。',
  contamination:'告诉孤立森林大致有多少数据可能异常；自动模式由模型自行判断，也可填写具体比例。',
  n_estimators:'孤立森林构建的随机树数量；数量越多结果通常越稳定，但计算时间也会增加。',
  cluster_count:'需要识别的运行状态数量；自动模式会比较多个候选数量并选择轮廓系数较高的结果。',
  max_iter:'K-Means调整聚类中心时允许的最大迭代次数，用于限制计算量并保证收敛。',
  horizon:'向未来预测多少个时间桶；每个桶的实际时长由查询时间范围与时间桶数量计算。',
  backtest_ratio:'从历史数据末尾留出多少比例进行模拟预测，用于估算模型误差。',
  prediction_interval:'预测上下界希望覆盖真实值的概率，例如0.95表示95%预测区间。',
  training_window:'线性趋势使用最近多少个有效时间桶拟合；自动模式使用全部有效历史数据。',
  trend:'决定Holt-Winters是否单独建模持续上升或下降的趋势。',
  seasonal:'决定Holt-Winters是否建模周期性重复波动。',
  seasonal_periods:'一个完整周期包含多少个时间桶，例如小时数据按天重复时可设为24。',
  lags:'自回归预测时参考前面多少个时间桶；阶数越大需要的训练数据越多。',
}

watch(()=>props.visible,visible=>{
  if(!visible)return
  activeTab.value='analysis'
  draftAnalysisType.value=props.analysisType
  draftAlgorithm.value=props.algorithm
  draftMode.value=props.mode
  draftParameters.value={...props.parameters}
  draftAggregation.value=props.aggregation
  draftMissingStrategy.value=props.missingStrategy
  draftMaxGap.value=props.maxGap
},{immediate:true})

const visibleParameter=(item:any)=>!item.visible_when||Object.entries(item.visible_when).every(([key,value])=>draftParameters.value[key]===value)
const optionLabel=(item:any,value:string)=>item.option_labels?.[value]||value
const displayValue=(item:any)=>draftParameters.value[item.name]==='auto'?'自动':draftParameters.value[item.name]
const rangeText=(item:any)=>item.minimum!==undefined&&item.maximum!==undefined?`${item.minimum} ～ ${item.maximum}`:item.default==='auto'?'自动或自定义数值':'按算法要求填写'
const defaultText=(item:any)=>item.default==='auto'?'自动':String(item.default)
const overlayStyle={position:'fixed',inset:'0',zIndex:'9999',display:'flex',alignItems:'center',justifyContent:'center'} as const
const modalStyle={position:'relative',width:'760px',maxWidth:'calc(100vw - 32px)',maxHeight:'calc(100vh - 32px)',display:'flex',flexDirection:'column'} as const

function changeAlgorithm(value:string){
  const spec=currentSpecs.value.find(item=>item.name===value)
  if(!spec)return
  draftAlgorithm.value=value
  draftMode.value=spec.modes[0]||'per_point'
  draftParameters.value=Object.fromEntries(spec.parameters.map(item=>[item.name,item.default]))
}
function changeAnalysisType(value:AnalysisType){
  draftAnalysisType.value=value
  const spec=props.catalog[value]?.[0]
  if(spec)changeAlgorithm(spec.name)
}
function setParam(name:string,value:unknown,type:string){
  const normalized=value==='自动'?'auto':type==='integer'||type==='number'?Number(value):value
  draftParameters.value={...draftParameters.value,[name]:normalized}
}
function apply(){
  emit('apply',{analysisType:draftAnalysisType.value,algorithm:draftAlgorithm.value,mode:draftMode.value,parameters:{...draftParameters.value},aggregation:draftAggregation.value,missingStrategy:draftMissingStrategy.value,maxGap:draftMaxGap.value})
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="analytics-config-overlay" :style="overlayStyle" @click.self="emit('close')">
      <section class="analytics-config-modal" :style="modalStyle" role="dialog" aria-modal="true" aria-label="分析参数配置">
        <header><div><h2>分析方案配置</h2><p>在一个位置完成分析类型、算法参数和数据处理设置</p></div><button type="button" aria-label="关闭" @click="emit('close')">×</button></header>
        <nav class="analytics-config-tabs"><button type="button" :class="{active:activeTab==='analysis'}" @click="activeTab='analysis'"><b>分析方法</b><small>{{analysisTypes.find(item=>item.value===draftAnalysisType)?.label}} · {{current?.label}}</small></button><button type="button" :class="{active:activeTab==='processing'}" @click="activeTab='processing'"><b>数据处理</b><small>聚合、缺失值与填补范围</small></button></nav>
        <div class="analytics-config-body">
          <template v-if="activeTab==='analysis'">
          <section class="analytics-config-group analytics-config-type-group">
            <div class="analytics-config-group-title"><h3>选择分析类型</h3><p>先确定要回答的问题，再选择具体算法和参数。</p></div>
            <div class="analytics-config-type-options"><button v-for="item in analysisTypes" :key="item.value" type="button" :class="{active:draftAnalysisType===item.value}" @click="changeAnalysisType(item.value)"><b>{{item.label}}</b><small>{{item.description}}</small></button></div>
          </section>

          <section class="analytics-config-group">
            <div class="analytics-config-group-title"><h3>算法设置</h3><p>{{current?.description}}</p></div>
            <div class="analytics-config-field-grid">
              <label><span>具体算法</span><select :value="draftAlgorithm" @change="changeAlgorithm(($event.target as HTMLSelectElement).value)"><option v-for="item in currentSpecs" :key="item.name" :value="item.name">{{item.label}}</option></select><small>{{current?.description}}</small></label>
              <label v-if="current&&current.modes.length>1"><span>检测模式</span><select v-model="draftMode"><option v-for="item in current.modes" :key="item" :value="item">{{item==='joint'?'多测点联合':'逐测点独立'}}</option></select><small>联合模式同时考虑多个测点的组合状态；逐点模式分别计算。</small></label>
            </div>
          </section>

          <section class="analytics-config-group">
            <div class="analytics-config-group-title"><h3>算法参数</h3><p>参数保留默认值即可完成通用的粗略分析。</p></div>
            <div class="analytics-config-parameter-list">
              <label v-for="item in current?.parameters||[]" v-show="visibleParameter(item)" :key="item.name" class="analytics-config-parameter-row">
                <span class="analytics-config-parameter-info"><b>{{item.label||item.name}}</b><small>{{item.description||parameterHelp[item.name]||`配置“${item.label||item.name}”在本次计算中的取值。`}}</small><em>范围：{{rangeText(item)}}　默认：{{defaultText(item)}}</em></span>
                <select v-if="item.type==='select'" :value="draftParameters[item.name]" @change="setParam(item.name,($event.target as HTMLSelectElement).value,item.type)"><option v-for="option in item.options" :key="option" :value="option">{{optionLabel(item,option)}}</option></select>
                <input v-else :type="item.type==='text'?'text':'number'" :min="item.minimum" :max="item.maximum" :value="displayValue(item)" :placeholder="item.default==='auto'?'自动或输入数值':''" @input="setParam(item.name,($event.target as HTMLInputElement).value,item.type)">
              </label>
            </div>
          </section>
          </template>

          <template v-else>
          <section class="analytics-config-group analytics-config-processing-intro"><div><b>数据预处理独立于算法</b><p>这里的设置会先把原始测量数据整理成等间隔样本，再交给所选算法。它们适用于所有分析类型，但不会修改或回写数据库中的原始数据。</p></div></section>
          <section class="analytics-config-group">
            <div class="analytics-config-group-title"><h3>时间对齐与缺失处理</h3><p>建议通用分析保留默认的“平均值 + 线性插值”。</p></div>
            <div class="analytics-config-field-grid">
              <label><span>时间桶聚合</span><select v-model="draftAggregation"><option value="mean">平均值</option><option value="min">最小值</option><option value="max">最大值</option><option value="first">首个值</option><option value="last">末尾值</option></select><small>同一个时间桶内存在多条数据时，用所选方式合并为一个值。</small></label>
              <label><span>缺失数据处理</span><select v-model="draftMissingStrategy"><option value="interpolate">线性插值</option><option value="drop">删除缺失样本</option><option value="forward_fill">使用最近值</option><option value="reject">存在缺失时拒绝</option></select><small>决定算法计算时如何处理空时间桶；图表仍使用原始值并显示断线。</small></label>
              <label v-if="draftMissingStrategy==='interpolate'||draftMissingStrategy==='forward_fill'"><span>最大填补桶数</span><input v-model.number="draftMaxGap" type="number" min="1" max="20"><small>只填补不超过该长度的连续缺口，较长缺口仍保持缺失。</small></label>
            </div>
          </section>
          </template>
        </div>
        <footer><button type="button" @click="emit('close')">取消</button><button type="button" class="primary" @click="apply">应用配置</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<style>
.analytics-config-overlay,.analytics-config-overlay *{box-sizing:border-box}.analytics-config-overlay{padding:16px;background:rgba(15,23,42,.48);backdrop-filter:blur(2px)}.analytics-config-modal{border:1px solid rgba(255,255,255,.75);border-radius:16px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.28);overflow:hidden}.analytics-config-modal header{display:flex;align-items:flex-start;justify-content:space-between;flex:none;padding:20px 22px 16px}.analytics-config-modal h2{margin:0 0 5px;color:#0f172a;font-size:19px}.analytics-config-modal header p,.analytics-config-group-title p{margin:0;color:#94a3b8;font-size:11px}.analytics-config-modal header button{padding:0;border:0;color:#64748b;background:none;font-size:24px;cursor:pointer}.analytics-config-tabs{display:grid;grid-template-columns:1fr 1fr;gap:6px;flex:none;padding:0 22px 12px;border-bottom:1px solid #e2e8f0}.analytics-config-tabs button{display:flex;flex-direction:column;align-items:flex-start;gap:3px;padding:10px 13px;border:1px solid transparent;border-radius:9px;color:#64748b;background:#f8fafc;cursor:pointer}.analytics-config-tabs button.active{border-color:#bfdbfe;color:#1d4ed8;background:#eff6ff}.analytics-config-tabs b{font-size:12px}.analytics-config-tabs small{color:#94a3b8;font-size:9px}.analytics-config-body{flex:1;min-height:0;display:flex;flex-direction:column;gap:14px;padding:18px 22px;overflow-y:auto}.analytics-config-group{flex:none;padding:15px;border:1px solid #e2e8f0;border-radius:12px;background:#fbfdff}.analytics-config-group-title{margin-bottom:13px}.analytics-config-group-title h3{margin:0 0 4px;color:#334155;font-size:14px}.analytics-config-type-options{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.analytics-config-type-options button{display:flex;flex-direction:column;align-items:flex-start;gap:5px;padding:12px;border:1px solid #e2e8f0;border-radius:9px;color:#475569;background:#fff;text-align:left;cursor:pointer}.analytics-config-type-options button.active{border-color:#60a5fa;color:#1d4ed8;background:#eff6ff;box-shadow:0 0 0 2px rgba(59,130,246,.08)}.analytics-config-type-options b{font-size:12px}.analytics-config-type-options small{color:#94a3b8;font-size:9px;line-height:1.45}.analytics-config-field-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}.analytics-config-field-grid label{display:flex;flex-direction:column;gap:6px;color:#475569;font-size:12px;font-weight:600}.analytics-config-field-grid small{color:#94a3b8;font-size:10px;font-weight:400;line-height:1.45}.analytics-config-modal input,.analytics-config-modal select{width:100%;height:38px;padding:0 11px;border:1px solid #cbd5e1;border-radius:8px;color:#334155;background:#fff;outline:none}.analytics-config-modal input:focus,.analytics-config-modal select:focus{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.11)}.analytics-config-parameter-list{display:flex;flex-direction:column;gap:8px}.analytics-config-parameter-row{display:grid;grid-template-columns:minmax(0,1fr) 190px;align-items:center;gap:18px;padding:11px 12px;border-radius:9px;background:#f8fafc}.analytics-config-parameter-info{display:flex;flex-direction:column;gap:4px}.analytics-config-parameter-info b{color:#334155;font-size:12px}.analytics-config-parameter-info small{color:#64748b;font-size:11px;line-height:1.5}.analytics-config-parameter-info em{color:#94a3b8;font-size:10px;font-style:normal}.analytics-config-processing-intro{border-color:#bfdbfe;color:#1e3a8a;background:#eff6ff}.analytics-config-processing-intro b{font-size:13px}.analytics-config-processing-intro p{margin:6px 0 0;color:#64748b;font-size:11px;line-height:1.6}.analytics-config-modal footer{display:flex;justify-content:flex-end;gap:8px;flex:none;padding:14px 22px;border-top:1px solid #e2e8f0;background:#fff}.analytics-config-modal footer button{height:36px;padding:0 18px;border:0;border-radius:8px;color:#475569;background:#f1f5f9;cursor:pointer}.analytics-config-modal footer .primary{color:#fff;background:#3b82f6}@media(max-width:650px){.analytics-config-overlay{padding:8px!important}.analytics-config-type-options,.analytics-config-field-grid,.analytics-config-parameter-row{grid-template-columns:1fr}.analytics-config-parameter-row{gap:9px}.analytics-config-modal{max-height:calc(100vh - 16px)!important}}
</style>
