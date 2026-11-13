import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'

const localPython = path.resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python')
const python = process.env.BEAMMPY_TEST_PYTHON || (existsSync(localPython) ? localPython : 'python')

export default defineConfig({
  testDir: './e2e', workers: 1, fullyParallel: false, timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:8791', browserName: 'chromium', trace: 'retain-on-failure' },
  // Keep independent feature scenarios out of the serial account suite's
  // login-attempt window; production throttling is exercised without overrides.
  webServer: [8791, 8792].map(port => ({
    command: `"${python}" ../tests/e2e_server.py ${port}`,
    url: `http://127.0.0.1:${port}/api/auth/session`,
    reuseExistingServer: false, timeout: 30000,
  })),
})
