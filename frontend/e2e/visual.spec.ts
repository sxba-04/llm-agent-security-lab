import { expect, test } from '@playwright/test';

// The synthetic case has no changing timestamps or campaign data. Linux-only
// baselines avoid treating platform font differences as application regressions.
for (const theme of ['light', 'dark']) {
  test(`case source comparison visual reference: ${theme}`, async ({ page }) => {
    test.skip(process.platform !== 'linux', 'Reviewed baseline is for Linux Chromium only.');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/#cases?id=DEV-G1-01');
    await page.getByRole('combobox', { name: 'Farbschema', exact: true }).selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    const panel = page.locator('.panel').filter({ has: page.getByRole('heading', { name: 'Quellen im direkten Vergleich', exact: true }) });
    await expect(panel).toBeVisible();
    await expect(panel).toHaveScreenshot(`source-comparison-${theme}.png`, { animations: 'disabled', maxDiffPixelRatio: 0.002 });
  });
}
