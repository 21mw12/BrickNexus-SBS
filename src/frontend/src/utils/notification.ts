import { readonly, ref } from 'vue'

export type NotificationKind = 'error' | 'warning' | 'info' | 'success'

export interface AppNotification {
  id: number
  kind: NotificationKind
  title: string
  message: string
  detail?: string
  actionLabel?: string
  onAction?: () => void
}

const notifications = ref<AppNotification[]>([])
const timers = new Map<number, ReturnType<typeof setTimeout>>()
let sequence = 0
let lastSignature = ''
let lastCreatedAt = 0

export const appNotifications = readonly(notifications)

export function dismissNotification(id: number) {
  notifications.value = notifications.value.filter(item => item.id !== id)
  const timer = timers.get(id)
  if (timer) clearTimeout(timer)
  timers.delete(id)
}

export function notify(
  kind: NotificationKind,
  message: string,
  options: { title?: string; detail?: string; duration?: number; actionLabel?: string; onAction?: () => void } = {},
) {
  const normalized = String(message || '').trim()
  if (!normalized) return 0
  const title = options.title || ({ error: '操作失败', warning: '操作提示', info: '系统提示', success: '操作成功' } as const)[kind]
  const signature = `${kind}:${title}:${normalized}:${options.detail || ''}`
  const createdAt = Date.now()
  if (signature === lastSignature && createdAt - lastCreatedAt < 800) return 0
  lastSignature = signature
  lastCreatedAt = createdAt

  const id = ++sequence
  notifications.value = [...notifications.value, { id, kind, title, message: normalized, detail: options.detail, actionLabel: options.actionLabel, onAction: options.onAction }].slice(-5)
  const duration = options.duration ?? (kind === 'error' ? 8000 : 5000)
  if (duration > 0) {
    const timer = setTimeout(() => dismissNotification(id), duration)
    timers.set(id, timer)
  }
  return id
}

export const notifyError = (message: string, title = '操作失败', detail?: string) =>
  notify('error', message, { title, detail, duration: 8000 })

export const notifyWarning = (message: string, title = '操作提示') =>
  notify('warning', message, { title })

export const notifyInfo = (message: string, title = '系统提示') =>
  notify('info', message, { title })

export const notifySuccess = (message: string, title = '操作成功') =>
  notify('success', message, { title })

export function notifyRetryableError(message: string, retry: () => void, title = '加载失败') {
  return notify('error', message, { title, actionLabel: '重新加载', onAction: retry, duration: 0 })
}
