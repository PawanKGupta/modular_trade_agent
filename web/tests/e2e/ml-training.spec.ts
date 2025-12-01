import { test, expect } from './fixtures/test-fixtures';

test.describe('ML Training Management Page', () => {
	test.beforeEach(async ({ authenticatedPage }) => {
		// Page is already authenticated via fixture and should be on dashboard
		// Just ensure we're on dashboard, don't navigate again as it might cause redirect
		await authenticatedPage.waitForURL(/\/dashboard/, { timeout: 10000 });
		await authenticatedPage.waitForLoadState('networkidle');
	});

	test('navigates to ML training management', async ({ authenticatedPage }) => {
		// Expand Administration menu first (it's collapsed by default)
		const adminButton = authenticatedPage.getByRole('button', { name: /Administration/i });
		await adminButton.click();
		await authenticatedPage.waitForTimeout(300);

		// Click ML Training link
		await authenticatedPage.getByRole('link', { name: /ML Training/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /ML Training Management/i })).toBeVisible();
		await expect(authenticatedPage.getByRole('heading', { name: /Start Training Job/i })).toBeVisible();
	});

	test('shows training jobs and models tables', async ({ authenticatedPage }) => {
		// Expand Administration menu first
		const adminButton = authenticatedPage.getByRole('button', { name: /Administration/i });
		await adminButton.click();
		await authenticatedPage.waitForTimeout(300);

		await authenticatedPage.getByRole('link', { name: /ML Training/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify sections are displayed - use headings to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Recent Training Jobs/i })).toBeVisible();
		await expect(authenticatedPage.getByRole('heading', { name: /Model Versions/i })).toBeVisible();
	});
});
