export interface RealtimePoint {
  point_id: string
  value: unknown
  unit: string
}

export interface RealtimeSensor {
  sensor_id: string
  sensor_status: boolean
  point_list: RealtimePoint[]
}

export interface TerminalSnapshot {
  terminal_id: string
  terminal_status: boolean
  sensor_list: RealtimeSensor[]
  time: string
}

export interface SnapshotMessage {
  type: 'snapshot'
  terminal_ids: string[]
  rejected_terminal_ids: string[]
  missing_terminal_ids: string[]
  data: TerminalSnapshot[]
}

export interface TerminalUpdateMessage {
  type: 'terminal_update'
  terminal_id: string
  data: TerminalSnapshot
}

export interface RealtimeErrorMessage {
  type: 'error'
  code: 'invalid_message' | 'unauthorized' | 'redis_unavailable' | 'internal_error' | string
  message: string
}

export type RealtimeMessage = SnapshotMessage | TerminalUpdateMessage | RealtimeErrorMessage
export type RealtimeConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'unauthorized' | 'closed'

export interface RealtimeSocketHandlers {
  onState: (state: RealtimeConnectionState) => void
  onMessage: (message: RealtimeMessage) => void
}

/** 单页面 WebSocket 客户端：维护完整订阅列表，并在异常断线后恢复订阅。 */
export class TerminalRealtimeSocket {
  private socket: WebSocket | null = null
  private terminalIds: string[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private retryCount = 0
  private stopped = true

  constructor(private readonly handlers: RealtimeSocketHandlers) {}

  connect() {
    if (!this.stopped && (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING)) return
    this.stopped = false
    this.open(false)
  }

  subscribe(terminalIds: string[]) {
    this.terminalIds = [...new Set(terminalIds)]
    if (this.socket?.readyState === WebSocket.OPEN) this.sendSubscription()
    else this.connect()
  }

  stop() {
    this.stopped = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    const socket = this.socket
    this.socket = null
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'page closed')
    this.handlers.onState('closed')
  }

  disableForUnauthorized() {
    this.stopped = true
    this.terminalIds = []
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    const socket = this.socket
    this.socket = null
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'unauthorized')
    this.handlers.onState('unauthorized')
  }

  private open(reconnecting: boolean) {
    if (this.stopped) return
    this.handlers.onState(reconnecting ? 'reconnecting' : 'connecting')
    const pageSecure = typeof location !== 'undefined' && location.protocol === 'https:'
    const protocol = pageSecure ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${location.host}/api/ws/terminals`)
    this.socket = socket
    socket.onopen = () => {
      if (this.socket !== socket) return
      this.retryCount = 0
      this.handlers.onState('connected')
      this.sendSubscription()
    }
    socket.onmessage = event => {
      try {
        const message = JSON.parse(String(event.data)) as RealtimeMessage
        if (message && typeof message.type === 'string') this.handlers.onMessage(message)
      } catch {
        this.handlers.onMessage({ type: 'error', code: 'invalid_message', message: '服务端返回了无法解析的消息' })
      }
    }
    socket.onerror = () => { /* close 事件统一负责重连 */ }
    socket.onclose = event => {
      if (this.socket === socket) this.socket = null
      if (this.stopped) return
      this.retryCount += 1
      const delay = event.code === 1013 ? 5000 : Math.min(1000 * 2 ** (this.retryCount - 1), 15000)
      this.handlers.onState('reconnecting')
      this.reconnectTimer = setTimeout(() => this.open(true), delay)
    }
  }

  private sendSubscription() {
    if (this.socket?.readyState !== WebSocket.OPEN) return
    const token = localStorage.getItem('auth_token') || ''
    this.socket.send(JSON.stringify({ type: 'subscribe', token, terminal_ids: this.terminalIds }))
  }
}
