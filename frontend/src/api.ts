let csrf = ''
let expired = () => {}
export function setCsrf(value: string) { csrf = value }
export function onExpired(callback: () => void) { expired = callback }
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  let data: any
  try { data = await response.json() }
  catch { throw new ApiError('The panel returned an unreadable response. Check the connection.', response.status) }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) expired()
    throw new ApiError(data.error || 'The request failed.', response.status)
  }
  return data as T
}

export function upload<T>(path: string, body: FormData, progress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', '/api' + path)
    request.withCredentials = true
    request.timeout = 15 * 60 * 1000
    request.setRequestHeader('X-CSRF-Token', csrf)
    request.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded * 100 / event.total)) }
    request.onerror = () => reject(new ApiError('Upload connection failed. Check the instance before retrying.', 0))
    request.ontimeout = () => reject(new ApiError('Upload timed out. Check the instance before retrying.', 0))
    request.onload = () => {
      let data: any
      try { data = JSON.parse(request.responseText) }
      catch { reject(new ApiError('The panel returned an unreadable upload response.', request.status)); return }
      if (request.status >= 200 && request.status < 300) resolve(data as T)
      else {
        if (request.status === 401) expired()
        reject(new ApiError(data.error || 'Upload failed.', request.status))
      }
    }
    request.send(body)
  })
}
