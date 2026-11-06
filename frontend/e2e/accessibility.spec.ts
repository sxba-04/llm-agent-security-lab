import { expect, test } from '@playwright/test';
import { audit, navigateTo, noPageOverflow } from './helpers';

for (const theme of ['light', 'dark'] as const) {
  test(`WCAG automated checks on core views in ${theme} theme`, async ({ page }, testInfo) => {
    await page.goto('/');
    await page.getByRole('combobox', { name: 'Farbschema', exact: true }).selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`overview-${theme}-desktop.png`), fullPage: true, animations: 'disabled' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: testInfo.outputPath(`overview-${theme}-mobile.png`), fullPage: true, animations: 'disabled' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await audit(page, testInfo, `overview-${theme}`);
    await navigateTo(page, 'Fälle');
    await expect(page.locator('.source-diff')).toBeVisible();
    await audit(page, testInfo, `cases-${theme}`);
    await navigateTo(page, 'Übersicht');
    await page.getByRole('button', { name: 'Neuer Mock-Versuch', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Neuen Mock-Versuch vorbereiten' })).toBeVisible();
    await audit(page, testInfo, `launch-${theme}`);
    await navigateTo(page, 'PDF-Quellen');
    await expect(page.getByLabel('PDF-Datei auswählen', { exact: true })).toBeVisible();
    await audit(page, testInfo, `documents-${theme}`);
  });
}

test('system preference tracks changes while explicit choice survives reload', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const picker = page.getByRole('combobox', { name: 'Farbschema', exact: true });
  await expect(picker).toHaveValue('system');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await picker.selectOption('dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(picker).toHaveValue('dark');
  expect(await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } })))
    .toEqual({ local: { 'security-lab.theme': 'dark' }, session: {} });
});

test('closed mobile navigation is absent from keyboard order; Escape restores trigger focus', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto('/');
  const menu = page.getByRole('button', { name: 'Menü öffnen', exact: true });
  await expect(menu).toBeVisible();
  // Start at the document, including the skip link, instead of clicking through the UI.
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Zum Inhalt springen' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(menu).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('link', { name: 'Übersicht', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toBeFocused();
  await expect(page.getByRole('navigation', { name: 'Hauptnavigation' })).toHaveCount(0);
  await page.keyboard.press('Enter');
  await page.getByRole('link', { name: 'Fälle', exact: true }).click();
  await expect(page.locator('#main-content')).toBeFocused();
  await noPageOverflow(page);
});
