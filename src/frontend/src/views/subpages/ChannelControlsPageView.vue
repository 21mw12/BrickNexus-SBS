<script setup lang="ts">
import{computed,nextTick,onBeforeUnmount,onMounted,reactive,ref,watch}from'vue'
import{useRoute,useRouter}from'vue-router'
import{menuConfig,isMenuGroup}from'../../config/menu'
import{fetchAssetTree,sortAssetTreeForDisplay,type AssetTreeNode}from'../../api/asset'
import{fetchHttpChannels,fetchMqttChannels,type HttpChannelListItem,type MqttChannelListItem}from'../../api/channel'
import{createControl,deleteControl,editControl,executeControl,fetchControlDetail,fetchControlPage,toggleControl,type ControlAssetType,type ControlListItem,type ControlPayload,type ControlProtocol}from'../../api/control'
import ConfirmModal from'../modals/ConfirmModal.vue'
import JsonTreeViewer from'../modals/asset/JsonTreeViewer.vue'
import HeaderTableEditor from'../../components/form/HeaderTableEditor.vue'
import JsonObjectEditor from'../../components/form/JsonObjectEditor.vue'
const router=useRouter(),route=useRoute(),siblings=computed(()=>{for(const e of menuConfig)if(isMenuGroup(e)&&e.children.some(c=>c.route===route.path))return e.children;return[]})
const rows=ref<ControlListItem[]>([]),loading=ref(false),error=ref(''),page=ref(1),pageSize=ref(10),total=ref(0),tableArea=ref<HTMLElement|null>(null),pages=computed(()=>Math.max(1,Math.ceil(total.value/pageSize.value)));const filters=reactive({name:'',type:''as''|ControlProtocol,status:''as''|'true'|'false'});let observer:ResizeObserver|null=null,timer:ReturnType<typeof setTimeout>|null=null
async function load(target=1){loading.value=true;error.value='';page.value=target;try{const r=await fetchControlPage(target,pageSize.value,{name:filters.name.trim()||undefined,type:filters.type||undefined,status:filters.status===''?undefined:filters.status==='true'});rows.value=r.data;total.value=r.total}catch(e:any){error.value=e?.message||'加载控制失败';rows.value=[];total.value=0}finally{loading.value=false}}
function resetFilters(){Object.assign(filters,{name:'',type:'',status:''});load(1)}function fmt(v:string){const d=new Date(v);return Number.isNaN(d.getTime())?v:d.toLocaleString('zh-CN',{hour12:false})}function resize(){if(!tableArea.value)return;const n=Math.max(3,Math.min(50,Math.floor((tableArea.value.getBoundingClientRect().height-43)/49)));if(n!==pageSize.value){pageSize.value=n;load(1)}}function schedule(){if(timer)clearTimeout(timer);timer=setTimeout(resize,120)}
const mqttChannels=ref<MqttChannelListItem[]>([]),httpChannels=ref<HttpChannelListItem[]>([]),assets=ref<AssetTreeNode[]>([]),resourcesLoading=ref(false)
type SelectableAsset={id:string;name:string;path:string;type:ControlAssetType}
const controlAssets=computed(()=>{const out:SelectableAsset[]=[];function visit(nodes:AssetTreeNode[],parents:string[],depth:number){for(const node of nodes){const path=[...parents,node.name];const explicit=node.asset_type||node.type;const inferred=depth===3?'terminal':depth>=4?'sensor':'';const type=explicit||inferred;if(type==='terminal'||type==='sensor')out.push({id:node.asset_id,name:node.name,path:parents.join(' / '),type});if(node.sub_assets?.length)visit(node.sub_assets,path,depth+1)}}visit(assets.value,[],0);return out})
async function loadResources(){if(assets.value.length&&mqttChannels.value.length&&httpChannels.value.length)return;resourcesLoading.value=true;try{const[m,h,a]=await Promise.all([fetchMqttChannels(1,100,{}),fetchHttpChannels(1,100,{}),fetchAssetTree()]);mqttChannels.value=m.data;httpChannels.value=h.data;assets.value=sortAssetTreeForDisplay(a);const mp=Math.ceil(m.total/100),hp=Math.ceil(h.total/100);const[mr,hr]=await Promise.all([Promise.all(Array.from({length:Math.max(0,mp-1)},(_,i)=>fetchMqttChannels(i+2,100,{}))),Promise.all(Array.from({length:Math.max(0,hp-1)},(_,i)=>fetchHttpChannels(i+2,100,{})))]);mqttChannels.value.push(...mr.flatMap(x=>x.data));httpChannels.value.push(...hr.flatMap(x=>x.data))}catch(e:any){formError.value=e?.message||'加载通道或传感器失败'}finally{resourcesLoading.value=false}}
const modal=ref(false),mode=ref<'create'|'edit'>('create'),editId=ref(''),saving=ref(false),detailLoading=ref(false),formError=ref('');const form=reactive({name:'',type:'mqtt'as ControlProtocol,channel_id:'',asset_type:'sensor'as ControlAssetType,asset_id:'',mqtt_topic:'',mqtt_retained:false,mqtt_payload:'',http_method:'POST'as'GET'|'POST',http_path:'',http_header:'{}',http_params:'{}',http_body:'{}'});const channels=computed(()=>form.type==='mqtt'?mqttChannels.value.map(x=>({id:x.channel_mqtt_id,label:`${x.broker_host}:${x.broker_port}`})):httpChannels.value.map(x=>({id:x.channel_http_id,label:x.base_url})))
const assetSearch=ref('');const filteredAssets=computed(()=>{const candidates=controlAssets.value.filter(item=>item.type===form.asset_type);const key=assetSearch.value.trim().toLocaleLowerCase();if(!key)return candidates;return candidates.filter(item=>`${item.path} ${item.name} ${item.id}`.toLocaleLowerCase().includes(key))});const selectedAsset=computed(()=>controlAssets.value.find(item=>item.id===form.asset_id));const mqttPayloadState=computed(()=>{const text=form.mqtt_payload.trim();if(!text)return{kind:'idle',text:'可填写 JSON 或普通文本'};if(!text.startsWith('{')&&!text.startsWith('['))return{kind:'plain',text:'普通文本，将按原内容发送'};try{JSON.parse(text);return{kind:'valid',text:'JSON 格式正确'}}catch{return{kind:'invalid',text:'JSON 格式不正确，请检查括号、引号或逗号'}}})
function changeAssetType(){form.asset_id='';assetSearch.value=''}function resetForm(){assetSearch.value='';Object.assign(form,{name:'',type:'mqtt',channel_id:'',asset_type:'sensor',asset_id:'',mqtt_topic:'',mqtt_retained:false,mqtt_payload:'',http_method:'POST',http_path:'',http_header:'{}',http_params:'{}',http_body:'{}'})}async function openCreate(){mode.value='create';editId.value='';formError.value='';resetForm();modal.value=true;await loadResources()}async function openEdit(row:ControlListItem){mode.value='edit';editId.value=row.control_id;formError.value='';resetForm();modal.value=true;detailLoading.value=true;try{await loadResources();const d=await fetchControlDetail(row.control_id);Object.assign(form,{name:d.name,type:d.type,channel_id:d.channel_id,asset_type:d.asset_type||d.asset?.asset_type||'sensor',asset_id:d.asset_id||d.asset?.asset_id||'',mqtt_topic:d.mqtt_topic||'',mqtt_retained:d.mqtt_retained||false,mqtt_payload:d.mqtt_payload||'',http_method:d.http_method||'POST',http_path:d.http_path||'',http_header:JSON.stringify(d.http_header||{},null,2),http_params:JSON.stringify(d.http_params||{},null,2),http_body:JSON.stringify(d.http_body||{},null,2)});assetSearch.value=d.asset?.name||''}catch(e:any){formError.value=e?.message||'加载详情失败'}finally{detailLoading.value=false}}
watch(()=>form.type,()=>{if(mode.value==='create')form.channel_id='' });watch(()=>form.http_method,m=>{if(m==='GET')form.http_body='{}';else form.http_params='{}'})
function obj(text:string,label:string){let v:any;try{v=JSON.parse(text||'{}')}catch{throw new Error(`${label}必须是有效 JSON 对象`)}if(!v||Array.isArray(v)||typeof v!=='object')throw new Error(`${label}必须是 JSON 对象`);return v}
function payload():ControlPayload{if(!form.name.trim())throw new Error('请输入 Control 名称');if(!form.channel_id)throw new Error('请选择通道');if(!form.asset_id)throw new Error(`请选择被控${form.asset_type==='terminal'?'终端':'传感器'}`);const p:any={name:form.name.trim(),type:form.type,channel_id:form.channel_id,asset_type:form.asset_type,asset_id:form.asset_id};if(form.type==='mqtt'){if(!form.mqtt_topic.trim())throw new Error('请输入 MQTT 发布主题');if(!form.mqtt_payload)throw new Error('请输入 MQTT 发送内容');if(mqttPayloadState.value.kind==='invalid')throw new Error('发送内容看起来是 JSON，但格式不合法');Object.assign(p,{mqtt_topic:form.mqtt_topic.trim(),mqtt_retained:form.mqtt_retained,mqtt_payload:form.mqtt_payload})}else{if(!form.http_path.trim())throw new Error('请输入 HTTP 请求路径');Object.assign(p,{http_method:form.http_method,http_path:form.http_path.trim(),http_header:obj(form.http_header,'独享 Header'),http_params:form.http_method==='GET'?obj(form.http_params,'查询参数'):null,http_body:form.http_method==='POST'?obj(form.http_body,'请求体'):null})}return p}
function assetTypeLabel(type:ControlAssetType){return type==='terminal'?'终端':'传感器'}function rowAssetName(row:ControlListItem){return row.asset?.name||row.asset_name||row.sensor_name||row.asset_id||'—'}
async function save(){formError.value='';try{const p=payload();saving.value=true;if(mode.value==='create')await createControl(p);else await editControl(editId.value,p);modal.value=false;await load(page.value)}catch(e:any){formError.value=e?.message||'保存失败'}finally{saving.value=false}}
const toggleTarget=ref<ControlListItem|null>(null),toggleLoading=ref(false),toggleError=ref('');async function confirmToggle(){if(!toggleTarget.value)return;toggleLoading.value=true;toggleError.value='';try{await toggleControl(toggleTarget.value.control_id);toggleTarget.value=null;await load(page.value)}catch(e:any){toggleError.value=e?.message||'切换失败'}finally{toggleLoading.value=false}}
const deleteTarget=ref<ControlListItem|null>(null),deleting=ref(false),deleteError=ref('');async function confirmDelete(){if(!deleteTarget.value)return;deleting.value=true;deleteError.value='';try{await deleteControl(deleteTarget.value.control_id);deleteTarget.value=null;await load(page.value)}catch(e:any){deleteError.value=e?.message||'删除失败'}finally{deleting.value=false}}
const executeTarget=ref<ControlListItem|null>(null),executing=ref(false),executeError=ref(''),executeResult=ref<any>(null);function askExecute(row:ControlListItem){executeTarget.value=row;executeError.value='';executeResult.value=null}async function runExecute(){if(!executeTarget.value)return;executing.value=true;executeError.value='';try{executeResult.value=await executeControl(executeTarget.value.control_id)}catch(e:any){executeError.value=e?.message||'执行失败'}finally{executing.value=false}}
onMounted(async()=>{await nextTick();resize();if(!loading.value)await load();observer=new ResizeObserver(schedule);if(tableArea.value)observer.observe(tableArea.value);window.addEventListener('resize',schedule)});onBeforeUnmount(()=>{observer?.disconnect();window.removeEventListener('resize',schedule);if(timer)clearTimeout(timer)})
</script>

