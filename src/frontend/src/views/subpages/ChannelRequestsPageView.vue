<script setup lang="ts">
	import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
	import { useRoute, useRouter } from 'vue-router'
	import { menuConfig, isMenuGroup } from '../../config/menu'
	import { fetchHttpChannels, fetchMqttChannels, type HttpChannelListItem, type MqttChannelListItem } from '../../api/channel'
	import { createRequestV2, deleteRequestV2, editRequestTimeV2, editRequestV2, fetchRequestDetailV2, fetchRequestPageV2, testRequestV2, toggleRequestV2, type RequestListItemV2, type RequestPayloadV2, type RequestProtocol } from '../../api/request'
	import ConfirmModal from '../modals/ConfirmModal.vue'
	import JsonTreeViewer from '../modals/asset/JsonTreeViewer.vue'
	import HeaderTableEditor from '../../components/form/HeaderTableEditor.vue'
	import JsonObjectEditor from '../../components/form/JsonObjectEditor.vue'
	
	const router=useRouter(),route=useRoute();const siblings=computed(()=>{for(const e of menuConfig)if(isMenuGroup(e)&&e.children.some(c=>c.route===route.path))return e.children;return[]})
	const rows=ref<RequestListItemV2[]>([]),loading=ref(false),error=ref(''),page=ref(1),pageSize=ref(10),total=ref(0),tableArea=ref<HTMLElement|null>(null);const pages=computed(()=>Math.max(1,Math.ceil(total.value/pageSize.value)))
	const filters=reactive({name:'',type:'' as ''|RequestProtocol,status:'' as ''|'true'|'false'});let observer:ResizeObserver|null=null,resizeTimer:ReturnType<typeof setTimeout>|null=null
	async function load(target=1){loading.value=true;error.value='';page.value=target;try{const r=await fetchRequestPageV2(target,pageSize.value,{name:filters.name.trim()||undefined,type:filters.type||undefined,status:filters.status===''?undefined:filters.status==='true'});rows.value=r.data;total.value=r.total}catch(e:any){error.value=e?.message||'加载请求失败';rows.value=[];total.value=0}finally{loading.value=false}}
	function resetFilters(){Object.assign(filters,{name:'',type:'',status:''});load(1)}function fmt(value:string){const d=new Date(value);return Number.isNaN(d.getTime())?value:d.toLocaleString('zh-CN',{hour12:false})}
	function adjustPageSize(){if(!tableArea.value)return;const next=Math.max(3,Math.min(50,Math.floor((tableArea.value.getBoundingClientRect().height-43)/49)));if(next!==pageSize.value){pageSize.value=next;load(1)}}function scheduleResize(){if(resizeTimer)clearTimeout(resizeTimer);resizeTimer=setTimeout(adjustPageSize,120)}
	
	const mqttChannels=ref<MqttChannelListItem[]>([]),httpChannels=ref<HttpChannelListItem[]>([]),channelsLoading=ref(false)
	async function loadChannels(){if(mqttChannels.value.length&&httpChannels.value.length)return;channelsLoading.value=true;try{const[m,h]=await Promise.all([fetchMqttChannels(1,100,{}),fetchHttpChannels(1,100,{})]);mqttChannels.value=m.data;httpChannels.value=h.data;const mqttPages=Math.ceil(m.total/100),httpPages=Math.ceil(h.total/100);const[mqttRest,httpRest]=await Promise.all([Promise.all(Array.from({length:Math.max(0,mqttPages-1)},(_,i)=>fetchMqttChannels(i+2,100,{}))),Promise.all(Array.from({length:Math.max(0,httpPages-1)},(_,i)=>fetchHttpChannels(i+2,100,{})))]);mqttChannels.value.push(...mqttRest.flatMap(item=>item.data));httpChannels.value.push(...httpRest.flatMap(item=>item.data))}catch(e:any){formError.value=e?.message||'加载通道列表失败'}finally{channelsLoading.value=false}}
	const modal=ref(false),mode=ref<'create'|'edit'>('create'),editId=ref(''),saving=ref(false),detailLoading=ref(false),formError=ref('')
	const form=reactive({name:'',type:'mqtt' as RequestProtocol,channel_id:'',interval_seconds:60,time_json_path:'',time_format:'',mqtt_topic:'',http_method:'GET' as 'GET'|'POST',http_path:'',http_header:'{}',http_params:'{}',http_body:'{}'})
	const availableChannels=computed(()=>form.type==='mqtt'?mqttChannels.value.map(c=>({id:c.channel_mqtt_id,label:`${c.broker_host}:${c.broker_port}`})):httpChannels.value.map(c=>({id:c.channel_http_id,label:c.base_url})))
	function resetForm(){Object.assign(form,{name:'',type:'mqtt',channel_id:'',interval_seconds:60,time_json_path:'',time_format:'',mqtt_topic:'',http_method:'GET',http_path:'',http_header:'{}',http_params:'{}',http_body:'{}'})}
	async function openCreate(){mode.value='create';editId.value='';formError.value='';resetForm();modal.value=true;await loadChannels()}
	async function openEdit(row:RequestListItemV2){mode.value='edit';editId.value=row.request_id;formError.value='';resetForm();modal.value=true;detailLoading.value=true;try{await loadChannels();const d=await fetchRequestDetailV2(row.request_id);Object.assign(form,{name:d.name,type:d.type,channel_id:d.channel_id,interval_seconds:d.interval_seconds,time_json_path:d.time_json_path||'',time_format:d.time_format||'',mqtt_topic:d.mqtt_topic||'',http_method:d.http_method||'GET',http_path:d.http_path||'',http_header:JSON.stringify(d.http_header||{},null,2),http_params:JSON.stringify(d.http_params||{},null,2),http_body:JSON.stringify(d.http_body||{},null,2)})}catch(e:any){formError.value=e?.message||'加载详情失败'}finally{detailLoading.value=false}}
	watch(()=>form.type,()=>{if(mode.value==='create')form.channel_id=''})
	watch(()=>form.http_method,m=>{if(m==='GET')form.http_body='{}';else form.http_params='{}'})
	function parseObject(text:string,label:string){let value:any;try{value=JSON.parse(text||'{}')}catch{throw new Error(`${label}必须是有效的 JSON 对象`)}if(!value||Array.isArray(value)||typeof value!=='object')throw new Error(`${label}必须是 JSON 对象`);return value as Record<string,unknown>}
	function buildPayload():RequestPayloadV2{if(!form.name.trim())throw new Error('请输入 Request 名称');if(!form.channel_id)throw new Error('请选择通道');if(Number(form.interval_seconds)<=0)throw new Error('执行或入库周期必须大于 0');const base:any={name:form.name.trim(),type:form.type,channel_id:form.channel_id,interval_seconds:Number(form.interval_seconds),time_json_path:form.time_json_path.trim()||null,time_format:form.time_format.trim()||null};if(form.type==='mqtt'){if(!form.mqtt_topic.trim())throw new Error('请输入 MQTT 订阅主题');base.mqtt_topic=form.mqtt_topic.trim()}else{if(!form.http_path.trim())throw new Error('请输入 HTTP 请求路径');base.http_method=form.http_method;base.http_path=form.http_path.trim();base.http_header=parseObject(form.http_header,'独享 Header');base.http_params=form.http_method==='GET'?parseObject(form.http_params,'查询参数'):null;base.http_body=form.http_method==='POST'?parseObject(form.http_body,'请求体'):null}return base}
	async function save(){formError.value='';try{const payload=buildPayload();saving.value=true;if(mode.value==='create')await createRequestV2(payload);else await editRequestV2(editId.value,payload);modal.value=false;await load(page.value)}catch(e:any){formError.value=e?.message||'保存失败'}finally{saving.value=false}}
	const toggleTarget=ref<RequestListItemV2|null>(null),toggleLoading=ref(false),toggleError=ref('');async function confirmToggle(){if(!toggleTarget.value)return;toggleLoading.value=true;toggleError.value='';try{await toggleRequestV2(toggleTarget.value.request_id);toggleTarget.value=null;await load(page.value)}catch(e:any){toggleError.value=e?.message||'切换状态失败'}finally{toggleLoading.value=false}}
	const deleteTarget=ref<RequestListItemV2|null>(null),deleting=ref(false),deleteError=ref('');async function confirmDelete(){if(!deleteTarget.value)return;deleting.value=true;deleteError.value='';try{await deleteRequestV2(deleteTarget.value.request_id);deleteTarget.value=null;await load(page.value)}catch(e:any){deleteError.value=e?.message||'删除失败'}finally{deleting.value=false}}
	const testTarget=ref<RequestListItemV2|null>(null),testTimeout=ref(10),testLoading=ref(false),testError=ref(''),testResult=ref<any>(null),testTimePath=ref(''),testTimeFormat=ref(''),timeValidation=ref<{ok:boolean;message:string;value?:unknown}>({ok:false,message:''}),timeSaving=ref(false)
	async function openTest(row:RequestListItemV2){testTarget.value=row;testTimeout.value=10;testError.value='';testResult.value=null;timeValidation.value={ok:false,message:''};try{const d=await fetchRequestDetailV2(row.request_id);testTimePath.value=d.time_json_path||'';testTimeFormat.value=d.time_format||''}catch(e:any){testError.value=e?.message||'加载时间配置失败'}}
	async function runTest(){if(!testTarget.value)return;testLoading.value=true;testError.value='';testResult.value=null;timeValidation.value={ok:false,message:''};try{testResult.value=await testRequestV2(testTarget.value.request_id,Number(testTimeout.value))}catch(e:any){testError.value=e?.message||'测试失败'}finally{testLoading.value=false}}
	function extractPath(data:any,path:string){if(!path.trim())return undefined;const clean=path.trim().replace(/^\$\.?/,'');if(!clean)return data;const parts=clean.replace(/\[(\d+)\]/g,'.$1').split('.').filter(Boolean);let value=data;for(const key of parts){if(value==null||!(key in Object(value)))throw new Error(`找不到字段：${key}`);value=value[key]}return value}
	function validateTime(){if(!testResult.value?.data){timeValidation.value={ok:false,message:'当前测试没有返回数据，无法校验时间字段'};return}if(!testTimePath.value.trim()&&!testTimeFormat.value.trim()){timeValidation.value={ok:true,message:'时间配置为空，将使用系统时间'};return}if(!testTimePath.value.trim()||!testTimeFormat.value.trim()){timeValidation.value={ok:false,message:'时间字段路径和时间格式需要同时填写'};return}try{const value=extractPath(testResult.value.data,testTimePath.value);const escaped=testTimeFormat.value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace('yyyy','(\\d{4})').replace('MM','(\\d{2})').replace('dd','(\\d{2})').replace('hh','(\\d{2})').replace('mm','(\\d{2})').replace('ss','(\\d{2})');if(!new RegExp(`^${escaped}$`).test(String(value)))throw new Error('提取结果与时间格式不匹配');timeValidation.value={ok:true,message:'时间字段提取和格式校验通过',value}}catch(e:any){timeValidation.value={ok:false,message:e?.message||'时间配置校验失败'}}}
	const canSaveTime=computed(()=>!testTimePath.value.trim()&&!testTimeFormat.value.trim()||timeValidation.value.ok)
	watch([testTimePath,testTimeFormat],()=>{timeValidation.value={ok:false,message:''}})
	async function saveTime(){if(!testTarget.value||!canSaveTime.value)return;timeSaving.value=true;testError.value='';try{await editRequestTimeV2(testTarget.value.request_id,testTimePath.value.trim()||null,testTimeFormat.value.trim()||null);testTarget.value=null;await load(page.value)}catch(e:any){testError.value=e?.message||'保存时间配置失败'}finally{timeSaving.value=false}}
	onMounted(async()=>{await nextTick();adjustPageSize();if(!loading.value)await load(1);observer=new ResizeObserver(scheduleResize);if(tableArea.value)observer.observe(tableArea.value);window.addEventListener('resize',scheduleResize)})
	onBeforeUnmount(()=>{observer?.disconnect();window.removeEventListener('resize',scheduleResize);if(resizeTimer)clearTimeout(resizeTimer)})
