import { getToken } from './auth'
import type { ActiveFault, Sandbox, SandboxEvent } from './sandbox'

export type SandboxConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'unauthorized' | 'closed'

export interface RealtimeMeasurement {
  point_id?: string
  tick: number
  value: number | null
}

export interface RealtimeSeries {
  point_id: string
  measurements: Array<{ tick: number; value: number | null }>
}

interface SchedulePayload {
  server_time: string
  next_tick_at: string | null
  tick_interval_seconds: number
}

export type SandboxRealtimeMessage =
  | ({
      type: 'snapshot'
      subscription_version: number
      sandbox: Sandbox
      point_ids: string[]
      rejected_point_ids: string[]
      series: RealtimeSeries[]
      active_faults: ActiveFault[]
    } & SchedulePayload)
  | ({ type: 'sandbox_state'; sandbox_id: string; state: boolean; tick: number } & SchedulePayload)
  | ({ type: 'sandbox_speed'; sandbox_id: string; speed: 1 | 2 | 5 | 10; tick: number } & SchedulePayload)
  | ({
      type: 'tick'
      sandbox_id: string
      tick: number
      subscription_version: number
      measurements: Array<Required<RealtimeMeasurement>>
    } & SchedulePayload)
  | { type: 'fault_event' | 'rule_event'; event: SandboxEvent }
  | { type: 'heartbeat' }
  | ({ type: 'error'; code?: string; message: string } & Partial<SchedulePayload>)

export class SandboxRealtimeSocket {
  private socket: WebSocket | null = null
  private sandboxId = ''
  private pointIds: string[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private retryCount = 0
  private stopped = true
  private subscriptionVersion = 0
  private requestedVersion = 0

  constructor(private readonly handlers: {
    onState: (state: SandboxConnectionState) => void
    onMessage: (message: SandboxRealtimeMessage) => void
  }) {}

  connect(sandboxId: string) {
    this.stop(false)
    this.sandboxId = sandboxId
    this.stopped = false
    this.open(false)
  }

  subscribe(pointIds: string[]) {
    this.pointIds = [...new Set(pointIds)]
    if (this.socket?.readyState === WebSocket.OPEN) this.sendSubscription()
  }

  stop(notify = true) {
    this.stopped = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    const socket = this.socket
    this.socket = null
    this.subscriptionVersion = 0
    this.requestedVersion = 0
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'page changed')
    if (notify) this.handlers.onState('closed')
  }

  private open(reconnecting: boolean) {
    if (this.stopped || !this.sandboxId) return
    this.handlers.onState(reconnecting ? 'reconnecting' : 'connecting')
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${location.host}/api/ws/sandboxes/${encodeURIComponent(this.sandboxId)}`)
    this.socket = socket
    socket.onopen = () => {
      if (this.socket !== socket) return
      const token = getToken()
      if (!token) {
        this.stopped = true
        this.handlers.onState('unauthorized')
        socket.close(1008, 'missing token')
        return
      }
      this.retryCount = 0
      this.subscriptionVersion = 0
      this.requestedVersion = 0
      this.handlers.onState('connected')
      this.sendSubscription()
    }
    socket.onmessage = event => {
      try {
        const message = JSON.parse(String(event.data)) as SandboxRealtimeMessage
        if (message?.type === 'error' && message.code === 'unauthorized') this.handlers.onState('unauthorized')
        if (message?.type === 'snapshot') {
          if (message.subscription_version < this.requestedVersion || message.subscription_version < this.subscriptionVersion) return
          this.subscriptionVersion = message.subscription_version
        }
        if (message?.type === 'tick' && message.subscription_version < this.subscriptionVersion) return
        this.handlers.onMessage(message)
      } catch {
        this.handlers.onMessage({ type: 'error', code: 'invalid_message', message: '服务端返回了无法解析的实时消息' })
      }
    }
    socket.onerror = () => { /* close 事件统一处理 */ }
    socket.onclose = event => {
      if (this.socket === socket) this.socket = null
      if (this.stopped) return
      if (event.code === 1008) {
        this.stopped = true
        this.handlers.onState('unauthorized')
        return
      }
      this.retryCount += 1
      this.handlers.onState('reconnecting')
      const delay = event.code === 1013 ? 5000 : Math.min(1000 * 2 ** (this.retryCount - 1), 15000)
      this.reconnectTimer = setTimeout(() => this.open(true), delay)
    }
  }

  private sendSubscription() {
    if (this.socket?.readyState !== WebSocket.OPEN) return
    const token = getToken()
    if (!token) {
      this.handlers.onState('unauthorized')
      this.socket.close(1008, 'missing token')
      return
    }
    this.requestedVersion += 1
    this.socket.send(JSON.stringify({
      type: 'subscribe',
      token,
      point_ids: this.pointIds,
      history_limit: 100,
    }))
  }
}
