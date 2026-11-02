import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const API = 'https://127.0.0.1:8876';
// Public synthetic fixture; never use this value for a deployment.
const TOKEN = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

async function login(page: Page) {
  await page.getByLabel('Zugangscode', { exact: true }).fill(TOKEN);
  await page.getByRole('button', { name: 'Werkbank öffnen', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
  await expect(page.getByRole('note', { name: 'Flüchtiger Testbetrieb' })).toContainText('Daten werden nicht dauerhaft gespeichert');
}

test('hosted access requires a token and keeps it out of browser storage', async ({ page }) => {
  const dataRequests: string[] = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/api/') && path !== '/api/auth/config') dataRequests.push(request.url());
  });
  await page.goto('./');
  await expect(page.getByLabel('Zugangscode', { exact: true })).toBeVisible();
  expect(dataRequests).toEqual([]);
  const denied = await page.request.get(`${API}/api/cases`);
  expect(denied.status()).toBe(401);
  await page.getByLabel('Zugangscode', { exact: true }).fill('invalid_synthetic_browser_test_token_20261029_only');
  await page.getByRole('button', { name: 'Werkbank öffnen', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toHaveCount(0);
  await login(page);
  await expect.poll(() => dataRequests.some(url => url === `${API}/api/cases`)).toBe(true);
  expect(dataRequests.every(url => new URL(url).origin === API)).toBe(true);
  expect(await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } })))
    .toEqual({ local: {}, session: {} });
  await page.getByRole('button', { name: 'Abmelden', exact: true }).click();
  await expect(page.getByLabel('Zugangscode', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toHaveCount(0);
  await login(page);
  await page.reload();
  await expect(page.getByLabel('Zugangscode', { exact: true })).toBeVisible();
});

test('GitHub callback, identity, own-session revocation and logout work across HTTPS origins', async ({ page, context }, testInfo) => {
  await context.route('https://github.com/login/oauth/authorize?*', async route => {
    const request = new URL(route.request().url());
    expect(request.searchParams.get('code_challenge_method')).toBe('S256');
    expect(request.searchParams.get('scope')).toBe('');
    const callback = new URL(request.searchParams.get('redirect_uri')!);
    callback.search = new URLSearchParams({ code: 'browser-approved-code', state: request.searchParams.get('state')! }).toString();
    await route.fulfill({ status: 302, headers: { location: callback.href } });
  });
  await page.goto('./');
  await page.getByRole('button', { name: 'Mit GitHub anmelden', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
  await expect(page).not.toHaveURL(/[?&](code|state)=/);
  await expect(page.getByRole('button', { name: '@browser-researcher', exact: true })).toBeVisible();
  expect(await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }))).toEqual({ local: {}, session: {} });

  const other = await context.newPage();
  let otherAuthorization = '';
  other.on('request', request => {
    if (request.url() === `${API}/api/health`) otherAuthorization = request.headers()['authorization'] || '';
  });
  await other.goto('https://127.0.0.1:4173/llm-agent-security-lab/');
  await other.getByRole('button', { name: 'Mit GitHub anmelden', exact: true }).click();
  await expect(other.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
  expect(otherAuthorization).toMatch(/^Bearer [A-Za-z0-9_-]{43,128}$/);
  await page.getByRole('button', { name: '@browser-researcher', exact: true }).click();
  await expect(page.getByText('Weitere Sitzung', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Beenden', exact: true }).click();
  await expect(page.getByText('Weitere Sitzung', { exact: true })).toHaveCount(0);
  const revoked = await page.request.get(`${API}/api/cases`, { headers: { Authorization: otherAuthorization } });
  expect(revoked.status()).toBe(401);
  await other.close();
  await page.screenshot({ path: testInfo.outputPath('github-sessions.png'), fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'Hier abmelden', exact: true }).click();
  await expect(page.getByLabel('Zugangscode', { exact: true })).toBeVisible();
});

test('an unapproved GitHub account stays outside the workbench with access-code recovery available', async ({ page }) => {
  await page.route('https://github.com/login/oauth/authorize?*', async route => {
    const request = new URL(route.request().url());
    const callback = new URL(request.searchParams.get('redirect_uri')!);
    callback.search = new URLSearchParams({ code: 'browser-unapproved-code', state: request.searchParams.get('state')! }).toString();
    await route.fulfill({ status: 302, headers: { location: callback.href } });
  });
  await page.goto('./');
  await page.getByRole('button', { name: 'Mit GitHub anmelden', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('nicht');
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toHaveCount(0);
  await expect(page).not.toHaveURL(/[?&](code|state)=/);
  await login(page);
});

test('cross-origin PDFs, confirmed import, mock campaign and authenticated archive work', async ({ page }, testInfo) => {
  const incorrectOriginRequests: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/') && url.origin !== API) incorrectOriginRequests.push(url.href);
  });
  await page.goto('./');
  await login(page);
  await page.getByRole('link', { name: 'Fälle', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Der Ausgangspunkt jedes Versuchs.' })).toBeVisible();
  await expect(page.locator('.case-item')).toHaveCount(12);
  await page.getByRole('link', { name: 'PDF-Quellen', exact: true }).click();
  const pdfDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Saubere Beispiel-PDF', exact: true }).click();
  const pdf = await pdfDownload;
  const pdfPath = await pdf.path();
  expect(pdfPath).toBeTruthy();
  const bytes = await readFile(pdfPath!);
  expect(bytes.subarray(0, 5).toString()).toBe('%PDF-');
  expect(bytes.length).toBeGreaterThan(500);
  await page.getByLabel('PDF-Datei auswählen', { exact: true }).setInputFiles({
    name: pdf.suggestedFilename(), mimeType: 'application/pdf', buffer: bytes,
  });
  await page.getByRole('button', { name: 'PDF importieren', exact: true }).click();
  const confirm = page.getByRole('button', { name: 'Extraktion bestätigen', exact: true });
  await expect(confirm).toBeVisible();
  await expect(confirm).toBeDisabled();
  await expect(page.locator('.pdf-text')).not.toBeEmpty();
  await page.getByRole('checkbox', { name: /Ich habe den extrahierten Text/ }).check();
  await confirm.click();
  await expect(page.getByText('Bestätigte Quelle', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Übersicht', exact: true }).click();
  await page.getByRole('button', { name: 'Neuer Mock-Versuch', exact: true }).click();
  await page.getByRole('button', { name: 'Mock-Versuch starten', exact: true }).click();
  await expect(page).toHaveURL(/#campaigns\?id=/);
  await expect(page.getByText('Versuch beendet', { exact: true })).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Versuchsfortschritt' })).toHaveAttribute('value', '8');
  await expect(page.locator('.timeline-event').first()).toBeVisible();
  const archiveDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Archiv herunterladen', exact: true }).click();
  const archive = await archiveDownload;
  const archivePath = await archive.path();
  expect(archivePath).toBeTruthy();
  const zipped = await readFile(archivePath!);
  expect(zipped.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]));
  expect(zipped.length).toBeGreaterThan(1000);
  expect(incorrectOriginRequests).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('hosted-campaign.png'), fullPage: true, animations: 'disabled' });
});
