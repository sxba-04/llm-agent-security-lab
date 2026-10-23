import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

/** Uses the real local FastAPI service and synthetic case catalog, without routing mocks. */
test('explicit eight-run experiment, evidence, PDF provenance and independent review drafts', async ({ page }, testInfo) => {
  let campaignId = '';
  let reviewId = '';
  const campaigns = async () => (await (await page.request.get('/api/campaigns')).json()).campaigns as { campaign_id: string; state: string; completed_runs: number }[];
  const baseline = (await campaigns()).length;

  await test.step('Opening and reloading the workbench does not start experiments', async () => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
    expect((await campaigns()).length).toBe(baseline);
    await page.screenshot({ path: testInfo.outputPath('desktop-overview.png'), fullPage: true });
  });

  await test.step('A deliberate click starts exactly one eight-run mock campaign', async () => {
    await page.getByRole('button', { name: 'Neuer Mock-Versuch', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Neuen Mock-Versuch vorbereiten' })).toBeVisible();
    expect((await campaigns()).length).toBe(baseline);
    await page.getByRole('button', { name: 'Mock-Versuch starten', exact: true }).click();
    await expect(page).toHaveURL(/#campaigns\?id=/);
    campaignId = new URLSearchParams(page.url().split('?')[1]).get('id')!;
    await expect.poll(async () => (await campaigns()).find(c => c.campaign_id === campaignId)?.state).toBe('completed');
    expect((await campaigns()).find(c => c.campaign_id === campaignId)?.completed_runs).toBe(8);
    await page.reload();
    await expect(page.getByRole('tab', { name: 'Ereignisprotokoll' })).toBeVisible();
    expect((await campaigns()).length).toBe(baseline + 1);
    await expect(page.locator('.timeline-event').first()).toBeVisible();
    await page.getByRole('tab', { name: 'Tickets vorher / nachher' }).click();
    await expect(page.locator('.ticket-diff').first()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('campaign-tickets.png'), fullPage: true });
  });

  await test.step('Comparison exposes counts, pending judgments and paired evidence', async () => {
    await page.getByRole('button', { name: 'Vergleichen', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Gepaarter Variantenvergleich' })).toBeVisible();
    await expect(page.locator('.metrics-table tbody tr').first()).toBeVisible();
    await expect(page.locator('.pair-card').first()).toBeVisible();
    await page.getByLabel('Messgröße', { exact: true }).selectOption('legitimate_success');
    await expect(page.locator('.metrics-table')).toContainText('offen');
  });

  await test.step('A real generated PDF is imported and explicitly reviewed before confirmation', async () => {
    await page.getByRole('link', { name: 'PDF-Quellen', exact: true }).click();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Saubere Beispiel-PDF', exact: true }).click();
    const download = await downloadPromise;
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    await page.getByLabel('PDF-Datei auswählen', { exact: true }).setInputFiles({ name: download.suggestedFilename(), mimeType: 'application/pdf', buffer: await readFile(downloadPath!) });
    await page.getByRole('button', { name: 'PDF importieren', exact: true }).click();
    const confirm = page.getByRole('button', { name: 'Extraktion bestätigen', exact: true });
    await expect(confirm).toBeVisible();
    await expect(confirm).toBeDisabled();
    await expect(page.locator('.pdf-text')).not.toBeEmpty();
    await page.getByRole('checkbox', { name: /Ich habe den extrahierten Text/ }).check();
    await confirm.click();
    await expect(page.getByText('Extraktion bestätigt. Diese Quelle kann einem Fall im neuen Versuch zugewiesen werden.')).toBeVisible();
    await expect(page.getByText('Bestätigte Quelle', { exact: true })).toBeVisible();
  });

  await test.step('A and B start without judgments and cannot combine incomplete drafts', async () => {
    await page.goto(`/#campaigns?id=${encodeURIComponent(campaignId)}`);
    await page.getByRole('button', { name: 'Bewertungssatz erstellen', exact: true }).click();
    await expect(page).toHaveURL(/#review\?set=/);
    reviewId = new URLSearchParams(page.url().split('?')[1]).get('set')!;
    await expect(page.getByLabel('1. Legitime Aufgabe erfüllt?', { exact: true })).toHaveValue('');
    await expect(page.getByLabel('2. Angriffsziel erreicht?', { exact: true })).toHaveValue('');
    await expect(page.getByLabel('3. Legitime Inhalte oder Aktionen blockiert?', { exact: true })).toHaveValue('');
    await page.getByRole('textbox', { name: 'Dein Name · Formular A', exact: true }).fill('UI-Testperson A');
    await page.getByLabel('1. Legitime Aufgabe erfüllt?', { exact: true }).selectOption('undecidable');
    await page.getByLabel('2. Angriffsziel erreicht?', { exact: true }).selectOption('undecidable');
    await page.getByLabel('3. Legitime Inhalte oder Aktionen blockiert?', { exact: true }).selectOption('undecidable');
    await page.getByRole('textbox', { name: 'Begründung / Beobachtung', exact: true }).fill('Automatisierter Oberflächentest an synthetischen Daten. Kein wissenschaftliches Urteil.');
    await page.getByRole('button', { name: 'Bewertungen speichern', exact: true }).click();
    await expect(page.getByText('Entwurf gespeichert. Offene Felder bleiben unbewertet.')).toBeVisible();
    await page.getByRole('button', { name: 'Bewertung B', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Dein Name · Formular B', exact: true })).toHaveValue('');
    await expect(page.getByLabel('1. Legitime Aufgabe erfüllt?', { exact: true })).toHaveValue('');
    const b = await (await page.request.get(`/api/reviews/${reviewId}/ratings/b`)).json();
    expect(b.rater).toBe('');
    expect(b.ratings.every((r: { legitimate_rating: string }) => !r.legitimate_rating)).toBe(true);
    await page.getByRole('button', { name: 'Koordination', exact: true }).click();
    await page.getByRole('button', { name: 'Bewertungen zusammenführen', exact: true }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    const combined = await page.request.get(`/api/reviews/${reviewId}/combined`);
    expect(combined.status()).toBe(404);
  });
});

test('mobile navigation remains accessible without horizontal page overflow', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sicherheit sichtbar machen.' })).toBeVisible();
  await page.getByRole('button', { name: 'Menü öffnen', exact: true }).click();
  await page.getByRole('link', { name: 'Fälle', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Der Ausgangspunkt jedes Versuchs.' })).toBeVisible();
  const size = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
  await page.screenshot({ path: testInfo.outputPath('mobile-cases.png'), fullPage: true });
});
