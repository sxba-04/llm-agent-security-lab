import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const cwd = fileURLToPath(new URL('..', import.meta.url));
const frontend = 'https://127.0.0.1:4173/llm-agent-security-lab/';

export default defineConfig({
  testDir: './e2e-hosted',
  testMatch: '**/*.spec.ts',
  outputDir: './test-results-hosted',
  timeout: 90000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-hosted', open: 'never' }]],
  use: {
    baseURL: frontend,
    actionTimeout: 15000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 1000 },
    // Only these disposable localhost fixtures use a self-signed certificate.
    ignoreHTTPSErrors: true,
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium', launchOptions: { executablePath: process.env.LAB_CHROMIUM_EXECUTABLE || undefined } } },
    { name: 'firefox', grep: /@smoke/, use: { browserName: 'firefox' } },
    { name: 'webkit', grep: /@smoke/, use: { browserName: 'webkit' } },
  ],
  webServer: [
    {
      cwd,
      command: 'uv run --locked --extra web python frontend/e2e-hosted/server.py api',
      url: 'https://127.0.0.1:8876/healthz',
      ignoreHTTPSErrors: true,
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      cwd,
      command: 'uv run --locked --extra web python frontend/e2e-hosted/server.py static',
      url: frontend,
      ignoreHTTPSErrors: true,
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
