<script setup lang="ts">
import { computed } from 'vue'
import type {
  AnalyticsResult,
  AnomalySeriesResult,
  ForecastPointSuccess,
  SelectedAnalysisPoint,
} from '../../api/analytics'

const props = defineProps<{
  result: AnalyticsResult
  points: SelectedAnalysisPoint[]
  algorithmLabel: string
}>()
const emit = defineEmits<{ ai: [] }>()

const analysisLabels = { anomaly: '异常检测', clustering: '聚类分析', forecasting: '趋势预测' }
const modeLabels: Record<string, string> = { per_point: '逐测点独立', joint: '多测点联合' }
const aggregationLabels: Record<string, string> = { mean: '平均值', min: '最小值', max: '最大值', first: '首个值', last: '末尾值' }
const scalingLabels: Record<string, string> = { none: '不缩放', standard: '标准缩放', robust: '稳健缩放' }

const anomaly = computed(() => props.result.analysis_type === 'anomaly' ? props.result.result : null)
const clustering = computed(() => props.result.analysis_type === 'clustering' ? props.result.result : null)
const forecasting = computed(() => props.result.analysis_type === 'forecasting' ? props.result.result : null)
const quality = computed(() => props.result.quality || {})

const pointName = (pointId: string) => props.points.find(point => point.point_id === pointId)?.point_name || pointId
const pointUnit = (pointId: string) => props.points.find(point => point.point_id === pointId)?.point_unit || ''
const pointNames = (pointIds: string[]) => pointIds.map(pointName).join('、')
const number = (value: number | null | undefined, digits = 3) => value == null || !Number.isFinite(value) ? '--' : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits })
const percent = (value: number | null | undefined, digits = 1) => `${number((value ?? 0) * 100, digits)}%`
const intervalText = (seconds: number) => {
  if (seconds < 60) return `${number(seconds, 2)} 秒`
  if (seconds < 3600) return `${number(seconds / 60, 2)} 分钟`
  return `${number(seconds / 3600, 2)} 小时`
}

function anomalyStats(series: AnomalySeriesResult) {
  const assessed = series.risk_scores.filter(value => value != null)
  const anomalyCount = series.labels.filter(Boolean).length
  return {
    anomalyCount,
    ratio: assessed.length ? anomalyCount / assessed.length : 0,
    maxRisk: assessed.length ? Math.max(...assessed as number[]) : 0,
  }
}

function successfulForecast(point: unknown): point is ForecastPointSuccess {
  return Boolean(point && typeof point === 'object' && (point as ForecastPointSuccess).status === 'success')
}

function featureHighlights(cluster: number) {
  return clustering.value?.feature_summaries.find(item => item.cluster === cluster)?.highlights || []
}
</script>

