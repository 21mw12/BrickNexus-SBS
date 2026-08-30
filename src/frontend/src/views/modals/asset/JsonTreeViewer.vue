<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ data: any; depth?: number; keyName?: string; isIndex?: boolean }>()
const expanded = ref(props.depth === 0)

function toggle() { expanded.value = !expanded.value }

function typeClass(val: any): string {
  if (val === null || val === undefined) return 'jt-null'
  if (typeof val === 'string') return 'jt-string'
  if (typeof val === 'number') return 'jt-number'
  if (typeof val === 'boolean') return 'jt-bool'
  return ''
}

function formatVal(val: any): string {
  if (val === null) return 'null'
  if (val === undefined) return 'undefined'
  if (typeof val === 'string') return `"${val}"`
  return String(val)
}
</script>

<template>
  <div class="jt-node" :style="{ paddingLeft: depth ? '16px' : '0' }">
    <!-- 对象 -->
    <template v-if="typeof data === 'object' && data !== null && !Array.isArray(data)">
      <div class="jt-line" @click="toggle">
        <span class="jt-arrow">{{ expanded ? '▾' : '▸' }}</span>
        <span :class="isIndex ? 'jt-index' : 'jt-key'" v-if="keyName">{{ keyName }}: </span>
        <span class="jt-brace">{{ '{' }}</span>
        <span class="jt-count" v-if="!expanded">{{ Object.keys(data).length }} keys</span>
      </div>
      <template v-if="expanded">
        <JsonTreeViewer v-for="(v, k) in data" :key="k" :data="v" :key-name="String(k)" :depth="(depth || 0) + 1" />
        <div class="jt-line" :style="{ paddingLeft: '16px' }"><span class="jt-brace">}</span></div>
      </template>
    </template>

    <!-- 数组 -->
    <template v-else-if="Array.isArray(data)">
      <div class="jt-line" @click="toggle">
        <span class="jt-arrow">{{ expanded ? '▾' : '▸' }}</span>
        <span :class="isIndex ? 'jt-index' : 'jt-key'" v-if="keyName">{{ keyName }}: </span>
        <span class="jt-brace">[</span>
        <span class="jt-count" v-if="!expanded">{{ data.length }} items</span>
      </div>
      <template v-if="expanded">
        <JsonTreeViewer v-for="(v, i) in data" :key="i" :data="v" :key-name="String(i)" :is-index="true" :depth="(depth || 0) + 1" />
        <div class="jt-line" :style="{ paddingLeft: '16px' }"><span class="jt-brace">]</span></div>
      </template>
    </template>

    <!-- 基本类型 -->
    <div class="jt-line" v-else>
      <span class="jt-arrow jt-empty"></span>
      <span :class="isIndex ? 'jt-index' : 'jt-key'" v-if="keyName">{{ keyName }}: </span>
      <span :class="typeClass(data)">{{ formatVal(data) }}</span>
    </div>
  </div>
</template>

<style scoped>
.jt-node { font-family: 'Menlo', 'Consolas', 'Courier New', monospace; font-size: 12px; line-height: 1.6; }
.jt-line { display: flex; align-items: baseline; cursor: pointer; white-space: nowrap; }
.jt-line:hover { background: rgba(59,130,246,0.04); border-radius: 2px; }
.jt-arrow { width: 14px; flex-shrink: 0; color: #94a3b8; font-size: 10px; user-select: none; }
.jt-empty { visibility: hidden; }
.jt-key { color: #7c3aed; flex-shrink: 0; }
.jt-index { color: #94a3b8; flex-shrink: 0; }
.jt-brace { color: #64748b; }
.jt-count { color: #94a3b8; font-size: 11px; margin-left: 4px; }
.jt-string { color: #16a34a; }
.jt-number { color: #2563eb; }
.jt-bool { color: #d97706; }
.jt-null { color: #94a3b8; font-style: italic; }
</style>
