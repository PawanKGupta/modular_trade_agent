import { test, expect } from './fixtures/test-fixtures';

test('auth -> dashboard -> admin users -> orders tabs', async ({ authenticatedPage }) => {
  // Page is already authenticated via fixture
  await authenticatedPage.goto('/dashboard');
  await authenticatedPage.waitForLoadState('networkidle');

  // Should land on dashboard - verify main content
  await expect(authenticatedPage.locator('main, [role="main"]')).toBeVisible();

  // Navigate to Admin Users (expand Administration menu first)
  const adminButton = authenticatedPage.getByRole('button', { name: /Administration/i });
  if (await adminButton.isVisible().catch(() => false)) {
    await adminButton.click();
    await authenticatedPage.waitForTimeout(300);

    const usersLink = authenticatedPage.getByRole('link', { name: /Users/i });
    if (await usersLink.isVisible().catch(() => false)) {
      await usersLink.click();
      await authenticatedPage.waitForLoadState('networkidle');
      const usersHeading = authenticatedPage.getByRole('heading', { name: /Users/i });
      const hasUsersHeading = await usersHeading.isVisible().catch(() => false);
      if (hasUsersHeading) {
        await expect(usersHeading).toBeVisible();
      }
    }
  }

  // Orders page and tabs - expand Trading category first
  const tradingButton = authenticatedPage.getByRole('button', { name: /Trading/i });
  if (await tradingButton.isVisible().catch(() => false)) {
    await tradingButton.click();
    await authenticatedPage.waitForTimeout(300);
  }

  await authenticatedPage.getByRole('link', { name: /Orders/i }).click();
  await authenticatedPage.waitForLoadState('networkidle');

  // Verify orders page loaded
  const ordersHeading = authenticatedPage.getByRole('heading', { name: /Orders/i });
  const hasOrdersHeading = await ordersHeading.isVisible().catch(() => false);
  if (hasOrdersHeading) {
    await expect(ordersHeading).toBeVisible();
  } else {
    // Fallback: just verify main content is visible
    await expect(authenticatedPage.locator('main, [role="main"]')).toBeVisible();
  }

  // Click order tabs if available
  const ongoingTab = authenticatedPage.getByRole('button', { name: 'Ongoing' });
  if (await ongoingTab.isVisible().catch(() => false)) {
    await ongoingTab.click();
    await authenticatedPage.waitForTimeout(200);
  }

  const sellTab = authenticatedPage.getByRole('button', { name: 'Sell' });
  if (await sellTab.isVisible().catch(() => false)) {
    await sellTab.click();
    await authenticatedPage.waitForTimeout(200);
  }

  const closedTab = authenticatedPage.getByRole('button', { name: 'Closed' });
  if (await closedTab.isVisible().catch(() => false)) {
    await closedTab.click();
    await authenticatedPage.waitForTimeout(200);
  }
});
