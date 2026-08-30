<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { createAccount } from '../../../api/user'
import type { RoleInfo } from '../../../api/user'

const props = defineProps<{
  visible: boolean
  roleList: RoleInfo[]
}>()

const emit = defineEmits<{
  close: []
  created: []
}>()

const loading = ref(false)
const error = ref('')
const form = reactive({
  account: '',
  password: '',
  nickname: '',
  role_id: '',
})

// 每次打开时重置表单
watch(() => props.visible, (v) => {
  if (v) {
    form.account = ''
    form.password = ''
    form.nickname = ''
    form.role_id = ''
    error.value = ''
  }
})

async function confirm() {
  error.value = ''
  loading.value = true
  try {
    await createAccount({ ...form })
    emit('created')
    emit('close')
  } catch (e: any) {
    error.value = e?.message || '创建失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" v-if="visible" @click.self="emit('close')">
    <div class="modal-card form-modal">
      <div class="modal-header">
        <h3>新增账号</h3>
      </div>
      <div class="modal-body form-grid">
        <div class="field">
          <label class="field-label">账号名</label>
          <input
            v-model="form.account"
            type="text"
            placeholder="请输入账号名"
            class="field-input"
          />
        </div>
        <div class="field">
          <label class="field-label">昵称</label>
          <input
            v-model="form.nickname"
            type="text"
            placeholder="请输入昵称"
            class="field-input"
          />
        </div>
        <div class="field">
          <label class="field-label">密码</label>
          <input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            class="field-input"
          />
        </div>
        <div class="field">
          <label class="field-label">所属角色</label>
          <select v-model="form.role_id" class="field-select modal-select">
            <option value="" disabled>请选择角色</option>
            <option
              v-for="role in roleList"
              :key="role.role_id"
              :value="role.role_id"
            >
              {{ role.name }}
            </option>
          </select>
        </div>
        <div class="modal-error form-span-2" v-if="error">{{ error }}</div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" @click="emit('close')" :disabled="loading">取消</button>
        <button class="btn btn-primary" @click="confirm" :disabled="loading">
          {{ loading ? '创建中...' : '确认' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: 440px;
  max-width: 90vw;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}

.modal-header {
  padding: 20px 24px 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.modal-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-modal { width: 620px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 16px; }
.form-grid .field { min-width: 0; }
.form-span-2 { grid-column: span 2; }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
  .form-span-2 { grid-column: span 1; }
}

.modal-select {
  width: 100%;
}

.modal-error {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 13px;
  line-height: 1.5;
}

.modal-footer {
  padding: 0 24px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ---------- 表单控件 ---------- */
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.field-input,
.field-select {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field-input:focus,
.field-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.field-input::placeholder {
  color: #94a3b8;
}

/* ---------- 按钮 ---------- */
.btn {
  height: 38px;
  padding: 0 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, opacity 0.2s ease;
  white-space: nowrap;
}

.btn-outline {
  background: #f1f5f9;
  color: #475569;
}

.btn-outline:hover {
  background: #e2e8f0;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}

.btn-primary:hover {
  background: #2563eb;
}
</style>
