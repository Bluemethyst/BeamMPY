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
export type Permission = 'power' | 'maps' | 'mods_toggle' | 'mods_upload' | 'configure' | 'console_view' | 'console_command' | 'statistics_view'
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
export interface StatisticsPoint {
  time: number; cpu: number | null; cpu_peak: number | null; memory: number | null; memory_peak: number | null
  players: number | null; joins: number | null
}
export interface Statistics {
  server_id: string; range: string; bucket_seconds: number; telemetry_enabled: boolean
  live: { status: string; time: number | null; cpu: number | null; memory: number | null; uptime: number | null; players: number | null; player_status: string }
  history: StatisticsPoint[]; summary: { peak_players: number | null; joins: number | null }
}
export interface MapChoice { path: string; name: string; kind: 'stock' | 'custom'; enabled: boolean; mod: string | null }
export interface Mod { filename: string; enabled: boolean; size: number; maps: { path: string; name: string }[]; error: string | null }