</script>

<template>
	<main class="page-content">
		<section class="workspace">
			<nav v-if="siblings.length>1" class="sibling-tabs"><button v-for="item in siblings" :key="item.route" :class="{active:route.path===item.route}" @click="router.push(item.route)">{{item.name}}</button></nav>
			<section class="card">
				<form class="toolbar" @submit.prevent="load(1)"><label>名称<input v-model="filters.name" placeholder="模糊搜索"></label><label>协议<select v-model="filters.type">
							<option value="">全部</option>
							<option value="mqtt">MQTT</option>
							<option value="http">HTTP</option>
						</select></label><label>状态<select v-model="filters.status">
							<option value="">全部</option>
							<option value="true">已启用</option>
							<option value="false">已停用</option>
						</select></label>
					<div class="toolbar-actions">
                        <button type="button" @click="resetFilters">重置</button>
                        <button class="primary">查询</button>
                        <button type="button" class="create inline-create" @click="openCreate">新增</button>
                    </div>
				</form>
				<div v-if="error" class="alert">{{error}}<button @click="load(page)">重试</button></div>
				<div ref="tableArea" class="table-area">
					<table>
						<thead>
							<tr>
								<th>Request 名称</th>
								<th>协议</th>
								<th>状态</th>
								<th>创建时间</th>
								<th class="operation">操作</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in rows" :key="row.request_id">
								<td><strong>{{row.name}}</strong></td>
								<td><span class="protocol" :class="row.type">{{row.type.toUpperCase()}}</span></td>
								<td><span class="status" :class="{on:row.status}"><i></i>{{row.status?'已启用':'已停用'}}</span></td>
								<td>{{fmt(row.created_at)}}</td>
								<td class="actions"><button :disabled="row.status" @click="openEdit(row)">编辑</button><button @click="openTest(row)">测试</button><button :class="row.status?'stop':'start'" @click="toggleTarget=row">{{row.status?'停用':'启用'}}</button><button class="danger"
										:disabled="row.status" @click="deleteTarget=row">删除</button></td>
							</tr>
						</tbody>
					</table>
					<div v-if="loading" class="state">加载中...</div>
					<div v-else-if="!rows.length" class="state">暂无 Request</div>
				</div>
				<footer v-if="total>0" class="pagination"><span class="pagination-info">共 {{total}} 条 · {{pages}} 页</span>
					<div class="page-buttons"><button class="page-btn" :disabled="page<=1||loading" @click="load(1)" title="首页">«</button><button class="page-btn" :disabled="page<=1||loading" @click="load(page-1)" title="上一页">‹</button><button v-for="p in pages" :key="p" class="page-btn"
							:class="{active:p===page}" @click="load(p)">{{p}}</button><button class="page-btn" :disabled="page>=pages||loading" @click="load(page+1)" title="下一页">›</button><button class="page-btn" :disabled="page>=pages||loading" @click="load(pages)" title="末页">»</button></div>
				</footer>
			</section>
		</section>
		<div v-if="modal" class="overlay" @click.self="modal=false">
			<form class="modal request-modal" @submit.prevent="save">
				<header>
					<div>
						<h2>{{mode==='create'?'新增':'编辑'}} Request</h2>
						<p>连接参数由通道统一管理，这里配置采集任务自身参数</p>
					</div><button type="button" @click="modal=false">×</button>
				</header>
				<div class="modal-body">
					<div v-if="detailLoading" class="loading-mask">加载详情...</div>
					<section>
						<h3>基础配置</h3>
						<div class="grid"><label>Request 名称 <span>*</span><input v-model="form.name" maxlength="20"></label><label>协议类型 <span>*</span><select v-model="form.type">
									<option value="mqtt">MQTT</option>
									<option value="http">HTTP</option>
								</select></label><label class="wide">绑定通道 <span>*</span><select v-model="form.channel_id" :disabled="channelsLoading">
									<option value="">{{channelsLoading?'加载通道中...':'请选择通道'}}</option>
									<option v-for="item in availableChannels" :key="item.id" :value="item.id">{{item.label}}</option>
								</select></label><label v-if="form.type==='mqtt'">订阅主题 <span>*</span><input v-model="form.mqtt_topic" maxlength="30" placeholder="building/one/measurements"></label><label>
								<div class="field-title">执行/入库周期（秒） <small>{{form.type==='mqtt'?'仅控制 SQL 入库周期，实时状态仍逐条更新':'HTTP 定时请求间隔'}}</small></div><input v-model.number="form.interval_seconds" type="number" min="1">
							</label></div>
					</section>
					<section>
						<h3>{{form.type==='mqtt'?'MQTT 订阅配置':'HTTP 请求配置'}}</h3>
						<div v-if="form.type==='mqtt'" class="grid mqtt-old"><label class="wide">订阅主题 <span>*</span><input v-model="form.mqtt_topic" maxlength="30" placeholder="building/one/measurements"></label></div>
						<div v-else class="grid"><label>请求方法<select v-model="form.http_method">
									<option value="GET">GET</option>
									<option value="POST">POST</option>
								</select></label><label>请求路径 <span>*</span><input v-model="form.http_path" maxlength="100" placeholder="/measurements"></label>
							<HeaderTableEditor v-model="form.http_header" class="wide" title="独享 Header" />
							<JsonObjectEditor v-if="form.http_method==='GET'" v-model="form.http_params" class="wide" title="查询参数（JSON）" :rows="4" />
							<JsonObjectEditor v-else v-model="form.http_body" class="wide" title="JSON 请求体" :rows="4" />
						</div>
					</section>
					<section>
						<h3>测量时间解析</h3>
						<p class="section-tip">留空时使用系统时间；清空后保存会向后端提交 null。</p>
						<div class="grid"><label>时间字段 JSONPath<input v-model="form.time_json_path" maxlength="200" placeholder="$.time"></label><label>时间格式<input v-model="form.time_format" maxlength="50" placeholder="yyyy-MM-dd hh:mm:ss"><small>小写 hh 表示 24 小时制</small></label></div>
					</section>
					<div v-if="formError" class="form-error">{{formError}}</div>
				</div>
				<footer><button type="button" @click="modal=false">取消</button><button class="primary" :disabled="saving||detailLoading">{{saving?'保存中...':'保存 Request'}}</button></footer>
			</form>
		</div>
		<div v-if="testTarget" class="overlay" @click.self="testTarget=null">
			<section class="modal test-modal">
				<header>
					<div>
						<h2>连通性测试</h2>
						<p>{{testTarget.name}} · 测试不会写入数据或改变状态</p>
					</div><button @click="testTarget=null">×</button>
				</header>
				<div class="test-body"><label>测试超时（秒）<input v-model.number="testTimeout" type="number" min="1" step="1"></label><button class="primary" :disabled="testLoading" @click="runTest">{{testLoading?'测试中...':'开始测试'}}</button>
					<div v-if="testResult" class="time-config wide">
						<div class="time-config-head">
							<div><b>测量时间解析</b><small>从本次测试数据中提取并校验</small></div><button type="button" @click="validateTime">校验提取</button>
						</div>
						<div class="time-fields"><label>时间字段 JSONPath<input v-model="testTimePath" maxlength="200" placeholder="$.time"></label><label>时间格式<input v-model="testTimeFormat" maxlength="50" placeholder="yyyy-MM-dd hh:mm:ss"></label></div>
						<div v-if="timeValidation.message" class="validation-result" :class="{ok:timeValidation.ok}">{{timeValidation.message}}<span v-if="timeValidation.value!==undefined">提取值：{{timeValidation.value}}</span></div>
						<div class="time-actions"><span>两项均留空时使用系统时间</span><button type="button" class="primary" :disabled="!canSaveTime||timeSaving" @click="saveTime">{{timeSaving?'保存中...':'保存时间配置'}}</button></div>
					</div>
					<div v-if="testError" class="form-error wide">{{testError}}</div>
					<div v-if="testResult" class="result wide">
						<header><b>{{testResult.ok?'连接成功':'连接失败'}}</b><span>{{testResult.message||'已获取响应数据'}}</span></header>
						<JsonTreeViewer v-if="testResult.data!==null" :data="testResult.data" />
					</div>
				</div>
			</section>
		</div>
		<ConfirmModal :visible="!!toggleTarget" :title="toggleTarget?.status?'停用 Request':'启用 Request'" :message="toggleTarget?.status?'停用后将停止数据采集，是否继续？':'启用时将校验通道配置并启动采集，是否继续？'" :confirm-text="toggleTarget?.status?'停用':'启用'" :danger="!!toggleTarget?.status" :loading="toggleLoading"
			:error="toggleError" @confirm="confirmToggle" @cancel="toggleTarget=null" />
		<ConfirmModal :visible="!!deleteTarget" title="删除 Request" :message="`确定删除「${deleteTarget?.name||''}」吗？关联终端的 Request 绑定将被清空。`" confirm-text="删除" :danger="true" :loading="deleting" :error="deleteError" @confirm="confirmDelete" @cancel="deleteTarget=null" />
	</main>
