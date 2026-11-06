import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, type TestInfo } from '@playwright/test';
import { readFile } from 'node:fs/promises';

export async function noPageOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
}

export async function audit(page: Page, testInfo: TestInfo, name: string) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  await testInfo.attach(`accessibility-${name}`, { body: JSON.stringify(results, null, 2), contentType: 'application/json' });
  expect(results.violations, `${name}: ${results.violations.map(item => `${item.id}: ${item.help}`).join('; ')}`).toEqual([]);
}

export async function navigateTo(page: Page, name: string) {
  const menu = page.getByRole('button', { name: 'Menü öffnen', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('link', { name, exact: true }).click();
}

export async function startCampaign(page: Page) {
  await page.getByRole('button', { name: 'Neuer Mock-Versuch', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Neuen Mock-Versuch vorbereiten' })).toBeVisible();
  await page.getByRole('button', { name: 'Mock-Versuch starten', exact: true }).click();
  await expect(page).toHaveURL(/#campaigns\?id=/);
  await expect(page.getByText('Versuch beendet', { exact: true })).toBeVisible();
  await expect(page.locator('.timeline-event').first()).toBeVisible();
  return new URLSearchParams(page.url().split('?')[1]).get('id')!;
}

export async function importSamplePdf(page: Page) {
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Saubere Beispiel-PDF', exact: true }).click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  await page.getByLabel('PDF-Datei auswählen', { exact: true }).setInputFiles({
    name: download.suggestedFilename(), mimeType: 'application/pdf', buffer: await readFile(downloadPath!),
  });
  await page.getByRole('button', { name: 'PDF importieren', exact: true }).click();
  const confirm = page.getByRole('button', { name: 'Extraktion bestätigen', exact: true });
  await expect(confirm).toBeDisabled();
  await expect(page.locator('.pdf-text')).not.toBeEmpty();
  await page.getByRole('checkbox', { name: /Ich habe den extrahierten Text/ }).check();
  await confirm.click();
  await expect(page.getByText('Bestätigte Quelle', { exact: true })).toBeVisible();
}

export async function archiveDownload(page: Page) {
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Archiv herunterladen', exact: true }).click();
  const archive = await downloadPromise;
  const path = await archive.path();
  expect(path).toBeTruthy();
  expect((await readFile(path!)).subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]));
}
