import { expect, test } from '@playwright/test';
import { archiveDownload, audit, importSamplePdf, navigateTo, noPageOverflow, startCampaign } from './helpers';

for (const width of [320, 390, 768, 1440]) {
  test(`PDF to mock evidence, comparison, rating and archive at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
    await noPageOverflow(page);
    await navigateTo(page, 'Fälle');
    await expect(page.getByRole('heading', { name: 'Der Ausgangspunkt jedes Versuchs.' })).toBeVisible();
    await noPageOverflow(page);
    await navigateTo(page, 'PDF-Quellen');
    await importSamplePdf(page);
    await noPageOverflow(page);
    await navigateTo(page, 'Übersicht');
    const campaign = await startCampaign(page);
    await noPageOverflow(page);
    await page.getByRole('button', { name: 'Vergleichen', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Gepaarter Variantenvergleich' })).toBeVisible();
    await expect(page.locator('.metrics-table tbody tr').first()).toBeVisible();
    await noPageOverflow(page);
    if (width === 390) await audit(page, testInfo, 'mobile-comparison');
    await page.goto(`/#campaigns?id=${encodeURIComponent(campaign)}`);
    await page.getByRole('button', { name: 'Bewertungssatz erstellen', exact: true }).click();
    const notes = page.getByRole('textbox', { name: 'Begründung / Beobachtung', exact: true });
    await expect(notes).toBeVisible();
    // Reduced height checks constrained layout, not a native software keyboard.
    await page.setViewportSize({ width, height: 420 });
    await notes.fill('Automatisierter technischer Entwurf, keine menschliche Studienbewertung.');
    await expect(notes).toBeFocused();
    await expect(notes).toBeInViewport();
    await noPageOverflow(page);
    if (width === 390) await audit(page, testInfo, 'mobile-review');
    await page.getByRole('textbox', { name: 'Dein Name · Formular A', exact: true }).fill('Browserprüfung');
    await page.getByRole('button', { name: 'Bewertungen speichern', exact: true }).click();
    await expect(page.getByText('Entwurf gespeichert. Offene Felder bleiben unbewertet.')).toBeVisible();
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`/#campaigns?id=${encodeURIComponent(campaign)}`);
    await archiveDownload(page);
    await noPageOverflow(page);
    await page.screenshot({ path: testInfo.outputPath(`campaign-${width}.png`), fullPage: true, animations: 'disabled' });
  });
}
