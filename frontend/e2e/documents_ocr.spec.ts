import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';
import { mockSchemesList } from './fixtures/mockData';

test.describe('Document Vault, OCR Extraction Engine & PII Masking', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('displays document checklist when scheme is selected', async ({ page }) => {
    await page.goto(`/documents?scheme_id=${mockSchemesList[0].id}`);

    // Checklist section appears
    await expect(page.locator('text=Aadhaar Card').first()).toBeVisible();
    await expect(page.locator('text=Land Records').first()).toBeVisible();
  });

  test('lists stored documents in citizen vault with sha256 checksums', async ({ page }) => {
    await page.goto('/documents');

    // Document vault items visible
    await expect(page.locator('text=aadhaar_card_masked.pdf')).toBeVisible();
    await expect(page.locator('text=khasra_khatauni.pdf')).toBeVisible();

    // Checksum prefix visible
    await expect(page.locator('text=SHA: e3b0c44298')).toBeVisible();
  });

  test('triggers OCR extraction, displays UIDAI PII masked fields and executes confirmation gate', async ({ page }) => {
    await page.goto('/documents');

    // Find and click OCR button on Aadhaar card
    const ocrBtn = page.locator('button[title*="OCR"]').first();
    await expect(ocrBtn).toBeVisible();
    await ocrBtn.click();

    // OCR Modal appears
    const modal = page.locator('.fixed.inset-0');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(/Extracted Document Details \(OCR\)|दस्तावेज़ से निकाले गए विवरण/i);

    // CRITICAL SECURITY ASSERTION: UIDAI PII Masking
    // Masked Aadhaar number must appear in the DOM
    await expect(modal).toContainText('XXXXXXXX1234');

    // Confidence badge is rendered
    await expect(modal).toContainText('96% Confidence');

    // Human-in-the-Loop Confirmation Gate
    const applyBtn = modal.getByRole('button', { name: /प्रोफ़ाइल में लागू करें \(पुष्टि करें\)|Apply to Profile \(Confirm\)/i });
    await expect(applyBtn).toBeVisible();
    await applyBtn.click();

    // Success feedback is presented
    await expect(modal).toContainText(/सफलतापूर्वक अपडेट|applied to citizen profile successfully/i);

    // Close modal
    const closeBtn = modal.getByRole('button', { name: /बंद करें|Close/i });
    await closeBtn.click();
    await expect(modal).not.toBeVisible();
  });
});
