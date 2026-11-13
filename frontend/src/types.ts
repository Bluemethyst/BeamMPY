export type ServerState = 'installing' | 'stopped' | 'starting' | 'running' | 'stopping' | 'error'
export interface Server {
  id: string; name: string; directory?: string; version: string | null
  state: ServerState; running: boolean; executable_exists: boolean; port: number | null; error: string | null
  operation?: Operation | null
}
export interface Operation {
  id: string; server_id: string; action: string; state: 'running' | 'succeeded' | 'failed'; progress: number; message: string
}
export interface Session {
  user: Account | null; setup_required: boolean; csrf_token: string
}
export type Permission = 'power' | 'maps' | 'mods_toggle' | 'mods_upload' | 'configure' | 'console_view' | 'console_command'
export interface Account {
  id: string; username: string; is_admin: boolean; can_create_servers: boolean; must_change_password: boolean
  permissions: Record<string, Permission[]>; enabled?: boolean
}
export interface Settings {
  Name: string; Description: string; Map: string; Port: number; MaxPlayers: number; MaxCars: number
  Private: boolean; AllowGuests: boolean; LogChat: boolean; Debug: boolean; InformationPacket: boolean
  IP: string; Tags: string; has_auth_key: boolean; AuthKey?: string
}
export interface ConsoleLine { sequence: number; text: string; time: number }
export interface MapChoice { path: string; name: string; kind: 'stock' | 'custom'; enabled: boolean; mod: string | null }
export interface Mod { filename: string; enabled: boolean; size: number; maps: { path: string; name: string }[]; error: string | null }
