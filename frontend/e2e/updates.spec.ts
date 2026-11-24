import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
const { version } = JSON.parse(readFileSync(new URL('../../beammpy/version.json', import.meta.url), 'utf8'))

test.use({ baseURL: 'http://127.0.0.1:8792' })

const windows = 'iwr -useb https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.ps1 | iex'
const ubuntu = 'curl -fsSL https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh | sh'

test('update indicator, host commands, clipboard, keyboard, drawer, themes and silent failures', async ({ page, context }) => {
  test.setTimeout(90000)
  page.setDefaultTimeout(10000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const bootstrap = await (await page.request.get('/api/auth/session')).json()
  const login = await page.request.post(`/api/auth/${bootstrap.setup_required ? 'setup' : 'login'}`, {
    headers: { 'X-CSRF-Token': bootstrap.csrf_token }, data: { username: 'admin', password: 'setup888' },
  })
  expect(login.ok()).toBe(true)
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  let info = { installed_version: version, available_version: '9.0.0', update_available: true,
    status: 'available', host_os: 'windows', command: windows }
  await page.route('**/api/panel/update', route => route.fulfill({ json: info }))
  await page.goto('/servers')
  await expect(page.locator('.version-label')).toHaveText(`BeamMPY · v${version}`)
  const indicator = page.getByRole('button', { name: 'Update available', exact: true })
  const dialog = page.getByRole('alertdialog', { name: 'BeamMPY update available' })
  await expect(indicator).toBeVisible()
  await expect(dialog).not.toBeVisible() // Never opens automatically.
  await indicator.focus()
  await expect(page.locator('m3e-tooltip[open]')).toContainText('Update available')
  const row = await page.locator('.version-label').boundingBox(), icon = await indicator.boundingBox()
  expect(icon!.x).toBeGreaterThan(row!.x + row!.width)
  expect(icon!.height).toBeLessThanOrEqual(48)
  await page.keyboard.press('Enter')
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText(`v${version}`)
  await expect(dialog).toContainText('v9.0.0')
  await expect(dialog).toContainText('same installation folder')
  await expect(dialog).toContainText('back up')
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press('Tab')
    expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true)
  }
  await dialog.getByRole('button', { name: 'Copy command' }).click()
  await expect(dialog.getByRole('status')).toHaveText('Update command copied.')
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(windows)
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(indicator).toBeFocused()

  for (const [host, command] of [['windows', windows], ['linux', ubuntu]]) {
    info = { ...info, host_os: host, command }
    for (const mode of ['light', 'dark']) {
      // The host supplied by the API selects the command, regardless of this
      // browser's platform. Test both commands on the same browser instance.
      await page.setViewportSize({ width: 1280, height: 900 })
      await page.reload()
      await page.getByRole('button', { name: 'Appearance', exact: true }).click()
      await page.getByRole('menuitemradio', { name: mode === 'light' ? 'Light theme' : 'Dark theme', exact: true }).click()
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 844 })
        await page.getByRole('button', { name: 'Toggle navigation' }).click()
        await expect(indicator).toBeVisible()
        await indicator.focus()
        await page.keyboard.press('Space')
        await expect(dialog).toBeVisible()
        await expect(dialog.getByLabel('Manual update command')).toHaveText(command)
        await expect(dialog).toContainText(host === 'windows' ? 'Windows panel host' : 'Ubuntu panel host')
        await expect(dialog).toContainText(host === 'windows' ? 'Start BeamMPY.bat' : 'systemd service')
        const box = await dialog.boundingBox()
        expect(box!.x).toBeGreaterThanOrEqual(0)
        expect(box!.x + box!.width).toBeLessThanOrEqual(width)
        expect(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true)
        await dialog.getByRole('button', { name: 'Copy command' }).click()
        expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(command)
        if (width === 320 && host === 'linux') await page.screenshot({ path: `test-results/update-${mode}-mobile.png`, fullPage: true })
        await dialog.getByRole('button', { name: 'Close', exact: true }).click()
        await expect(dialog).not.toBeVisible()
        await expect(indicator).toBeFocused()
        await page.keyboard.press('Escape') // Close the containing mobile drawer.
        await expect(page.getByRole('button', { name: 'Toggle navigation' })).toBeFocused()
      }
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.reload()
  await indicator.click()
  // Exercise the LAN HTTP path with Clipboard API unavailable, while retaining
  // a reference for checking what the browser's copy command put on clipboard.
  await page.evaluate(() => {
    ;(window as any).testClipboard = navigator.clipboard
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined })
  })
  await dialog.getByRole('button', { name: 'Copy command' }).click()
  await expect(dialog.getByRole('status')).toHaveText('Update command copied.')
  expect(await page.evaluate(() => (window as any).testClipboard.readText())).toBe(ubuntu)
  await page.evaluate(() => { document.execCommand = () => false })
  await dialog.getByRole('button', { name: 'Copy command' }).click()
  await expect(dialog.getByRole('status')).toContainText('copy it manually')
  await page.keyboard.press('Escape')

  for (const status of ['current', 'unavailable', 'checking']) {
    info = { ...info, status, update_available: false }
    await page.reload()
    await expect(page.getByRole('heading', { name: 'All servers.' })).toBeVisible()
    await expect(indicator).toHaveCount(0)
    await expect(dialog).not.toBeVisible()
  }
  await page.unroute('**/api/panel/update')
  await page.route('**/api/panel/update', route => route.abort())
  await page.reload()
  await expect(page.getByRole('heading', { name: 'All servers.' })).toBeVisible()
  await expect(indicator).toHaveCount(0)
  await expect(page.locator('m3e-snackbar-host')).not.toContainText('update')
  expect(errors).toEqual([])
})
