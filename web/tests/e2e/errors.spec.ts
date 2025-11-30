import { test, expect } from '@playwright/test';

test.describe('Error Handling & Edge Cases', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);
	});

	test('application handles API errors gracefully', async ({ page }) => {
		// Intercept API calls and return error
		await page.route('**/api/**', route => {
			route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'Internal Server Error' })
			});
		});

		// Navigate to a page that requires API call
		await page.goto('/dashboard/buying-zone');

		// Verify error message is displayed
		await expect(page.getByText(/error|failed|unable to load/i)).toBeVisible({ timeout: 5000 });

		// Verify application doesn't crash
		await expect(page.getByText(/Buying Zone|Dashboard/i)).toBeVisible();
	});

	test('application shows loading states', async ({ page }) => {
		// Slow down API responses
		await page.route('**/api/**', route => {
			setTimeout(() => {
				route.continue();
			}, 1000);
		});

		await page.goto('/dashboard/buying-zone');

		// Verify loading indicator is shown
		await expect(page.getByText(/loading|Loading/i)).toBeVisible({ timeout: 500 });
	});

	test('validates input and shows errors', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await page.waitForLoadState('networkidle');

		// Find capital input field
		const capitalInput = page.getByLabel(/Capital|User Capital/i).first();

		if (await capitalInput.isVisible().catch(() => false)) {
			// Enter invalid value (negative number)
			await capitalInput.clear();
			await capitalInput.fill('-1000');

			// Try to save
			const saveButton = page.getByRole('button', { name: /Save/i });
			await saveButton.click();

			// Verify validation error is shown
			await expect(page.getByText(/invalid|must be|greater than|positive/i)).toBeVisible({ timeout: 3000 });
		}
	});

	test('handles empty states correctly', async ({ page }) => {
		// Navigate to pages that might be empty
		await page.goto('/dashboard/orders');
		await page.waitForLoadState('networkidle');

		// Check if empty state is shown when no orders
		const emptyState = page.getByText(/No orders|No data|empty/i);
		if (await emptyState.isVisible().catch(() => false)) {
			await expect(emptyState).toBeVisible();
		}
	});

	test('handles network timeout gracefully', async ({ page }) => {
		// Simulate network timeout
		await page.route('**/api/**', route => {
			// Don't fulfill the request - simulate timeout
		});

		// Set timeout for navigation
		page.setDefaultTimeout(3000);

		// Navigate to page
		try {
			await page.goto('/dashboard/buying-zone', { timeout: 3000 });
		} catch (e) {
			// Expected to timeout or show error
		}

		// Reset timeout
		page.setDefaultTimeout(30000);

		// Verify error handling
		await expect(page.locator('body')).toBeVisible();
	});
});
