import { test, expect } from '@playwright/test'
import { createServer } from 'node:net'

test.use({ baseURL: 'http://127.0.0.1:8792' })

async function port(): Promise<number> {
  const server = createServer()
  await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(0, '::', resolve) })
  const value = server.address()
  if (!value || typeof value === 'string') throw new Error('No disposable port')
  await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  return value.port
}

test('per-server resource history, player telemetry, permissions, time ranges and mobile charts', async ({ page, browser }) => {
  test.setTimeout(90000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const bootstrap = await (await page.request.get('/api/auth/session')).json()
  const login = await page.request.post(`/api/auth/${bootstrap.setup_required ? 'setup' : 'login'}`, {
    headers: { 'X-CSRF-Token': bootstrap.csrf_token }, data: { username: 'admin', password: 'setup888' },
  })
  expect(login.ok()).toBe(true)
  const auth = await login.json(), headers = { 'X-CSRF-Token': auth.csrf_token }
  const created = await page.request.post('/api/servers', { headers, data: { name: 'Statistics instance', port: await port(), auth_key: 'disposable-statistics-fixture' } })
  expect(created.status()).toBe(202)
  const result = await created.json(), id = result.server.id
  await expect.poll(async () => (await (await page.request.get(`/api/operations/${result.operation.id}`)).json()).operation.state).toBe('succeeded')
  await page.goto(`/servers/${id}/statistics`)
  await expect(page.getByRole('tab', { name: 'Statistics', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('Server stopped', { exact: true })).toBeVisible()
  await expect(page.getByRole('article', { name: 'CPU usage', exact: true })).toContainText('No observations')
  await page.getByLabel('Collect player statistics', { exact: true }).check()
  await expect.poll(async () => (await (await page.request.get(`/api/servers/${id}/statistics`)).json()).telemetry_enabled).toBe(true)
  // Start without a console or Statistics page mounted: the panel owns collection.
  await page.goto('/servers')
  const start = await page.request.post(`/api/servers/${id}/start`, { headers, data: {} })
  expect(start.status()).toBe(202)
  await expect.poll(async () => (await (await page.request.get(`/api/servers/${id}/statistics`)).json()).live.memory, { timeout: 15000 }).toBeGreaterThan(0)
  // CPU is an interval measurement: its first observation intentionally has no value.
  await expect.poll(async () => (await (await page.request.get(`/api/servers/${id}/statistics`)).json()).live.cpu, { timeout: 15000 }).not.toBeNull()
  await page.goto(`/servers/${id}/console`)
  await expect(page.locator('.console-connection')).toContainText('Connected')
  await page.getByLabel('Console command', { exact: true }).fill('fixture-player-join')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.terminal')).toContainText('ECHO fixture-player-join')
  await expect(page.locator('.terminal')).not.toContainText('BEAMMPY_STATS:')
  await page.getByRole('tab', { name: 'Statistics', exact: true }).click()
  await expect(page.locator('.statistics-value').filter({ hasText: 'PLAYERS ONLINE' }).locator('strong')).toHaveText('1')
  await expect(page.getByRole('region', { name: 'Player activity', exact: true })).toContainText('1 successful joins')
  await expect(page.getByRole('img', { name: /^CPU usage/ })).toBeVisible()
  await expect(page.getByRole('img', { name: /^Memory usage/ })).toBeVisible()
  await expect(page.getByLabel('Collect player statistics', { exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Last hour', exact: true })).toBeVisible()
  await expect(page.getByRole('article', { name: 'CPU usage', exact: true })).toContainText('Intervals: 10 sec')
  await page.getByRole('button', { name: 'Last hour', exact: true }).click()
  await page.getByRole('menuitemradio', { name: 'Last 24 hours', exact: true }).click()
  await expect(page.getByRole('article', { name: 'CPU usage', exact: true })).toContainText('Intervals: 5 min')
  await page.getByRole('button', { name: 'Last 24 hours', exact: true }).click()
  await page.getByRole('menuitemradio', { name: 'Last hour', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Last hour', exact: true })).toBeVisible()
  await expect(page.getByRole('article', { name: 'CPU usage', exact: true })).toContainText('Intervals: 10 sec')
  await page.getByRole('button', { name: 'Show cpu usage data table', exact: true }).click()
  await expect(page.getByRole('table', { name: 'CPU usage · %', exact: true })).toBeVisible()
  await page.getByRole('img', { name: /^CPU usage/ }).focus()
  await page.keyboard.press('ArrowLeft')
  await page.screenshot({ path: 'test-results/desktop-statistics.png', fullPage: true })
  await page.reload()
  await expect(page.getByRole('region', { name: 'Player activity', exact: true })).toContainText('1 successful joins')
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    // Chart coordinates adapt to the card so axis text stays readable on phones.
    const chart = page.getByRole('img', { name: /^CPU usage/ })
    await expect.poll(() => chart.evaluate(node => Math.abs((node as SVGSVGElement).viewBox.baseVal.width - node.getBoundingClientRect().width))).toBeLessThan(2)
  }
  await page.getByRole('button', { name: 'Appearance', exact: true }).click()
  await page.getByRole('menuitemradio', { name: 'Dark theme', exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.screenshot({ path: 'test-results/mobile-statistics-dark.png', fullPage: true })
  const user = await page.request.post('/api/users', { headers, data: { username: 'statistics-viewer', password: 'statistics-pass', temporary: false, permissions: { [id]: ['statistics_view'] } } })
  expect(user.status()).toBe(201)
  const account = (await user.json()).user
  const context = await browser.newContext(), memberPage = await context.newPage()
  try {
    await memberPage.goto('/login')
    await memberPage.getByLabel('Username', { exact: true }).fill('statistics-viewer')
    await memberPage.getByLabel('Password', { exact: true }).fill('statistics-pass')
    await memberPage.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(memberPage).toHaveURL(/\/servers$/)
    await memberPage.goto(`/servers/${id}/statistics`)
    await expect(memberPage.getByRole('heading', { name: 'Statistics', exact: true })).toBeVisible()
    await expect(memberPage.getByLabel('Collect player statistics', { exact: true })).toHaveCount(0)
    await memberPage.getByRole('tab', { name: 'Console', exact: true }).click()
    await expect(memberPage.getByText('Console access has not been granted for this server.')).toBeVisible()
    const servers = await (await page.request.get('/api/servers')).json()
    const other = servers.servers.find((server: { id: string }) => server.id !== id)
    if (other) expect((await memberPage.request.get(`/api/servers/${other.id}/statistics`)).status()).toBe(404)
    await page.request.put(`/api/users/${account.id}`, { headers, data: { username: 'statistics-viewer', permissions: { [id]: [] } } })
    await memberPage.reload()
    await expect(memberPage).toHaveURL(/\/login$/)
    await memberPage.getByLabel('Username', { exact: true }).fill('statistics-viewer')
    await memberPage.getByLabel('Password', { exact: true }).fill('statistics-pass')
    await memberPage.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(memberPage).toHaveURL(/\/servers$/)
    await memberPage.goto(`/servers/${id}/statistics`)
    await expect(memberPage).toHaveURL(new RegExp(`/servers/${id}/console$`))
    await expect(memberPage.getByRole('tab', { name: 'Statistics', exact: true })).toHaveCount(0)
  } finally { await context.close() }
  const stop = await page.request.post(`/api/servers/${id}/stop`, { headers, data: {} })
  expect(stop.status()).toBe(202)
  const stopJob = (await stop.json()).operation.id
  await expect.poll(async () => (await (await page.request.get(`/api/operations/${stopJob}`)).json()).operation.state).toBe('succeeded')
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByText('Server stopped', { exact: true })).toBeVisible()
  await expect(page.locator('.statistics-value').filter({ hasText: 'SERVER MEMORY' }).locator('strong')).toContainText('—')
  await expect(page.getByRole('img', { name: /^Memory usage/ })).toBeVisible()
  expect(errors).toEqual([])
})
