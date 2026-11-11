import { test, expect } from '@playwright/test';
import { setupApiMocks, loginViaUI } from './fixtures/testHelper';
import { mockSchemesList } from './fixtures/mockData';

test.describe('End-to-End Citizen Journey Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('executes complete citizen lifecycle from login through scheme discovery, OCR, application handoff, and tracking', async ({ page }) => {
    // 1. Citizen Sign In
    await loginViaUI(page);
    await expect(page).toHaveURL('/');

    // 2. Discover Schemes
    await page.goto('/schemes');
    await expect(page.locator('h1')).toContainText(/योजनाएं|Schemes/i);
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible();

    // 3. Evaluate Eligibility on PM-KISAN
    const checkBtn = page.getByRole('button', { name: /पात्रता जांचें|Check Eligibility/i }).first();
    await checkBtn.click();
    const modal = page.locator('.fixed.inset-0');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(/पात्र \(Eligible\)|Eligible/i);
    const closeModalBtn = modal.locator('button').filter({ has: page.locator('svg.lucide-x') });
    await closeModalBtn.click();

    // 4. Conversational AI Assistant
    await page.goto('/');
    const chatInput = page.locator('input[type="text"]').last();
    await chatInput.fill('क्या मैं पीएम किसान के लिए पात्र हूँ?');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('text=नमस्ते रमेश जी!')).toBeVisible();

    // 5. Document Vault & PII-Masked OCR
    await page.goto('/documents');
    await expect(page.locator('text=aadhaar_card_masked.pdf')).toBeVisible();
    const ocrBtn = page.locator('button[title*="OCR"]').first();
    await ocrBtn.click();
    const ocrModal = page.locator('.fixed.inset-0');
    await expect(ocrModal).toBeVisible();
    // Security check: UIDAI PII Masking
    await expect(ocrModal).toContainText('XXXXXXXX1234');
    const closeOcrBtn = ocrModal.getByRole('button', { name: /बंद करें|Close/i });
    await closeOcrBtn.click();

    // 6. Application Draft & Official Portal Handoff
    await page.goto('/applications');
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible();
    const portalLink = page.locator('a[href*="pmkisan.gov.in"]').first();
    await expect(portalLink).toBeVisible();

    // 7. Track Application Timeline
    await page.goto('/tracking');
    await expect(page.locator('text=PMK-2026-UP-88419').first()).toBeVisible();

    // 8. Bilingual Switcher verification
    const langBtn = page.locator('header button[title="Toggle Hindi / English"]');
    await langBtn.click();
    await expect(page.locator('header')).toContainText('Scheme Saathi');
    await langBtn.click();
    await expect(page.locator('header')).toContainText('योजना साथी');
  });
});
