import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { installAuthFetchInterceptor } from './utils/authSession'

installAuthFetchInterceptor()
createApp(App).use(router).mount('#app')
