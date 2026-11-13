let csrf = ''
let expired = () => {}
export function setCsrf(value: string) { csrf = value }
export function onExpired(callback: () => void) { expired = callback }
function reportExpired(requestCsrf: string) {
  // Logout/login rotate CSRF. A response from an older session cannot expire
  // the signed-out state or a subsequent sign-in.
  if (requestCsrf === csrf) expired()
}
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const requestCsrf = csrf
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': requestCsrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  let data: any
  try { data = await response.json() }
  catch { throw new ApiError('The panel returned an unreadable response. Check the connection.', response.status) }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) reportExpired(requestCsrf)
    throw new ApiError(data.error || 'The request failed.', response.status)
  }
  return data as T
}

export function upload<T>(path: string, body: FormData, progress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const requestCsrf = csrf
    const request = new XMLHttpRequest()
    request.open('POST', '/api' + path)
    request.withCredentials = true
    request.timeout = 15 * 60 * 1000
    request.setRequestHeader('X-CSRF-Token', requestCsrf)
    request.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded * 100 / event.total)) }
    request.onerror = () => reject(new ApiError('Upload connection failed. Check the instance before retrying.', 0))
    request.ontimeout = () => reject(new ApiError('Upload timed out. Check the instance before retrying.', 0))
    request.onload = () => {
      let data: any
      try { data = JSON.parse(request.responseText) }
      catch { reject(new ApiError('The panel returned an unreadable upload response.', request.status)); return }
      if (request.status >= 200 && request.status < 300) resolve(data as T)
      else {
        if (request.status === 401) reportExpired(requestCsrf)
        reject(new ApiError(data.error || 'Upload failed.', request.status))
      }
    }
    request.send(body)
  })
}
