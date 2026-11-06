import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  testDir: './e2e',
  timeout: 90000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    actionTimeout: 15000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 1000 },
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium', launchOptions: { executablePath: process.env.LAB_CHROMIUM_EXECUTABLE || undefined } } },
    { name: 'firefox', testMatch: '**/*.smoke.spec.ts', use: { browserName: 'firefox' } },
    { name: 'webkit', testMatch: '**/*.smoke.spec.ts', use: { browserName: 'webkit' } },
  ],
  webServer: {
    cwd: fileURLToPath(new URL('..', import.meta.url)),
    command: 'uv run --locked --extra web python frontend/e2e/server.py',
    url: 'http://127.0.0.1:8765/api/health',
    reuseExistingServer: false,
    timeout: 60000,
  },
});
