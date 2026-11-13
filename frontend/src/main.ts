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
  const session = useSession()
  // Already-signed-out pages must stay ready, even when old work returns 401.
  if (!session.user) return
  session.expire(); useServers().reset()
  // Run the session guard even if a concurrent logout already opened /login.
  void router.replace({ path: '/login', force: true })
})
app.use(router)
app.mount('#app')