<template>
	<main class="page-content">
		<section class="workspace">
			<nav class="sibling-tabs"><button v-for="s in siblings" :key="s.route" :class="{active:route.path===s.route}" @click="router.push(s.route)">{{s.name}}</button></nav>
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
                        <button type="button" class="create" @click="openCreate">新增</button>
                    </div>
				</form>
				<div v-if="error" class="alert">{{error}}</div>
				<div ref="tableArea" class="table-area">
					<table>
						<thead>
							<tr>
								<th>Control 名称</th>
								<th>协议</th>
									<th class="asset-type-col">资产类型</th>
									<th>绑定资产</th>
								<th>状态</th>
								<th>创建时间</th>
								<th class="operation">操作</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="r in rows" :key="r.control_id">
								<td><strong>{{r.name}}</strong></td>
								<td><span class="protocol" :class="r.type">{{r.type.toUpperCase()}}</span></td>
									<td><span class="asset-type" :class="r.asset_type">{{assetTypeLabel(r.asset_type)}}</span></td>
									<td><strong>{{rowAssetName(r)}}</strong></td>
								<td><span class="status" :class="{on:r.status}"><i></i>{{r.status?'已启用':'已停用'}}</span></td>
								<td>{{fmt(r.created_at)}}</td>
								<td class="actions"><button :disabled="r.status" @click="openEdit(r)">编辑</button><button class="execute" :disabled="!r.status" @click="askExecute(r)">执行</button><button :class="r.status?'stop':'start'" @click="toggleTarget=r">{{r.status?'停用':'启用'}}</button><button
										class="danger" :disabled="r.status" @click="deleteTarget=r">删除</button></td>
							</tr>
						</tbody>
					</table>
					<div v-if="loading" class="state">加载中...</div>
					<div v-else-if="!rows.length" class="state">暂无 Control</div>
				</div>
				<footer v-if="total>0" class="pagination"><span class="pagination-info">共 {{total}} 条 · {{pages}} 页</span>
					<div class="page-buttons"><button class="page-btn" :disabled="page<=1||loading" @click="load(1)" title="首页">«</button><button class="page-btn" :disabled="page<=1||loading" @click="load(page-1)" title="上一页">‹</button><button v-for="p in pages" :key="p" class="page-btn"
							:class="{active:p===page}" @click="load(p)">{{p}}</button><button class="page-btn" :disabled="page>=pages||loading" @click="load(page+1)" title="下一页">›</button><button class="page-btn" :disabled="page>=pages||loading" @click="load(pages)" title="末页">»</button></div>
				</footer>
			</section>
		</section>
		<div v-if="modal" class="overlay" @click.self="modal=false">
			<form class="modal" @submit.prevent="save">
				<header>
					<div>
								<h2>{{mode==='create'?'新增':'编辑'}} Control</h2>
								<p>绑定终端或传感器，并配置固定控制指令</p>
					</div><button type="button" @click="modal=false">×</button>
				</header>
				<div class="modal-body">
					<div v-if="detailLoading" class="mask">加载详情...</div>
					<section>
						<h3>基础配置</h3>
						<div class="grid"><label><span class="field-title">Control 名称 <b>*</b></span><input v-model="form.name" maxlength="30"></label><label><span class="field-title">协议类型</span><select v-model="form.type">
									<option value="mqtt">MQTT</option>
									<option value="http">HTTP</option>
								</select></label><label class="wide"><span class="field-title">绑定通道 <b>*</b></span><select v-model="form.channel_id" :disabled="resourcesLoading">
									<option value="">请选择通道</option>
									<option v-for="c in channels" :key="c.id" :value="c.id">{{c.label}}</option>
									</select></label><label><span class="field-title">被控资产类型 <b>*</b></span><select v-model="form.asset_type" @change="changeAssetType">
										<option value="terminal">终端</option>
										<option value="sensor">传感器</option>
									</select></label><label class="wide sensor-picker"><span class="field-title">选择{{form.asset_type==='terminal'?'终端':'传感器'}} <b>*</b><small>需要对应资产的操作权限，启用时资产必须处于使用状态</small></span><input v-model="assetSearch" type="search" :placeholder="`输入${form.asset_type==='terminal'?'终端':'传感器'}名称、路径或 ID 搜索`"><select v-model="form.asset_id" :disabled="resourcesLoading"
										size="5">
										<option v-if="selectedAsset&&selectedAsset.type===form.asset_type&&!filteredAssets.some(item=>item.id===selectedAsset?.id)" :value="selectedAsset.id">{{selectedAsset.path}} / {{selectedAsset.name}}</option>
										<option v-for="item in filteredAssets" :key="item.id" :value="item.id">{{item.path}} / {{item.name}}</option>
									</select></label></div>
					</section>
					<section>
						<h3>{{form.type==='mqtt'?'MQTT 发布指令':'HTTP 控制请求'}}</h3>
						<div v-if="form.type==='mqtt'" class="grid"><label><span class="field-title">发布主题 <b>*</b></span><input v-model="form.mqtt_topic" maxlength="30"></label><label class="check"><input v-model="form.mqtt_retained" type="checkbox">发送保留消息</label><label class="wide"><span
									class="field-title">发送内容 <b>*</b><small :class="['payload-hint',mqttPayloadState.kind]">{{mqttPayloadState.text}}</small></span><textarea v-model="form.mqtt_payload" :class="{invalid:mqttPayloadState.kind==='invalid'}" rows="6"
									placeholder='{"enabled":true}'></textarea></label></div>
						<div v-else class="grid"><label><span class="field-title">请求方法</span><select v-model="form.http_method">
									<option value="GET">GET</option>
									<option value="POST">POST</option>
								</select></label><label><span class="field-title">请求路径 <b>*</b></span><input v-model="form.http_path" maxlength="100"></label>
							<HeaderTableEditor v-model="form.http_header" class="wide" title="独享 Header" />
							<JsonObjectEditor v-if="form.http_method==='GET'" v-model="form.http_params" class="wide" title="查询参数（JSON）" :rows="5" />
							<JsonObjectEditor v-else v-model="form.http_body" class="wide" title="JSON 请求体" :rows="5" />
						</div>
					</section>
					<div v-if="formError" class="form-error">{{formError}}</div>
				</div>
				<footer><button type="button" @click="modal=false">取消</button><button class="primary" :disabled="saving||detailLoading">{{saving?'保存中...':'保存 Control'}}</button></footer>
			</form>
		</div>
		<div v-if="executeTarget" class="overlay" @click.self="executeTarget=null">
			<section class="modal execute-modal">
				<header>
					<div>
						<h2>立即执行 Control</h2>
						<p>{{executeTarget.name}} · 将发送已保存的控制内容</p>
					</div><button @click="executeTarget=null">×</button>
				</header>
				<div class="execute-body">
					<div v-if="!executeResult" class="execute-warning">执行后会立即向设备发送控制指令，且不能临时修改 payload 或参数。请确认现场设备状态安全。</div>
					<div v-if="executeError" class="form-error">{{executeError}}</div>
					<div v-if="executeResult" class="result">
						<header><b>执行成功</b><span>{{fmt(executeResult.executed_at)}}</span></header>
						<JsonTreeViewer :data="executeResult.result" :depth="0" />
					</div>
				</div>
				<footer><button @click="executeTarget=null">关闭</button><button v-if="!executeResult" class="primary" :disabled="executing" @click="runExecute">{{executing?'执行中...':'确认执行'}}</button></footer>
			</section>
		</div>
		<ConfirmModal :visible="!!toggleTarget" :title="toggleTarget?.status?'停用 Control':'启用 Control'" :message="toggleTarget?.status?'停用后将不能执行该控制，是否继续？':'启用只开放执行能力，不会自动发送控制指令。是否继续？'" :confirm-text="toggleTarget?.status?'停用':'启用'" :danger="!!toggleTarget?.status" :loading="toggleLoading"
			:error="toggleError" @confirm="confirmToggle" @cancel="toggleTarget=null" />
		<ConfirmModal :visible="!!deleteTarget" title="删除 Control" :message="`确定删除「${deleteTarget?.name||''}」吗？`" confirm-text="删除" :danger="true" :loading="deleting" :error="deleteError" @confirm="confirmDelete" @cancel="deleteTarget=null" />
	</main>