<template>
  <section class="analysis-report">
    <header class="report-heading">
      <span>{{ analysisLabels[result.analysis_type] }}</span>
      <div class="report-method-row">
        <h2>{{ algorithmLabel || result.algorithm }}</h2>
        <button
          type="button"
          class="ai-analysis-button"
          :disabled="!result.ai_context?.available || !result.ai_context.analysis_id"
          :title="result.ai_context?.available ? '让AI进一步解释当前分析报告' : 'AI分析上下文暂不可用'"
          @click="emit('ai')"
        >AI 分析</button>
      </div>
      <p>{{ modeLabels[result.mode] || result.mode }}</p>
    </header>

    <section class="report-section">
      <h3>运行摘要</h3>
      <dl class="summary-grid">
        <div><dt>实际时间范围</dt><dd>{{ result.range.start_time }}<br>至 {{ result.range.actual_end_time }}</dd></div>
        <div><dt>时间桶</dt><dd>{{ result.sampling.actual_sample_count }} 个</dd></div>
        <div><dt>采样间隔</dt><dd>{{ intervalText(result.sampling.interval_seconds) }}</dd></div>
        <div><dt>桶内聚合</dt><dd>{{ aggregationLabels[result.sampling.aggregation] || result.sampling.aggregation }}</dd></div>
      </dl>
      <p v-if="result.range.was_clipped" class="notice">结束时间超过当前时间，已自动裁剪为 {{ result.range.actual_end_time }}</p>
    </section>

    <section v-if="anomaly" class="report-section">
      <h3>异常结果</h3>
      <article v-for="series in anomaly.series" :key="series.point_ids.join('-')" class="result-card">
        <h4>{{ pointNames(series.point_ids) }}</h4>
        <dl class="metric-grid">
          <div><dt>异常数量</dt><dd>{{ anomalyStats(series).anomalyCount }}</dd></div>
          <div><dt>异常比例</dt><dd>{{ percent(anomalyStats(series).ratio) }}</dd></div>
          <div><dt>最高风险</dt><dd>{{ number(anomalyStats(series).maxRisk, 1) }}</dd></div>
          <div><dt>判定阈值</dt><dd>{{ number(series.threshold) }}</dd></div>
          <div><dt>连续区间</dt><dd>{{ series.events.length }}</dd></div>
        </dl>
        <details v-if="series.events.length">
          <summary>查看异常区间</summary>
          <ol class="event-list">
            <li v-for="(event, index) in series.events" :key="`${event.start_time}-${index}`">
              <b>{{ event.start_time }} 至 {{ event.end_time }}</b>
              <span>{{ event.sample_count }} 个异常桶 · 最高风险 {{ number(event.max_score, 1) }}</span>
            </li>
          </ol>
        </details>
      </article>
    </section>

    <section v-if="clustering" class="report-section">
      <h3>聚类结果</h3>
      <dl class="metric-grid top-metrics">
        <div><dt>聚类数</dt><dd>{{ clustering.cluster_count }}</dd></div>
        <div><dt>轮廓系数</dt><dd>{{ number(clustering.silhouette_score) }}</dd></div>
        <div><dt>簇内距离</dt><dd>{{ number(clustering.inertia) }}</dd></div>
      </dl>
      <article v-for="(center, cluster) in clustering.centers" :key="cluster" class="result-card">
        <h4>状态 {{ Number(cluster) + 1 }}</h4>
        <p>{{ clustering.cluster_sizes[Number(cluster)] || 0 }} 个时间桶，占 {{ percent((clustering.cluster_sizes[Number(cluster)] || 0) / Math.max(1, clustering.labels.length)) }}</p>
        <dl class="value-list">
          <div v-for="(value, column) in center" :key="column"><dt>{{ pointName(clustering.point_ids[Number(column)] || '') }}</dt><dd>{{ number(value) }} {{ pointUnit(clustering.point_ids[Number(column)] || '') }}</dd></div>
        </dl>
        <p v-if="featureHighlights(Number(cluster)).length" class="feature-line">主要特征：{{ featureHighlights(Number(cluster)).map(item => `${pointName(item.point_id)}${item.direction === 'high' ? '偏高' : '偏低'}`).join('、') }}</p>
      </article>
      <details v-if="clustering.candidate_scores?.length > 1">
        <summary>查看候选聚类数评分</summary>
        <dl class="value-list candidates">
          <div v-for="item in clustering.candidate_scores" :key="item.cluster_count"><dt>K={{ item.cluster_count }}</dt><dd>轮廓 {{ number(item.silhouette_score) }} · Inertia {{ number(item.inertia) }}</dd></div>
        </dl>
      </details>
    </section>

    <section v-if="forecasting" class="report-section">
      <h3>预测结果</h3>
      <article v-for="(point, index) in forecasting.points" :key="point.point_id" class="result-card" :class="{ failed: point.status === 'failed' }">
        <details :open="index === 0">
          <summary>{{ pointName(point.point_id) }} <em>{{ point.status === 'success' ? '预测成功' : '预测失败' }}</em></summary>
          <template v-if="successfulForecast(point)">
            <dl class="metric-grid forecast-metrics">
              <div><dt>MAE</dt><dd>{{ number(point.metrics.mae) }} {{ pointUnit(point.point_id) }}</dd></div>
              <div><dt>RMSE</dt><dd>{{ number(point.metrics.rmse) }} {{ pointUnit(point.point_id) }}</dd></div>
              <div><dt>sMAPE</dt><dd>{{ number(point.metrics.smape, 2) }}%</dd></div>
              <div><dt>预测步数</dt><dd>{{ point.forecast_values.length }}</dd></div>
            </dl>
            <p v-if="point.forecast_times.length">预测范围：{{ point.forecast_times[0] }} 至 {{ point.forecast_times[point.forecast_times.length - 1] }}</p>
            <p>预测区间：{{ percent(Number(result.parameters.prediction_interval ?? 0.95), 0) }} {{ point.lower && point.upper ? '（已生成）' : '（有效回测残差不足，未生成）' }}</p>
          </template>
          <p v-else class="failure-message">{{ point.message }}</p>
        </details>
      </article>
    </section>

    <section class="report-section">
      <h3>数据质量</h3>
      <dl class="metric-grid quality-grid">
        <div><dt>原始数据</dt><dd>{{ quality.raw_count ?? 0 }}</dd></div>
        <div><dt>有效时间桶</dt><dd>{{ quality.valid_count ?? 0 }} / {{ quality.bucket_count ?? 0 }}</dd></div>
        <div><dt>缺失率</dt><dd>{{ percent(quality.missing_ratio ?? 0) }}</dd></div>
        <div><dt>最大连续缺口</dt><dd>{{ quality.max_consecutive_gap ?? 0 }} 桶</dd></div>
        <div><dt>已插值</dt><dd>{{ quality.interpolated_count ?? 0 }}</dd></div>
        <div><dt>已丢弃</dt><dd>{{ quality.dropped_count ?? 0 }}</dd></div>
      </dl>
      <p v-if="quality.constant_point_ids?.length" class="notice">恒定测点：{{ quality.constant_point_ids.map(pointName).join('、') }}</p>
      <p v-if="quality.low_variance_point_ids?.length" class="notice">低方差测点：{{ quality.low_variance_point_ids.map(pointName).join('、') }}</p>
    </section>

    <section v-if="result.warnings.length" class="report-section">
      <h3>警告（{{ result.warnings.length }}）</h3>
      <article v-for="(warning, index) in result.warnings" :key="`${warning.code}-${warning.point_id}-${index}`" class="warning-card">
        <b>{{ warning.point_id ? `${pointName(warning.point_id)}：` : '' }}{{ warning.message }}</b>
        <small>{{ warning.code }}</small>
      </article>
    </section>

    <details class="technical-details">
      <summary>数据处理详情</summary>
      <dl class="value-list">
        <div><dt>时区</dt><dd>{{ result.timezone }}</dd></div>
        <div><dt>标准化</dt><dd>{{ scalingLabels[String(result.preprocessing.scaling)] || result.preprocessing.scaling || '--' }}</dd></div>
        <div><dt>请求时间桶</dt><dd>{{ result.sampling.requested_sample_count }}</dd></div>
      </dl>
    </details>
  </section>
