import { test, expect } from '@playwright/test';
import { setupApiMocks, injectAuthSession } from './fixtures/testHelper';
import { mockUser } from './fixtures/mockData';

test.describe('Citizen Authentication & Session Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('unauthenticated visit to protected route redirects to /login', async ({ page }) => {
    await page.goto('/schemes');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('citizen registration flow succeeds and grants access', async ({ page }) => {
    await page.goto('/register');
    await page.fill('input[placeholder*="रमेश कुमार"]', 'Amit Sharma');
    await page.fill('input[type="email"]', 'new.citizen@example.com');
    await page.fill('input[type="password"]', 'ValidPassword123!');
    await page.click('button[type="submit"]');

    // Should navigate to authenticated home
    await expect(page).toHaveURL('/');
  });

  test('citizen login flow authenticates and stores JWT token in localStorage', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', mockUser.email);
    await page.fill('input[type="password"]', 'StrongCitizenPassword123!');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/');

    const token = await page.evaluate(() => localStorage.getItem('scheme_saathi_token'));
    expect(token).toBeTruthy();
    expect(token).toContain('mock-jwt-token');
  });

  test('logout clears citizen session and redirects to /login', async ({ page }) => {
    await injectAuthSession(page);
    await page.goto('/');

    // Locate logout button in header with Lucide LogOut icon
    const logoutBtn = page.locator('header button').filter({ has: page.locator('svg.lucide-log-out') });
    await expect(logoutBtn).toBeVisible();
    await logoutBtn.click();

    await expect(page).toHaveURL(/\/login/);
    const token = await page.evaluate(() => localStorage.getItem('scheme_saathi_token'));
    expect(token).toBeNull();
  });
});
