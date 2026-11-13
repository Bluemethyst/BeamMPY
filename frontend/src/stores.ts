import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, setCsrf } from './api'
import type { Operation, Server, Session } from './types'

export const useSession = defineStore('session', () => {
  const user = ref<Session['user']>(null)
  const setupRequired = ref(false)
  const csrf = ref('')
  const ready = ref(false)
  function apply(value: Session) {
    user.value = value.user; setupRequired.value = value.setup_required
    csrf.value = value.csrf_token; setCsrf(value.csrf_token); ready.value = true
  }
  async function load() { apply(await api<Session>('/auth/session')) }
  async function authenticate(mode: 'login' | 'setup', username: string, password: string) {
    apply(await api<Session>('/auth/' + mode, 'POST', { username, password }))
  }
  async function logout() { apply(await api<Session>('/auth/logout', 'POST', {})) }
  function expire() { user.value = null; ready.value = false }
  return { user, setupRequired, csrf, ready, apply, load, authenticate, logout, expire }
})

export const useNotices = defineStore('notices', () => {
  const items = ref<{ id: number; message: string; error: boolean }[]>([])
  let nextId = 0
  function dismiss(id: number) { items.value = items.value.filter(item => item.id !== id) }
  function show(message: string, error = false) {
    const id = ++nextId
    items.value.push({ id, message, error })
  }
  return { items, show, dismiss }
})

export const useServers = defineStore('servers', () => {
  const servers = ref<Server[]>([])
  const operations = ref<Record<string, Operation>>({})
  const loading = ref(false)
  const error = ref('')
  let request: Promise<void> | null = null
  let generation = 0
  function update(server: Server) {
    const index = servers.value.findIndex(item => item.id === server.id)
    if (index < 0) servers.value.push(server)
    else servers.value[index] = server
  }
  async function refresh() {
    if (request) return request
    const started = generation
    request = (async () => {
      loading.value = true
      try {
        const result = await api<{ servers: Server[] }>('/servers')
        if (started === generation) {
          servers.value = result.servers; error.value = ''
          for (const server of result.servers) {
            if (server.operation) operations.value[server.id] = server.operation
            else delete operations.value[server.id]
          }
        }
      } catch (err) { if (started === generation) error.value = (err as Error).message }
      finally { loading.value = false; request = null }
    })()
    return request
  }
  async function track(initial: Operation) {
    const started = generation
    operations.value[initial.server_id] = initial
    let current = initial
    try {
      while (current.state === 'running' && started === generation) {
        await new Promise(resolve => setTimeout(resolve, 500))
        if (started !== generation) return
        current = (await api<{ operation: Operation }>('/operations/' + initial.id)).operation
        operations.value[initial.server_id] = current
      }
      if (started !== generation) return
      useNotices().show(current.message, current.state === 'failed')
    } catch (err) { if (started === generation) useNotices().show((err as Error).message, true) }
    finally {
      if (started === generation) { delete operations.value[initial.server_id]; await refresh() }
    }
  }
  async function operate(id: string, action: string) {
    if (operations.value[id]) return
    const result = await api<{ operation: Operation }>(`/servers/${id}/${action}`, 'POST', {})
    void track(result.operation)
    await refresh()
  }
  function reset() { generation++; servers.value = []; operations.value = {}; error.value = '' }
  return { servers, operations, loading, error, refresh, update, track, operate, reset }
})
