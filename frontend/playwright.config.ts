import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'

const localPython = path.resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python')
const python = process.env.BEAMMPY_TEST_PYTHON || (existsSync(localPython) ? localPython : 'python')

export default defineConfig({
  testDir: './e2e', workers: 1, fullyParallel: false, timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:8791', browserName: 'chromium', trace: 'retain-on-failure' },
  webServer: {
    command: `"${python}" ../tests/e2e_server.py`,
    url: 'http://127.0.0.1:8791/api/auth/session',
    reuseExistingServer: false, timeout: 30000,
  },
})
