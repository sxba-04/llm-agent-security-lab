import { expect, test, type Dialog, type Page } from '@playwright/test';
import { startCampaign } from './helpers';

test.beforeEach(async ({ browser, browserName }, testInfo) => {
  await testInfo.attach('unload-browser-version', {
    body: JSON.stringify({ engine: browserName, version: browser.version() }),
    contentType: 'application/json',
  });
});

async function createUnsavedReview(page: Page) {
  await page.goto('/');
  await startCampaign(page);
  await page.getByRole('button', { name: 'Bewertungssatz erstellen', exact: true }).click();
  await page.getByRole('textbox', { name: /^Dein Name/ }).fill('Technischer Browsertest');
  const notes = page.getByRole('textbox', { name: 'Begründung / Beobachtung', exact: true });
  // Real input establishes the user activation that browsers require for an unload prompt.
  await notes.click();
  await page.keyboard.type('Synthetischer Entwurf ohne wissenschaftliches Urteil.');
  const draft = await notes.inputValue();
  await expect(page.getByText('Ungespeicherte Änderungen', { exact: true })).toBeVisible();
  return { notes, draft };
}

// Exercise browser-generated unload prompts, not the separate SPA confirm dialog.
// Keep cancelled tab close and successful tab close on independent pages: each
// test observes one close attempt without inheriting a prior cancelled close.
test('unsaved review survives cancelled reload; saved review reloads and closes without a prompt', async ({ page }) => {
  const { notes, draft } = await createUnsavedReview(page);
  const reviewUrl = page.url();

  const reloadPrompt = page.waitForEvent('dialog', { timeout: 15000 });
  // Schedule a real reload after this evaluation returns, so a modal cannot block it.
  await page.evaluate(() => { setTimeout(() => window.location.reload(), 0); });
  const reloadDialog = await reloadPrompt;
  const reloadDialogType = reloadDialog.type();
  await reloadDialog.dismiss();
  expect(reloadDialogType).toBe('beforeunload');
  await expect(page).toHaveURL(reviewUrl);
  await expect(notes).toHaveValue(draft);
  await expect(page.getByText('Ungespeicherte Änderungen', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Bewertungen speichern', exact: true }).click();
  await expect(page.getByText('Entwurf gespeichert. Offene Felder bleiben unbewertet.')).toBeVisible();
  await expect(page.getByText('Gespeicherter Stand', { exact: true })).toBeVisible();
  const unexpectedDialogs: string[] = [];
  const dismissUnexpected = async (dialog: Dialog) => {
    unexpectedDialogs.push(dialog.type());
    await dialog.dismiss();
  };
  page.on('dialog', dismissUnexpected);
  try {
    await page.reload();
    await expect(notes).toHaveValue(draft);
    await expect(page.getByText('Gespeicherter Stand', { exact: true })).toBeVisible();
    expect(unexpectedDialogs).toEqual([]);
    // Activate the reloaded document without editing it; absence of a prompt must
    // reflect a clean form, not the browser's no-user-activation suppression.
    await notes.click();
    const closed = page.waitForEvent('close', { timeout: 15000 });
    await page.close({ runBeforeUnload: true });
    await closed;
    expect(unexpectedDialogs).toEqual([]);
  } finally {
    page.off('dialog', dismissUnexpected);
  }
});

test('unsaved review survives cancelled tab close', async ({ page }) => {
  const { notes, draft } = await createUnsavedReview(page);
  const reviewUrl = page.url();
  const closePrompt = page.waitForEvent('dialog', { timeout: 15000 });
  const closeAttempt = page.close({ runBeforeUnload: true });
  const closeDialog = await closePrompt;
  const closeDialogType = closeDialog.type();
  await closeDialog.dismiss();
  await closeAttempt;
  expect(closeDialogType).toBe('beforeunload');
  expect(page.isClosed()).toBe(false);
  await expect(page).toHaveURL(reviewUrl);
  await expect(notes).toHaveValue(draft);
  await expect(page.getByText('Ungespeicherte Änderungen', { exact: true })).toBeVisible();
});
