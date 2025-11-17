import { test, expect } from '@playwright/test';

test.describe('ML Training Management Page', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page.getByText(/Overview|Buying Zone/i)).toBeVisible();
	});

	test('navigates to ML training management', async ({ page }) => {
		await page.getByRole('link', { name: /ML Training/i }).click();
		await expect(page.getByText(/ML Training Management/i)).toBeVisible();
		await expect(page.getByText(/Start Training Job/i)).toBeVisible();
	});

	test('shows training jobs and models tables', async ({ page }) => {
		await page.getByRole('link', { name: /ML Training/i }).click();
		await expect(page.getByText(/Recent Training Jobs/i)).toBeVisible();
		await expect(page.getByText(/Model Versions/i)).toBeVisible();
	});
});
