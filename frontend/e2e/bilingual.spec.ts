import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';

test.describe('Bilingual Localization & Language Switcher', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('default language renders Hindi Devanagari text and typography', async ({ page }) => {
    await page.goto('/');

    // Verify brand title in Hindi Devanagari
    const brand = page.locator('header');
    await expect(brand).toContainText('योजना साथी');
  });

  test('clicking language switcher toggles between Hindi and English', async ({ page }) => {
    await page.goto('/');

    // Locate language switcher button in header
    const langBtn = page.locator('header button[title="Toggle Hindi / English"]');
    await expect(langBtn).toBeVisible();

    // Currently Hindi -> Click to toggle to English
    await langBtn.click();
    const brand = page.locator('header');
    await expect(brand).toContainText('Scheme Saathi');

    // Click again to toggle back to Hindi
    await langBtn.click();
    await expect(brand).toContainText('योजना साथी');
  });

  test('language preference persists in localStorage across page reloads', async ({ page }) => {
    await page.goto('/');

    const langBtn = page.locator('header button[title="Toggle Hindi / English"]');
    await langBtn.click();

    // Assert English is active
    await expect(page.locator('header')).toContainText('Scheme Saathi');

    // Reload page
    await page.reload();

    // Must still be in English after reload
    await expect(page.locator('header')).toContainText('Scheme Saathi');
    const storedLang = await page.evaluate(() => localStorage.getItem('scheme_saathi_lang'));
    expect(storedLang).toBe('en');
  });
});
