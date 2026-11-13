import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './stores'
import AuthView from './views/AuthView.vue'
import ServersView from './views/ServersView.vue'
import ServerView from './views/ServerView.vue'
import SettingsView from './views/SettingsView.vue'
import MapsView from './views/MapsView.vue'
import ModsView from './views/ModsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: (_to, _from, saved) => saved || { top: 0 },
  routes: [
    { path: '/', redirect: '/servers' },
    { path: '/login', component: AuthView },
    { path: '/setup', component: AuthView },
    { path: '/servers', component: ServersView },
    { path: '/servers/:id/console', component: ServerView },
    { path: '/servers/:id/settings', component: SettingsView },
    { path: '/servers/:id/maps', component: MapsView },
    { path: '/servers/:id/mods', component: ModsView },
    { path: '/:pathMatch(.*)*', redirect: '/servers' },
  ],
})
router.beforeEach(async to => {
  const session = useSession()
  if (!session.ready) await session.load()
  if (session.setupRequired && to.path !== '/setup') return '/setup'
  if (!session.setupRequired && !session.user && to.path !== '/login') return '/login'
  if (session.user && ['/login', '/setup'].includes(to.path)) return '/servers'
})