</template>

<style scoped>
	* {
		box-sizing: border-box
	}

	.page-content {
		flex: 1;
		min-width: 0;
		padding: 20px 28px;
		overflow: hidden;
		color: #172033
	}

	.workspace {
		height: calc(100vh - 40px);
		min-height: 0;
		display: flex;
		flex-direction: column
	}

	.sibling-tabs {
		display: flex;
		flex: none;
		gap: 4px;
		margin-bottom: 16px;
		padding: 4px;
		border-radius: 14px;
		background: #fff;
		box-shadow: 0 4px 16px rgba(15, 23, 42, .05)
	}

	.sibling-tabs button {
		padding: 9px 18px;
		border: 0;
		border-radius: 10px;
		color: #64748b;
		background: transparent;
		cursor: pointer
	}

	.sibling-tabs button.active {
		color: #fff;
		background: #3b82f6
	}

	.card {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		border-radius: 16px;
		background: #fff;
		box-shadow: 0 4px 16px rgba(15, 23, 42, .06);
		overflow: hidden
	}

	.card>header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid #e2e8f0
	}

	.card h2 {
		margin: 0 0 4px;
		font-size: 18px
	}

	.card header p {
		margin: 0;
		color: #94a3b8;
		font-size: 11px
	}

	.create {
		height: 36px;
		padding: 0 16px;
		border: 0;
		border-radius: 8px;
		color: #fff;
		background: #10b981;
		font-weight: 600;
		cursor: pointer
	}

	.toolbar {
		display: flex;
		align-items: end;
		gap: 10px;
		padding: 12px 20px;
		border-bottom: 1px solid #e2e8f0;
		background: #fbfcfe
	}

	.toolbar label {
		display: flex;
		flex-direction: column;
		gap: 5px;
		color: #64748b;
		font-size: 10px
	}

	.toolbar input,
	.toolbar select {
		width: 160px;
		height: 34px;
		padding: 0 9px;
		border: 1px solid #cbd5e1;
		border-radius: 7px;
		background: #fff
	}

	.toolbar-actions {
		display: flex;
		gap: 6px;
		margin-left: auto
	}

	.toolbar-actions button {
		height: 34px;
		padding: 0 14px;
		border: 0;
		border-radius: 7px;
		color: #475569;
		background: #f1f5f9
	}

	.primary {
		color: #fff !important;
		background: #3b82f6 !important
	}

	.alert {
		display: flex;
		justify-content: space-between;
		margin: 9px 20px 0;
		padding: 8px 11px;
		border-radius: 7px;
		color: #b91c1c;
		background: #fef2f2;
		font-size: 11px
	}

	.alert button {
		border: 0;
		color: #2563eb;
		background: none
	}

	.table-area {
		position: relative;
		flex: 1;
		min-height: 0;
		margin: 11px 20px 0;
		overflow: hidden;
		border: 1px solid #e2e8f0;
		border-radius: 9px
	}

	table {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed
	}

	th,
	td {
		height: 48px;
		padding: 0 13px;
		border-bottom: 1px solid #edf1f6;
		text-align: left;
		font-size: 12px
	}

	th {
		height: 42px;
		color: #64748b;
		background: #f8fafc
	}

	.operation {
		width: 280px
	}

	.protocol {
		padding: 4px 8px;
		border-radius: 5px;
		font-size: 9px
	}

	.protocol.mqtt {
		color: #6d28d9;
		background: #ede9fe
	}

	.protocol.http {
		color: #0369a1;
		background: #e0f2fe
	}

	.status {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: #64748b
	}

	.status i {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #94a3b8
	}

	.status.on {
		color: #047857
	}

	.status.on i {
		background: #10b981
	}

	.actions {
		display: flex;
		gap: 5px
	}

	.actions button {
		padding: 5px 9px;
		border: 0;
		border-radius: 6px;
		color: #2563eb;
		background: #eff6ff
	}

	.actions button:disabled {
		opacity: .4
	}

	.actions .start {
		color: #047857;
		background: #d1fae5
	}

	.actions .stop {
		color: #b45309;
		background: #fef3c7
	}

	.actions .danger {
		color: #dc2626;
		background: #fef2f2
	}

	.state {
		position: absolute;
		inset: 43px 0 0;
		display: grid;
		place-items: center;
		color: #94a3b8;
		background: rgba(255, 255, 255, .87)
	}

	.pagination {
		height: 55px;
		flex: none;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 20px;
		color: #94a3b8;
		font-size: 11px
	}

	.pagination div {
		display: flex;
		align-items: center;
		gap: 9px
	}

	.pagination button {
		height: 29px;
		padding: 0 10px;
		border: 1px solid #e2e8f0;
		border-radius: 6px;
		background: #fff;
		color: #475569
	}

	.pagination button:disabled {
		opacity: .4
	}

	.overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		display: grid;
		place-items: center;
		background: rgba(15, 23, 42, .48)
	}

	.modal {
		width: 760px;
		max-width: 95vw;
		max-height: 94vh;
		display: flex;
		flex-direction: column;
		border-radius: 15px;
		background: #fff;
		box-shadow: 0 24px 70px rgba(15, 23, 42, .25);
		overflow: hidden
	}

	.modal>header {
		display: flex;
		justify-content: space-between;
		padding: 18px 22px;
		border-bottom: 1px solid #e2e8f0
	}

	.modal h2 {
		margin: 0 0 4px;
		font-size: 18px
	}

	.modal header p {
		margin: 0;
		color: #94a3b8;
		font-size: 10px
	}

	.modal header>button {
		border: 0;
		background: none;
		font-size: 23px
	}

	.modal-body {
		position: relative;
		padding: 17px 20px;
		overflow-y: auto
	}

	.modal-body section {
		margin-bottom: 12px;
		padding: 14px;
		border: 1px solid #e2e8f0;
		border-radius: 9px
	}

	.modal-body h3 {
		margin: 0 0 11px;
		font-size: 13px
	}

	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 11px
	}

	.grid label {
		display: flex;
		flex-direction: column;
		gap: 5px;
		color: #475569;
		font-size: 11px;
		font-weight: 600
	}

	.grid label>span {
		color: #dc2626
	}

	.grid input,
	.grid select,
	.grid textarea,
	.test-body input {
		width: 100%;
		padding: 8px 9px;
		border: 1px solid #cbd5e1;
		border-radius: 7px;
		background: #fff;
		outline: none
	}

	.grid textarea {
		resize: vertical;
		font: 11px/1.5 ui-monospace, monospace
	}

	.grid small {
		color: #94a3b8;
		font-size: 9px;
		font-weight: 400
	}

	.wide {
		grid-column: 1/-1
	}

	.section-tip {
		margin: -5px 0 11px;
		color: #94a3b8;
		font-size: 10px
	}

	.form-error {
		padding: 9px 11px;
		border-radius: 7px;
		color: #b91c1c;
		background: #fef2f2;
		font-size: 11px
	}

	.loading-mask {
		position: absolute;
		inset: 0;
		z-index: 2;
		display: grid;
		place-items: center;
		background: rgba(255, 255, 255, .82)
	}

	.modal>footer {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		padding: 13px 20px;
		border-top: 1px solid #e2e8f0
	}

	.modal>footer button {
		height: 35px;
		padding: 0 16px;
		border: 0;
		border-radius: 7px;
		color: #475569;
		background: #f1f5f9
	}

	.test-modal {
		width: 680px
	}

	.test-body {
		display: grid;
		grid-template-columns: 1fr 130px;
		align-items: end;
		gap: 10px;
		padding: 18px 20px;
		overflow: auto
	}

	.test-body label {
		display: flex;
		flex-direction: column;
		gap: 5px;
		color: #475569;
		font-size: 11px
	}

	.test-body>button {
		height: 35px;
		border: 0;
		border-radius: 7px
	}

	.result {
		margin-top: 5px;
		border: 1px solid #d1fae5;
		border-radius: 9px;
		overflow: hidden
	}

	.result>header {
		display: flex;
		justify-content: space-between;
		padding: 10px 12px;
		color: #047857;
		background: #ecfdf5;
		font-size: 11px
	}

	@media(max-width:750px) {
		.page-content {
			padding: 14px;
			overflow: auto
		}

		.workspace {
			height: auto
		}

		.toolbar {
			flex-wrap: wrap
		}

		.toolbar-actions {
			margin-left: 0
		}

		.grid {
			grid-template-columns: 1fr
		}

		.wide {
			grid-column: auto
		}

		.operation {
			width: 245px
		}
	}

	.pagination {
		border-top: 1px solid #edf1f6
	}

	.pagination button {
		min-width: 68px;
		background: #fff;
		transition: .15s
	}

	.pagination button:hover:not(:disabled) {
		border-color: #93c5fd;
		color: #2563eb;
		background: #eff6ff
	}

	.actions button {
		min-width: 52px;
		height: 30px;
		padding: 0 9px;
		border: 1px solid #dbe3ee;
		background: #fff;
		transition: .15s
	}

	.actions button:hover:not(:disabled) {
		border-color: #93c5fd;
		color: #1d4ed8;
		background: #eff6ff
	}

	.actions .start {
		border-color: #a7f3d0
	}

	.actions .stop {
		border-color: #fde68a
	}

	.actions .danger {
		border-color: #fecaca
	}

	.modal {
		border: 1px solid rgba(255, 255, 255, .7);
		border-radius: 18px
	}

	.modal>header {
		position: relative;
		padding: 22px 25px;
		background: linear-gradient(135deg, #f8fbff, #fff)
	}

	.modal>header:before {
		content: '';
		position: absolute;
		left: 0;
		top: 20px;
		bottom: 20px;
		width: 4px;
		border-radius: 0 4px 4px 0;
		background: #3b82f6
	}

	.modal h2 {
		font-size: 20px;
		color: #0f172a
	}

	.modal header p {
		font-size: 12px
	}

	.modal header>button {
		width: 34px;
		height: 34px;
		border-radius: 9px;
		background: #f1f5f9;
		color: #64748b
	}

	.modal-body {
		padding: 22px 24px;
		background: #f8fafc
	}

	.modal-body section {
		margin-bottom: 16px;
		padding: 18px;
		border-color: #e5eaf1;
		border-radius: 12px;
		background: #fff;
		box-shadow: 0 2px 7px rgba(15, 23, 42, .025)
	}

	.modal-body h3 {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 15px;
		color: #1e293b;
		font-size: 14px
	}

	.modal-body h3:before {
		content: '';
		width: 4px;
		height: 15px;
		border-radius: 4px;
		background: #3b82f6
	}

	.grid {
		gap: 14px
	}

	.grid label {
		gap: 7px;
		color: #334155;
		font-size: 12px
	}

	.grid input,
	.grid select,
	.grid textarea,
	.test-body input {
		min-height: 41px;
		padding: 10px 11px;
		border-color: #d8e0eb;
		border-radius: 9px
	}

	.grid input:focus,
	.grid select:focus,
	.grid textarea:focus,
	.test-body input:focus {
		border-color: #60a5fa;
		box-shadow: 0 0 0 3px rgba(59, 130, 246, .12)
	}

	.grid textarea {
		resize: none
	}

	.modal>footer {
		padding: 16px 24px;
		background: #fff
	}

	.modal>footer button {
		min-width: 88px;
		height: 38px;
		border: 1px solid #e2e8f0
	}

	.modal>footer .primary {
		border-color: #3b82f6;
		box-shadow: 0 3px 8px rgba(59, 130, 246, .2)
	}

	.test-body {
		padding: 22px 24px;
		background: #f8fafc
	}

	.operation {
		text-align: center
	}

	.actions {
		height: 48px;
		align-items: center;
		justify-content: center
	}

	.pagination {
		justify-content: flex-end;
		gap: 4px;
		height: 55px
	}

	.pagination-info {
		margin-right: 12px;
		font-size: 13px
	}

	.page-buttons {
		display: flex;
		gap: 4px
	}

	.pagination .page-btn {
		min-width: 34px;
		width: auto;
		height: 34px;
		padding: 0 8px;
		display: grid;
		place-items: center;
		border: 1px solid #e2e8f0;
		border-radius: 6px;
		background: #fff;
		color: #475569;
		font-size: 13px
	}

	.pagination .page-btn:hover:not(:disabled) {
		border-color: #94a3b8;
		background: #f1f5f9
	}

	.pagination .page-btn.active {
		border-color: #3b82f6;
		color: #fff;
		background: #3b82f6
	}

	.toolbar-actions .inline-create {
		color: #fff;
		background: #10b981
	}

	.toolbar-actions .inline-create:hover {
		color: #fff;
		background: #059669
	}

	.request-modal .modal-body>section {
		margin: 0 0 15px;
		padding: 0;
		border: 0;
		background: transparent;
		box-shadow: none
	}

	.request-modal .modal-body>section>h3 {
		display: none
	}

	.request-modal .modal-body>section:nth-of-type(3) {
		display: none
	}

	.request-modal .mqtt-old {
		display: none
	}

	.request-modal .grid label {
		display: block;
		color: #334155;
		font-size: 12px;
		font-weight: 600
	}

	.request-modal .grid label>input,
	.request-modal .grid label>select,
	.request-modal .grid label>textarea {
		display: block;
		margin-top: 7px
	}

	.request-modal .grid label>span {
		display: inline;
		color: #dc2626
	}

	.request-modal .field-title {
		display: flex;
		align-items: center;
		gap: 6px
	}

	.request-modal .field-title small {
		color: #94a3b8;
		font-size: 10px;
		font-weight: 400
	}

	.time-config {
		margin-top: 8px;
		padding: 15px;
		border: 1px solid #bfdbfe;
		border-radius: 10px;
		background: #f8fbff
	}

	.time-config-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 12px
	}

	.time-config-head>div {
		display: flex;
		flex-direction: column;
		gap: 3px
	}

	.time-config-head b {
		color: #1e293b;
		font-size: 13px
	}

	.time-config-head small {
		color: #94a3b8;
		font-size: 10px
	}

	.time-config-head button {
		height: 32px;
		padding: 0 12px;
		border: 1px solid #93c5fd;
		border-radius: 7px;
		color: #2563eb;
		background: #fff
	}

	.time-fields {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px
	}

	.time-fields label {
		display: flex;
		flex-direction: column;
		gap: 6px;
		color: #475569;
		font-size: 11px
	}

	.time-fields input {
		height: 38px;
		padding: 0 10px;
		border: 1px solid #cbd5e1;
		border-radius: 8px
	}

	.validation-result {
		display: flex;
		justify-content: space-between;
		margin-top: 10px;
		padding: 9px 11px;
		border-radius: 7px;
		color: #b91c1c;
		background: #fef2f2;
		font-size: 10px
	}

	.validation-result.ok {
		color: #047857;
		background: #ecfdf5
	}

	.time-actions {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 11px
	}

	.time-actions>span {
		color: #94a3b8;
		font-size: 10px
	}

	.time-actions button {
		height: 34px;
		padding: 0 14px;
		border: 0;
		border-radius: 7px
	}

	.time-actions button:disabled {
		opacity: .45
	}

	@media(max-width:700px) {
		.time-fields {
			grid-template-columns: 1fr
		}
	}

	.test-modal {
		width: 980px
	}

	.test-body {
		grid-template-columns: minmax(0, 1fr) 360px;
		grid-template-rows: auto minmax(0, 1fr);
		align-items: start;
		gap: 14px;
		min-height: 430px
	}

	.test-body>label:first-child {
		grid-column: 1;
		grid-row: 1;
		padding-right: 145px
	}

	.test-body>button {
		grid-column: 1;
		grid-row: 1;
		justify-self: end;
		width: 130px;
		align-self: end
	}

	.test-body>.time-config {
		grid-column: 2;
		grid-row: 1/3;
		margin: 0;
		height: 100%;
		align-self: stretch
	}

	.test-body>.form-error {
		grid-column: 1;
		grid-row: 2;
		margin: 0
	}

	.test-body>.result {
		grid-column: 1;
		grid-row: 2;
		margin: 0;
		max-height: 360px;
		overflow: auto
	}

	.time-fields {
		grid-template-columns: 1fr
	}

	.time-actions {
		align-items: flex-start;
		flex-direction: column;
		gap: 10px
	}

	.time-actions button {
		width: 100%
	}

	@media(max-width:850px) {
		.test-modal {
			width: 95vw
		}

		.test-body {
			display: flex;
			flex-direction: column;
			min-height: 0
		}

		.test-body>label:first-child {
			width: 100%;
			padding-right: 0
		}

		.test-body>button {
			width: 100%
		}

		.test-body>.time-config,
		.test-body>.form-error,
		.test-body>.result {
			width: 100%;
			height: auto
		}
	}
</style>