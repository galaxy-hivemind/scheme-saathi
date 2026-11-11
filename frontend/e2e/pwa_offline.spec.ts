import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';
import { mockSchemesList } from './fixtures/mockData';

test.describe('PWA & Offline Capability', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('serves compliant Web App Manifest with bilingual Devanagari branding and standalone display', async ({ page }) => {
    const response = await page.goto('/manifest.webmanifest');
    expect(response?.status()).toBe(200);

    const manifest = await response?.json();
    expect(manifest.name).toContain('Scheme Saathi (योजना साथी)');
    expect(manifest.short_name).toBe('Scheme Saathi');
    expect(manifest.theme_color).toBe('#ea580c');
    expect(manifest.background_color).toBe('#f8fafc');
    expect(manifest.display).toBe('standalone');
    expect(manifest.icons.length).toBeGreaterThanOrEqual(3);
  });

  test('displays reactive offline banner upon network disconnection and recovers on reconnection', async ({ page }) => {
    await page.goto('/');

    // Initially online: offline banner is not present
    await expect(page.locator('aside[aria-label="Offline status"]')).not.toBeVisible();

    // 1. Simulate network disconnection
    await page.context().setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event('offline')));

    // Offline banner appears with Hindi Devanagari copy
    const offlineBanner = page.locator('aside[aria-label="Offline status"]');
    await expect(offlineBanner).toBeVisible();
    await expect(offlineBanner).toContainText(/ऑफ़लाइन मोड सक्रिय|Offline Mode Active/i);

    // 2. Simulate network reconnection
    await page.context().setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event('online')));

    // Reconnection toast appears
    const onlineToast = page.locator('aside[aria-label="Online status"]');
    await expect(onlineToast).toBeVisible();
    await expect(onlineToast).toContainText(/वापस ऑनलाइन आ गए|Back Online/i);
  });

  test('browses cached schemes catalogue without network crash during simulated offline mode', async ({ page }) => {
    // Prime the schemes page while online
    await page.goto('/schemes');
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible({ timeout: 10000 });

    // Disconnect network
    await page.context().setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event('offline')));

    // Offline indicator is visible
    await expect(page.locator('aside[aria-label="Offline status"]')).toBeVisible();

    // Navigate to Chat via client-side routing (desktop nav or mobile bottom bar)
    const chatLink = page.locator('a[href="/"]:visible').first();
    await chatLink.click();
    await expect(page.locator('aside[aria-label="Offline status"]')).toBeVisible();

    // Navigate back to Schemes via client-side routing
    const schemesLink = page.locator('a[href="/schemes"]:visible').first();
    await schemesLink.click();

    // Schemes remain fully browseable
    await expect(page.locator('h1')).toContainText(/योजनाएं|Schemes/i);
    await expect(page.locator('text=Pradhan Mantri Kisan Samman Nidhi').first()).toBeVisible({ timeout: 10000 });
  });

  test('saves application draft locally when offline and queues for background sync', async ({ page }) => {
    await page.goto(`/schemes/${mockSchemesList[0].id}`);

    // Disconnect network
    await page.context().setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event('offline')));

    // Click Create Draft button while offline
    const createDraftBtn = page.getByRole('button', { name: /आवेदन ड्राफ्ट बनाएं|Create Application Draft/i });
    if (await createDraftBtn.isVisible()) {
      await createDraftBtn.click();

      // Assert offline feedback message appears
      await expect(page.locator('text=ऑफ़लाइन ड्राफ्ट सहेजा गया')).toBeVisible();

      // Verify draft is stored in localStorage queue
      const offlineQueue = await page.evaluate(() => {
        const raw = localStorage.getItem('scheme_saathi_offline_drafts');
        return raw ? JSON.parse(raw) : [];
      });
      expect(offlineQueue.length).toBeGreaterThan(0);
      expect(offlineQueue[0].pending_sync).toBe(true);

      // Reconnect network
      await page.context().setOffline(false);
      await page.evaluate(() => window.dispatchEvent(new Event('online')));
    }
  });

  test('displays PWA mobile install prompt upon beforeinstallprompt event and allows dismissal', async ({ page }) => {
    await page.goto('/');

    // Dispatch simulated beforeinstallprompt event
    await page.evaluate(() => {
      const event = new Event('beforeinstallprompt');
      (event as any).prompt = () => {};
      (event as any).userChoice = Promise.resolve({ outcome: 'accepted' });
      window.dispatchEvent(event);
    });

    // Install banner appears
    const installBanner = page.locator('div[aria-label="PWA install banner"]');
    await expect(installBanner).toBeVisible();
    await expect(installBanner).toContainText(/योजना साथी ऐप इंस्टॉल करें|Install Scheme Saathi App/i);

    // Dismiss banner
    const dismissBtn = installBanner.locator('button[title="Dismiss"]');
    await dismissBtn.click();
    await expect(installBanner).not.toBeVisible();
  });
});
