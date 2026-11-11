import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';

test.describe('Conversational AI Assistant & Citizen Agency Gates', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await injectAuthSession(page);
  });

  test('displays initial assistant greeting in citizen preferred language', async ({ page }) => {
    await page.goto('/');

    // Verify assistant welcome bubble
    const welcomeBubble = page.locator('div').filter({ hasText: /नमस्ते|Hello/i }).first();
    await expect(welcomeBubble).toBeVisible();
  });

  test('sends citizen message via suggested question chips', async ({ page }) => {
    await page.goto('/');

    // Click suggested chip for PM-KISAN
    const chip = page.getByRole('button', { name: /पीएम किसान योजना की पात्रता क्या है\?|What is the eligibility for PM-KISAN\?/i });
    if (await chip.isVisible()) {
      await chip.click();
    } else {
      // Fallback to text input
      const input = page.locator('input[type="text"]').last();
      await input.fill('पीएम किसान योजना की पात्रता क्या है?');
      await page.locator('button[type="submit"]').click();
    }

    // Response bubble appears with reply text
    await expect(page.locator('text=नमस्ते रमेश जी!')).toBeVisible();
  });

  test('sends custom query and enforces Human-in-the-Loop confirmation gate', async ({ page }) => {
    await page.goto('/');

    const input = page.locator('input[type="text"]').last();
    await input.fill('कृपया मेरा आधार विवरण अपडेट करें');
    await page.locator('button[type="submit"]').click();

    // Verify Pending Action Card appears
    const actionCard = page.locator('div').filter({ hasText: /नागरिक पुष्टि की प्रतीक्षा है|Waiting for Citizen Confirmation/i }).first();
    await expect(actionCard).toBeVisible();

    // Verify Masked Aadhaar is presented inside the card
    await expect(actionCard).toContainText('XXXXXXXX1234');

    // Click "Confirm Action" button
    const confirmBtn = page.getByRole('button', { name: /पुष्टि करें|Confirm Action/i });
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Verify status updates to Confirmed & Applied
    await expect(page.locator('text=सत्यापित व सहेजा गया / Confirmed & Applied')).toBeVisible();
  });

  test('simulates speech recognition trigger on mic button click', async ({ page }) => {
    await page.goto('/');

    const micBtn = page.locator('button[title="Voice input"]');
    await expect(micBtn).toBeVisible();

    // Mock window.SpeechRecognition in browser
    await page.evaluate(() => {
      (window as any).SpeechRecognition = class MockSpeechRecognition {
        lang = 'hi-IN';
        onstart: any = null;
        onend: any = null;
        onerror: any = null;
        onresult: any = null;
        start() {
          if (this.onstart) this.onstart();
          setTimeout(() => {
            if (this.onresult) {
              this.onresult({
                results: [[{ transcript: 'पीएम किसान योजना' }]],
              });
            }
            if (this.onend) this.onend();
          }, 100);
        }
        stop() {
          if (this.onend) this.onend();
        }
      };
    });

    await micBtn.click();

    // Input field receives transcript from speech recognition
    const input = page.locator('input[type="text"]').last();
    await expect(input).toHaveValue(/पीएम किसान योजना/);
  });
});
