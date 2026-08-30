<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api/auth'

const router = useRouter()
const account = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submitForm() {
  error.value = ''
  if (!account.value || !password.value) {
    error.value = '请输入账号和密码'
    return
  }
  loading.value = true
  try {
    // login() 内部已从登录 API 响应中获取 page_codes 并存储到 localStorage
    await login({ account: account.value, password: password.value })
    // 登录成功后统一进入看板
    await router.push('/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-form-panel">
        <div class="form-header">
          <div>
            <h2>欢迎登录智慧楼宇系统</h2>
            <p class="form-tip">请输入账号和密码完成登录。</p>
          </div>
        </div>

        <div class="form-group">
          <label>账号</label>
          <input v-model="account" type="text" placeholder="请输入账号" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" />
        </div>

        <div v-if="error" class="error-message">{{ error }}</div>

        <button class="login-button" @click="submitForm" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </div>

      <div class="login-visual-panel">
        <img class="visual-image" src="/images/login-visual.png" alt="登录视觉图" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 54%, #2b7be4 100%);
}

.login-card {
  width: min(760px, 100%);
  background: #ffffff;
  border: 1px solid #d1d9e6;
  border-radius: 28px;
  box-shadow: 0 25px 60px rgba(30, 42, 62, 0.08);
  display: flex;
  overflow: hidden;
}

.login-form-panel {
  width: min(420px, 100%);
  padding: 44px 40px 40px;
}

.form-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 32px;
}

.form-eyebrow {
  margin: 0 0 10px;
  color: #2b7be4;
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.login-form-panel h2 {
  margin: 0;
  font-size: 2rem;
  color: #1e2a3e;
  line-height: 1.1;
}

.form-tip {
  margin: 0;
  color: #6c7a8e;
  max-width: 240px;
  font-size: 0.95rem;
  line-height: 1.7;
}

.form-group {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.form-group label {
  width: 50px;
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1e2a3e;
  line-height: 44px;
}

.form-group input {
  flex: 1;
  min-height: 44px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid #d1d9e6;
  background: #ffffff;
  color: #1e2a3e;
  font-size: 1.08rem;
  outline: none;
}

.form-group input::placeholder {
  color: #b0c0d0;
}

.form-group input:focus {
  border-color: #2b7be4;
  box-shadow: 0 0 0 4px rgba(43, 123, 228, 0.12);
}

.error-message {
  margin-bottom: 18px;
  color: #d14343;
  background: #ffecec;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid #f6c0c0;
}

.login-button {
  width: 100%;
  padding: 14px 0;
  border: none;
  border-radius: 14px;
  background: #2b7be4;
  color: #ffffff;
  font-weight: 700;
  font-size: 1.05rem;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.login-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(43, 123, 228, 0.2);
}

.login-visual-panel {
  flex: 1;
  min-width: 260px;
  background: linear-gradient(180deg, rgba(43, 123, 228, 0.16), rgba(43, 123, 228, 0.04));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}

.visual-image {
  width: 100%;
  height: auto;
  max-width: 320px;
  border-radius: 24px;
  object-fit: contain;
  box-shadow: 0 18px 40px rgba(16, 42, 62, 0.08);
}

@media (max-width: 920px) {
  .login-card {
    flex-direction: column;
  }

  .login-visual-panel {
    min-height: 200px;
    padding: 24px;
  }
}

@media (max-width: 720px) {
  .login-page {
    padding: 20px;
  }

  .login-card {
    width: 100%;
  }

  .login-form-panel {
    padding: 32px 24px 28px;
  }
}
</style>
