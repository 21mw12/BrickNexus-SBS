import { BASE_URL } from '../config'
import { getToken } from './auth'
export type ControlProtocol='mqtt'|'http'
export type ControlAssetType='terminal'|'sensor'
export interface ControlListItem{control_id:string;name:string;type:ControlProtocol;asset_type:ControlAssetType;asset_id:string;asset_name?:string;sensor_name?:string;status:boolean;created_at:string;asset?:{asset_id:string;asset_type:ControlAssetType;name:string;is_use:boolean}}
export interface ControlDetail extends ControlListItem{channel_id:string;mqtt_topic:string|null;mqtt_retained:boolean|null;mqtt_payload:string|null;http_method:'GET'|'POST'|null;http_path:string|null;http_header:Record<string,unknown>|null;http_params:Record<string,unknown>|null;http_body:Record<string,unknown>|null;asset:{asset_id:string;asset_type:ControlAssetType;name:string;is_use:boolean};channel:Record<string,unknown>}
export interface ControlPayload{name:string;type:ControlProtocol;channel_id:string;asset_type:ControlAssetType;asset_id:string;mqtt_topic?:string;mqtt_retained?:boolean;mqtt_payload?:string;http_method?:'GET'|'POST';http_path?:string;http_header?:Record<string,unknown>|null;http_params?:Record<string,unknown>|null;http_body?:Record<string,unknown>|null}
export interface ControlQuery{name?:string;type?:ControlProtocol;status?:boolean;asset_type?:ControlAssetType;asset_id?:string}
export interface ExecuteControlResult{success:boolean;executed_at:string;result:Record<string,unknown>}
async function extract(response:Response){try{return(await response.json())?.message}catch{return`请求失败（${response.status}）`}}
async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{const response=await fetch(`${BASE_URL}${path}`,{method,headers:{Authorization:`Bearer ${getToken()}`,Accept:'application/json',...(body!==undefined?{'Content-Type':'application/json'}:{})},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok)throw new Error(await extract(response));const result=await response.json();if(!result.success||result.code!==200)throw new Error(result.message||'请求失败');return result.data}
export async function fetchControlPage(page:number,limit:number,query:ControlQuery={}){const data=await request<{total:number;items:ControlListItem[]}>(`/control/list?page=${page}&limit=${limit}`,'POST',query);return{data:data.items,total:data.total}}
export const fetchControlDetail=(id:string)=>request<ControlDetail>(`/control/find/${encodeURIComponent(id)}`)
export const createControl=(payload:ControlPayload)=>request<ControlDetail>('/control/add','POST',payload)
export const editControl=(id:string,payload:ControlPayload)=>request<ControlDetail>(`/control/edit/${encodeURIComponent(id)}`,'POST',payload)
export const toggleControl=(id:string)=>request<{ok:boolean}>(`/control/toggle/${encodeURIComponent(id)}`,'POST')
export const deleteControl=(id:string)=>request<{ok:boolean}>(`/control/drop/${encodeURIComponent(id)}`)
export const executeControl=(id:string)=>request<ExecuteControlResult>(`/control/execute/${encodeURIComponent(id)}`,'POST')
