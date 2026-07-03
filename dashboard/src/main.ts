import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import naive from 'naive-ui'
import { createPinia } from 'pinia'

import App from './app.vue'
import { router } from './router'
import './styles/tokens.css'
import './styles/global.css'

const app = createApp(App)

app.use(createPinia())
app.use(naive)
app.use(VueQueryPlugin)
app.use(router)

app.mount('#app')
