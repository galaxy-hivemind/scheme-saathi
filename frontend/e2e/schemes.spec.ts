import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';
import { mockSchemesList, mockEligibilityResult } from './fixtures/mockData';

test.describe('Welfare Scheme Discovery & Eligibility Evaluation', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('renders verified 2026 central government welfare schemes catalogue', async ({ page }) => {
    await page.goto('/schemes');

    // Assert page header
    await expect(page.locator('h1')).toContainText(/योजनाएं|Schemes/i);

    // Assert scheme cards exist
    const schemeCard = page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first();
    await expect(schemeCard).toBeVisible();

    // Verify 2026 badge
    const badge = page.locator('text=2026').first();
    await expect(badge).toBeVisible();
  });

  test('filters schemes by search keyword', async ({ page }) => {
    await page.goto('/schemes');

    const searchInput = page.locator('input[type="text"]').first();
    await searchInput.fill('Awas');

    // Verify PMAY is shown
    await expect(page.locator('text=Pradhan Mantri Awas Yojana').first()).toBeVisible();
  });

  test('filters schemes by category pills (Agriculture, Housing, Health)', async ({ page }) => {
    await page.goto('/schemes');

    // Click Agriculture category button
    const agriBtn = page.getByRole('button', { name: /कृषि|Agriculture/i });
    await agriBtn.click();
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible();

    // Click Housing category button
    const housingBtn = page.getByRole('button', { name: /आवास|Housing/i });
    await housingBtn.click();
    await expect(page.locator('text=Pradhan Mantri Awas Yojana').first()).toBeVisible();
  });

  test('opens quick eligibility evaluation modal and displays evaluation breakdown', async ({ page }) => {
    await page.goto('/schemes');

    // Click Check Eligibility button on PM-KISAN card
    const checkBtn = page.getByRole('button', { name: /पात्रता जांचें|Check Eligibility/i }).first();
    await checkBtn.click();

    // Modal dialog appears
    const modal = page.locator('.fixed.inset-0');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(/पात्र \(Eligible\)|Eligible/i);
    await expect(modal).toContainText(/पूरी की गई शर्तें|Matched/i);

    // Close modal
    const closeBtn = modal.locator('button').filter({ has: page.locator('svg.lucide-x') });
    await closeBtn.click();
    await expect(modal).not.toBeVisible();
  });

  test('navigates to scheme details page and inspects criteria', async ({ page }) => {
    await page.goto(`/schemes/${mockSchemesList[0].id}`);

    // Verify scheme title
    await expect(page.locator('h1')).toContainText('Pradhan Mantri Kisan Samman Nidhi');

    // Verify ministry name
    await expect(page.locator('body')).toContainText('Ministry of Agriculture and Farmers Welfare');

    // Verify benefits DBT amount
    await expect(page.locator('body')).toContainText('6,000');
  });
});
