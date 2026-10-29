import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const API = 'https://127.0.0.1:8876';
// Public synthetic fixture; never use this value for a deployment.
const TOKEN = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

async function login(page: Page) {
  await page.getByLabel('Zugangscode', { exact: true }).fill(TOKEN);
  await page.getByRole('button', { name: 'Werkbank öffnen', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
}

test('hosted access requires a token and keeps it out of browser storage', async ({ page }) => {
  const dataRequests: string[] = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) dataRequests.push(request.url());
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