</template>

<style scoped>
*{box-sizing:border-box}.page-content{flex:1;min-width:0;padding:20px 28px;overflow:hidden;color:#172033}.workspace{height:calc(100vh - 40px);min-height:0;display:flex;flex-direction:column}.sibling-tabs{display:flex;flex:none;gap:4px;margin-bottom:16px;padding:4px;border-radius:14px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.05)}.sibling-tabs button{padding:9px 18px;border:0;border-radius:10px;color:#64748b;background:transparent}.sibling-tabs .active{color:#fff;background:#3b82f6}.card{flex:1;min-height:0;display:flex;flex-direction:column;border-radius:16px;background:#fff;box-shadow:0 4px 16px rgba(15,23,42,.06);overflow:hidden}.card>header{display:flex;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #e2e8f0}.card h2{margin:0 0 4px;font-size:18px}.card header p{margin:0;color:#94a3b8;font-size:11px}.create{height:36px;padding:0 16px;border:0;border-radius:8px;color:#fff;background:#10b981}.toolbar{display:flex;align-items:end;gap:10px;padding:12px 20px;border-bottom:1px solid #e2e8f0}.toolbar label,.grid label{display:flex;flex-direction:column;gap:5px;color:#64748b;font-size:10px}.toolbar input,.toolbar select{width:160px;height:34px;padding:0 9px;border:1px solid #cbd5e1;border-radius:7px}.toolbar-actions{display:flex;gap:6px;margin-left:auto}.toolbar-actions button,.pagination button{height:32px;padding:0 12px;border:0;border-radius:7px;color:#475569;background:#f1f5f9}.primary{color:#fff!important;background:#3b82f6!important}.alert,.form-error{margin:9px 20px 0;padding:9px 11px;border-radius:7px;color:#b91c1c;background:#fef2f2;font-size:11px}.table-area{position:relative;flex:1;min-height:0;margin:11px 20px 0;overflow:hidden;border:1px solid #e2e8f0;border-radius:9px}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{height:48px;padding:0 12px;border-bottom:1px solid #edf1f6;text-align:left;font-size:12px}th{height:42px;color:#64748b;background:#f8fafc}.operation{width:285px}.protocol{padding:4px 8px;border-radius:5px;font-size:9px}.protocol.mqtt{color:#6d28d9;background:#ede9fe}.protocol.http{color:#0369a1;background:#e0f2fe}.status{display:inline-flex;align-items:center;gap:5px}.status i{width:7px;height:7px;border-radius:50%;background:#94a3b8}.status.on{color:#047857}.status.on i{background:#10b981}.actions{display:flex;gap:5px}.actions button{padding:5px 8px;border:0;border-radius:6px;color:#2563eb;background:#eff6ff}.actions button:disabled{opacity:.4}.actions .execute{color:#7c3aed;background:#ede9fe}.actions .start{color:#047857;background:#d1fae5}.actions .stop{color:#b45309;background:#fef3c7}.actions .danger{color:#dc2626;background:#fef2f2}.state{position:absolute;inset:43px 0 0;display:grid;place-items:center;color:#94a3b8;background:rgba(255,255,255,.87)}.pagination{height:55px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 20px;color:#94a3b8;font-size:11px}.pagination div{display:flex;align-items:center;gap:9px}.overlay{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;background:rgba(15,23,42,.48)}.modal{width:760px;max-width:95vw;max-height:94vh;display:flex;flex-direction:column;border-radius:15px;background:#fff;overflow:hidden}.modal>header{display:flex;justify-content:space-between;padding:18px 22px;border-bottom:1px solid #e2e8f0}.modal h2{margin:0 0 4px;font-size:18px}.modal header p{margin:0;color:#94a3b8;font-size:10px}.modal header>button{border:0;background:none;font-size:23px}.modal-body{position:relative;padding:17px 20px;overflow:auto}.modal-body section{margin-bottom:12px;padding:14px;border:1px solid #e2e8f0;border-radius:9px}.modal-body h3{margin:0 0 11px;font-size:13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:11px}.grid input,.grid select,.grid textarea{width:100%;padding:8px 9px;border:1px solid #cbd5e1;border-radius:7px;background:#fff}.grid textarea{resize:vertical;font:11px/1.5 ui-monospace,monospace}.grid label>span{color:#dc2626}.grid small{color:#94a3b8;font-size:9px}.wide{grid-column:1/-1}.check{align-items:center!important;flex-direction:row!important;justify-content:flex-start}.check input{width:auto}.mask{position:absolute;inset:0;z-index:2;display:grid;place-items:center;background:rgba(255,255,255,.84)}.modal>footer{display:flex;justify-content:flex-end;gap:8px;padding:13px 20px;border-top:1px solid #e2e8f0}.modal>footer button{height:35px;padding:0 16px;border:0;border-radius:7px;color:#475569;background:#f1f5f9}.execute-modal{width:660px}.execute-body{padding:18px 20px}.execute-warning{padding:13px;border:1px solid #fde68a;border-radius:8px;color:#92400e;background:#fffbeb;font-size:12px;line-height:1.6}.execute-body .form-error{margin:10px 0}.result{border:1px solid #d1fae5;border-radius:9px;overflow:auto;max-height:420px;padding:12px}.result>header{display:flex;justify-content:space-between;margin:-12px -12px 12px;padding:10px 12px;color:#047857;background:#ecfdf5}@media(max-width:760px){.page-content{padding:14px;overflow:auto}.workspace{height:auto}.toolbar{flex-wrap:wrap}.toolbar-actions{margin-left:0}.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
.pagination{border-top:1px solid #edf1f6}.pagination button{min-width:68px;border:1px solid #e2e8f0;background:#fff;transition:.15s}.pagination button:hover:not(:disabled){border-color:#93c5fd;color:#2563eb;background:#eff6ff}.pagination button:disabled{opacity:.4}.actions button{min-width:52px;height:30px;padding:0 8px;border:1px solid #dbe3ee;background:#fff;transition:.15s}.actions button:hover:not(:disabled){border-color:#93c5fd;color:#1d4ed8;background:#eff6ff}.actions .execute{border-color:#ddd6fe}.actions .start{border-color:#a7f3d0}.actions .stop{border-color:#fde68a}.actions .danger{border-color:#fecaca}.modal{border:1px solid rgba(255,255,255,.7);border-radius:18px;box-shadow:0 24px 70px rgba(15,23,42,.25)}.modal>header{position:relative;padding:22px 25px;background:linear-gradient(135deg,#f8fbff,#fff)}.modal>header:before{content:'';position:absolute;left:0;top:20px;bottom:20px;width:4px;border-radius:0 4px 4px 0;background:#3b82f6}.modal h2{font-size:20px;color:#0f172a}.modal header p{font-size:12px}.modal header>button{width:34px;height:34px;border-radius:9px;background:#f1f5f9;color:#64748b}.modal-body{padding:22px 24px;background:#f8fafc}.modal-body section{margin-bottom:16px;padding:18px;border-color:#e5eaf1;border-radius:12px;background:#fff;box-shadow:0 2px 7px rgba(15,23,42,.025)}.modal-body h3{display:flex;align-items:center;gap:8px;margin-bottom:15px;color:#1e293b;font-size:14px}.modal-body h3:before{content:'';width:4px;height:15px;border-radius:4px;background:#3b82f6}.grid{gap:14px}.grid label{gap:7px;color:#334155;font-size:12px}.grid input,.grid select,.grid textarea{min-height:41px;padding:10px 11px;border-color:#d8e0eb;border-radius:9px}.grid input:focus,.grid select:focus,.grid textarea:focus{border-color:#60a5fa;box-shadow:0 0 0 3px rgba(59,130,246,.12)}.grid textarea{resize:none}.modal>footer{padding:16px 24px;background:#fff}.modal>footer button{min-width:88px;height:38px;border:1px solid #e2e8f0}.modal>footer .primary{border-color:#3b82f6;box-shadow:0 3px 8px rgba(59,130,246,.2)}.execute-body{background:#f8fafc}
.operation{text-align:center}.actions{height:48px;align-items:center;justify-content:center}.pagination{justify-content:flex-end;gap:4px;height:55px}.pagination-info{margin-right:12px;font-size:13px}.page-buttons{display:flex;gap:4px}.pagination .page-btn{min-width:34px;width:auto;height:34px;padding:0 8px;display:grid;place-items:center;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:#475569;font-size:13px}.pagination .page-btn:hover:not(:disabled){border-color:#94a3b8;background:#f1f5f9}.pagination .page-btn.active{border-color:#3b82f6;color:#fff;background:#3b82f6}
.toolbar-actions .create{height:32px;color:#fff;background:#10b981;border:1px solid #10b981}.toolbar-actions .create:hover{background:#059669;border-color:#059669}.field-title{min-height:18px;display:flex;align-items:center;gap:4px;color:#334155!important;line-height:1.35}.field-title b{color:#dc2626;font-size:13px}.field-title small{margin-left:7px;color:#94a3b8;font-weight:400}.sensor-picker input[type=search]{min-height:38px}.sensor-picker select{height:132px;padding:5px}.sensor-picker option{padding:6px 8px;border-radius:5px}.payload-hint.valid{color:#059669}.payload-hint.invalid{color:#dc2626}.payload-hint.plain{color:#2563eb}.grid textarea.invalid{border-color:#ef4444;box-shadow:0 0 0 3px rgba(239,68,68,.1)}
.asset-type-col{width:88px}.asset-type{display:inline-block;padding:4px 8px;border-radius:6px;font-size:10px}.asset-type.terminal{color:#0369a1;background:#e0f2fe}.asset-type.sensor{color:#047857;background:#d1fae5}
</style>
