import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@kyralabs/m3exp-web/css/index.css'
import '@kyralabs/m3e-tokens/material-symbols.css'
import '@kyralabs/m3e-elements/loading-indicator.js'
import '@kyralabs/m3e-elements/text-field.js'
import '@kyralabs/m3e-elements/checkbox.js'
import '@kyralabs/m3e-elements/dialog.js'
import '@kyralabs/m3e-elements/menu.js'
import '@kyralabs/m3e-elements/tabs.js'
import '@kyralabs/m3e-elements/navigation-drawer.js'
import '@kyralabs/m3e-elements/icon.js'
import '@kyralabs/m3e-elements/linear-progress.js'
import '@kyralabs/m3e-elements/snackbar-host.js'
import '@kyralabs/m3e-elements/ripple.js'
import './theme.css'
import './layout.css'
import App from './App.vue'
import { router } from './router'
import { onExpired } from './api'
import { useSession, useServers } from './stores'

const app = createApp(App)
app.use(createPinia())
onExpired(() => {
  useSession().expire(); useServers().reset()
  void router.replace('/login')
})
app.use(router)
app.mount('#app')
