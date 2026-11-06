import { expect, test } from '@playwright/test';
import { archiveDownload, noPageOverflow, startCampaign } from './helpers';

// Full application + actual FastAPI backend. No real provider calls or data.
test('keyboard tabs, independent review draft and archive work across browser engines', async ({ page }) => {
  await page.goto('/');
  const campaign = await startCampaign(page);
  const trace = page.getByRole('tab', { name: 'Ereignisprotokoll', exact: true });
  await trace.focus();
  await page.keyboard.press('ArrowRight');
  const tickets = page.getByRole('tab', { name: 'Tickets vorher / nachher', exact: true });
  await expect(tickets).toBeFocused();
  await expect(tickets).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tabpanel', { name: 'Tickets vorher / nachher', exact: true })).toBeVisible();
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: 'Aufgabe & Quelle', exact: true })).toBeFocused();
  await page.keyboard.press('Home');
  await expect(trace).toBeFocused();
  await archiveDownload(page);
  await page.getByRole('button', { name: 'Bewertungssatz erstellen', exact: true }).click();
  await expect(page.getByLabel('1. Legitime Aufgabe erfüllt?', { exact: true })).toHaveValue('');
  await page.getByRole('textbox', { name: 'Dein Name · Formular A', exact: true }).fill('Synthetischer Browsertest');
  const notes = page.getByRole('textbox', { name: 'Begründung / Beobachtung', exact: true });
  await notes.fill('Technischer Entwurf ohne wissenschaftliches Urteil.');
  await page.getByRole('button', { name: 'Bewertungen speichern', exact: true }).click();
  await expect(page.getByText('Entwurf gespeichert. Offene Felder bleiben unbewertet.')).toBeVisible();
  await page.reload();
  await expect(notes).toHaveValue('Technischer Entwurf ohne wissenschaftliches Urteil.');
  await page.getByRole('button', { name: 'Bewertung B', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Dein Name · Formular B', exact: true })).toHaveValue('');
  await expect(notes).toHaveValue('');
  await page.goto(`/#campaigns?id=${encodeURIComponent(campaign)}`);
  await page.setViewportSize({ width: 390, height: 600 });
  await noPageOverflow(page);
});