</template>

<style scoped>
*{box-sizing:border-box}.analysis-report{height:100%;padding:18px;overflow-y:auto;color:#475569;background:#fff}.report-heading{padding:3px 2px 18px}.report-heading span{display:inline-block;padding:5px 9px;border-radius:6px;color:#1d4ed8;background:#eff6ff;font-size:11px;font-weight:700}.report-method-row{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:10px}.report-heading h2{min-width:0;margin:0;color:#172033;font-size:18px;line-height:1.4;overflow-wrap:anywhere}.report-heading p{margin:4px 0 0;color:#94a3b8;font-size:12px;line-height:1.5}.ai-analysis-button{flex:none;height:34px;padding:0 14px;border:1px solid #bfdbfe;border-radius:8px;color:#1d4ed8;background:#eff6ff;font-size:12px;font-weight:700;cursor:pointer}.ai-analysis-button:hover:not(:disabled){border-color:#60a5fa;background:#dbeafe}.ai-analysis-button:disabled{color:#94a3b8;border-color:#e2e8f0;background:#f8fafc;cursor:not-allowed}.report-section{padding:16px 0;border-top:1px solid #edf1f6}.report-section h3{margin:0 0 12px;color:#334155;font-size:14px;line-height:1.4}.summary-grid,.metric-grid,.value-list{margin:0}.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.summary-grid>div:first-child{grid-column:1/-1}.summary-grid>div,.metric-grid>div{min-width:0;padding:10px;border-radius:8px;background:#f8fafc}.summary-grid dt,.metric-grid dt,.value-list dt{color:#8492a6;font-size:11px;line-height:1.45}.summary-grid dd,.metric-grid dd,.value-list dd{margin:4px 0 0;color:#334155;font-size:13px;font-weight:650;line-height:1.55;overflow-wrap:anywhere}.notice{margin:10px 0 0;padding:9px 10px;border-radius:7px;color:#92400e;background:#fffbeb;font-size:12px;line-height:1.6}.result-card{margin:10px 0;padding:13px;border:1px solid #e2e8f0;border-radius:10px;background:#fff}.result-card h4{margin:0 0 10px;color:#334155;font-size:13px;line-height:1.45;overflow-wrap:anywhere}.result-card>p,.result-card details p{margin:9px 0 0;color:#64748b;font-size:12px;line-height:1.6;overflow-wrap:anywhere}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.top-metrics{margin-bottom:12px}.value-list>div{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:8px 0;border-bottom:1px dashed #e2e8f0}.value-list>div:last-child{border-bottom:0}.value-list dt{min-width:0;flex:1;overflow-wrap:anywhere}.value-list dd{max-width:58%;flex:none;text-align:right}.feature-line{padding:9px;border-radius:7px;background:#eff6ff!important;color:#1e40af!important}.result-card.failed{border-color:#fecaca;background:#fffafa}.result-card summary,.analysis-report>details summary{color:#475569;font-size:12px;font-weight:650;line-height:1.5;cursor:pointer}.result-card summary em{float:right;margin-left:8px;color:#16a34a;font-size:11px;font-style:normal}.result-card.failed summary em{color:#dc2626}.event-list{max-height:260px;margin:10px 0 0;padding-left:21px;overflow:auto}.event-list li{margin:9px 0;color:#64748b;font-size:11px;line-height:1.55}.event-list b,.event-list span{display:block;overflow-wrap:anywhere}.event-list b{color:#475569;font-size:12px}.event-list span{margin-top:3px;color:#94a3b8}.forecast-metrics{margin-top:11px}.failure-message{color:#b91c1c!important}.warning-card{display:flex;flex-direction:column;gap:5px;margin:9px 0;padding:11px;border-radius:8px;color:#92400e;background:#fffbeb;font-size:12px;line-height:1.6;overflow-wrap:anywhere}.warning-card small{color:#b08968;font-size:10px;line-height:1.4}.technical-details{margin:0 0 14px;padding:13px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc}.technical-details .value-list{margin-top:10px}.candidates dd{font-size:12px}@media(max-width:560px){.analysis-report{padding:16px}.summary-grid,.metric-grid{grid-template-columns:1fr 1fr}}@media(max-width:380px){.summary-grid,.metric-grid{grid-template-columns:1fr}.summary-grid>div:first-child{grid-column:auto}.report-method-row{align-items:flex-start;flex-direction:column}.ai-analysis-button{align-self:flex-end}}
</style>
