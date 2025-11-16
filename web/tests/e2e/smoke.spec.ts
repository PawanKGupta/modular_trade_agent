import { test, expect } from '@playwright/test';

test('auth -> dashboard -> admin users -> orders tabs', async ({ page }) => {
  // Assumes API running at VITE_API_URL and web at baseURL
  await page.goto('/');

  // Login
  await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
  await page.getByLabel(/password/i).fill('Admin@123');
  await page.getByRole('button', { name: /login/i }).click();

  // Should land on dashboard (seeing overview/buying zone link)
  await expect(page.getByText(/Overview|Buying Zone/i)).toBeVisible();

  // Navigate to Admin Users (if visible)
  const adminLink = page.getByRole('link', { name: /Admin/i });
  if (await adminLink.isVisible()) {
    await adminLink.click();
    await expect(page.getByText(/Users/i)).toBeVisible();
  }

  // Orders page and tabs
  await page.getByRole('link', { name: /Orders/i }).click();
  await expect(page.getByText(/Orders/i)).toBeVisible();
  await page.getByRole('button', { name: 'Ongoing' }).click();
  await page.getByRole('button', { name: 'Sell' }).click();
  await page.getByRole('button', { name: 'Closed' }).click();
});
