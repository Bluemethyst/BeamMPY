import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './stores'
import AuthView from './views/AuthView.vue'
import ServersView from './views/ServersView.vue'
import ServerView from './views/ServerView.vue'
import SettingsView from './views/SettingsView.vue'
import MapsView from './views/MapsView.vue'
import ModsView from './views/ModsView.vue'
import AccountView from './views/AccountView.vue'
import UsersView from './views/UsersView.vue'
import StatisticsView from './views/StatisticsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: (_to, _from, saved) => saved || { top: 0 },
  routes: [
    { path: '/', redirect: '/servers' },
    { path: '/login', component: AuthView },
    { path: '/setup', component: AuthView },
    { path: '/servers', component: ServersView },
    { path: '/account', component: AccountView },
    { path: '/users', component: UsersView },
    { path: '/servers/:id/console', component: ServerView },
    { path: '/servers/:id/settings', component: SettingsView },
    { path: '/servers/:id/maps', component: MapsView },
    { path: '/servers/:id/mods', component: ModsView },
    { path: '/servers/:id/statistics', component: StatisticsView },
    { path: '/:pathMatch(.*)*', redirect: '/servers' },
  ],
})
router.beforeEach(async to => {
  const session = useSession()
  if (!session.ready) await session.load()
  if (session.setupRequired && to.path !== '/setup') return '/setup'
  if (!session.setupRequired && !session.user && to.path !== '/login') return '/login'
  if (session.user && ['/login', '/setup'].includes(to.path)) return '/servers'
  if (session.user?.must_change_password && to.path !== '/account') return '/account'
  if (to.path === '/users' && !session.user?.is_admin) return '/servers'
  if (to.params.id && session.user) {
    const id = String(to.params.id)
    if (!session.user.is_admin && !(id in session.user.permissions)) return '/servers'
    if (to.path.endsWith('/settings') && !session.can('configure', id)) return `/servers/${id}/console`
    if (to.path.endsWith('/statistics') && !session.can('statistics_view', id)) return `/servers/${id}/console`
  }
})
