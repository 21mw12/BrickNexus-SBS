<script setup lang="ts">
import { appNotifications, dismissNotification } from '../utils/notification'

const icon: Record<string, string> = { error: '!', warning: '!', info: 'i', success: '✓' }
function runAction(id: number, action?: () => void) {
  dismissNotification(id)
  action?.()
}
</script>

<template>
  <Teleport to="body">
    <div class="notification-host" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="notification">
        <article
          v-for="item in appNotifications"
          :key="item.id"
          class="notification-card"
          :class="item.kind"
          :role="item.kind === 'error' ? 'alert' : 'status'"
        >
          <i class="notification-icon">{{ icon[item.kind] }}</i>
          <div class="notification-content">
            <strong>{{ item.title }}</strong>
            <p>{{ item.message }}</p>
            <small v-if="item.detail">{{ item.detail }}</small>
            <button v-if="item.actionLabel" type="button" class="notification-action" @click="runAction(item.id,item.onAction)">{{ item.actionLabel }}</button>
          </div>
          <button type="button" aria-label="关闭提醒" @click="dismissNotification(item.id)">×</button>
          <span v-if="!item.actionLabel" class="notification-progress"></span>
        </article>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.notification-host{position:fixed;z-index:3000;top:20px;right:22px;width:min(390px,calc(100vw - 32px));display:flex;flex-direction:column;gap:10px;pointer-events:none}.notification-card{position:relative;display:grid;grid-template-columns:34px minmax(0,1fr) 22px;gap:11px;padding:14px 14px 16px;border:1px solid #dbeafe;border-radius:13px;color:#1e3a8a;background:rgba(255,255,255,.98);box-shadow:0 18px 45px rgba(15,23,42,.18);overflow:hidden;pointer-events:auto}.notification-card.error{border-color:#fecaca;color:#991b1b;box-shadow:0 18px 45px rgba(127,29,29,.2)}.notification-card.warning{border-color:#fed7aa;color:#92400e}.notification-card.success{border-color:#a7f3d0;color:#047857}.notification-icon{width:32px;height:32px;display:grid;place-items:center;border-radius:50%;color:#fff;background:#3b82f6;font-style:normal;font-size:16px;font-weight:800}.error .notification-icon{background:#dc2626}.warning .notification-icon{background:#f59e0b}.success .notification-icon{background:#10b981}.notification-content{min-width:0}.notification-content strong{display:block;margin:1px 0 5px;color:inherit;font-size:13px}.notification-content p{margin:0;color:#475569;font-size:11px;line-height:1.55;overflow-wrap:anywhere}.notification-content small{display:block;margin-top:5px;color:#94a3b8;font-size:9px}.notification-card>button{align-self:start;padding:0;border:0;color:#94a3b8;background:none;font-size:19px;line-height:20px;cursor:pointer}.notification-card>button:hover{color:#475569}.notification-progress{position:absolute;right:0;bottom:0;left:0;height:2px;background:currentColor;opacity:.32;transform-origin:left;animation:notification-progress 8s linear forwards}.warning .notification-progress,.info .notification-progress,.success .notification-progress{animation-duration:5s}@keyframes notification-progress{to{transform:scaleX(0)}}.notification-enter-active,.notification-leave-active{transition:transform .22s ease,opacity .22s ease}.notification-enter-from,.notification-leave-to{transform:translateX(42px);opacity:0}.notification-move{transition:transform .22s ease}@media(max-width:640px){.notification-host{top:12px;right:12px;width:calc(100vw - 24px)}}
.notification-content .notification-action{margin-top:9px;padding:5px 10px;border:1px solid currentColor;border-radius:6px;color:inherit;background:#fff;font-size:10px;line-height:16px;cursor:pointer}.notification-content .notification-action:hover{background:#f8fafc}
</style>
