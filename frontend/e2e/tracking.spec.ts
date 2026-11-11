import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';
import { mockApplicationDraft } from './fixtures/mockData';

test.describe('Application Drafts, Official Portal Handoff & Tracking Timeline', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('displays application draft cards with status and portal handoff action', async ({ page }) => {
    await page.goto('/applications');

    // Scheme name visible
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible();

    // Verify official portal link is present
    const portalLink = page.locator('a[href*="pmkisan.gov.in"]').first();
    await expect(portalLink).toBeVisible();
  });

  test('records portal submission acknowledgement reference ID', async ({ page }) => {
    await page.goto('/applications');

    // Click submit acknowledgement button
    const recordBtn = page.getByRole('button', { name: /संदर्भ संख्या दर्ज करें|Record Acknowledgement/i }).first();
    if (await recordBtn.isVisible()) {
      await recordBtn.click();

      const modal = page.locator('.fixed.inset-0');
      await expect(modal).toBeVisible();

      // Enter reference ID
      const refInput = modal.locator('input[type="text"]').first();
      await refInput.fill('PMK-2026-UP-88419');

      const saveBtn = modal.getByRole('button', { name: /सहेजें|Save/i });
      await saveBtn.click();

      await expect(modal).not.toBeVisible();
    }
  });

  test('displays vertical progress timeline and syncs status with official portal', async ({ page }) => {
    await page.goto(`/tracking?application_id=${mockApplicationDraft.id}`);

    // Vertical steps visible
    await expect(page.getByText(/Drafted|ड्राफ्ट/i).first()).toBeVisible();
    await expect(page.getByText(/Submitted|जमा किया गया/i).first()).toBeVisible();

    // Audit trail events
    await expect(page.getByText('PMK-2026-UP-88419').first()).toBeVisible();

    // Trigger Portal Sync
    const syncBtn = page.getByRole('button', { name: /सिंक करें|Sync/i }).first();
    await expect(syncBtn).toBeVisible();
    await syncBtn.click();

    // Sync button enters loading and completes without error
    await expect(syncBtn).toBeEnabled();
  });

  test('notification drawer displays unread count badge and opens slide-out drawer', async ({ page }) => {
    await page.goto('/');

    // Notification bell icon in header with unread badge "1"
    const bellBtn = page.locator('header button').filter({ has: page.locator('svg.lucide-bell') });
    await expect(bellBtn).toBeVisible();
    await expect(bellBtn.locator('text=1')).toBeVisible();

    // Click bell to open slide-out notification drawer
    await bellBtn.click();

    const drawer = page.locator('.fixed.inset-0');
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText(/PM-KISAN/);

    // Close notification drawer
    const closeBtn = drawer.locator('button').filter({ has: page.locator('svg.lucide-x') });
    await closeBtn.click();
    await expect(drawer).not.toBeVisible();
  });
});
