import { test, expect } from '@playwright/test';

test.describe('Log Viewer Page', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page.getByText(/Overview|Buying Zone/i)).toBeVisible();
	});

	test('shows service and error logs', async ({ page }) => {
		await page.goto('/dashboard/logs');
		await expect(page.getByText(/Log Management/i)).toBeVisible();
		await expect(page.getByText(/Analysis task finished successfully/i)).toBeVisible();
		await expect(page.getByText(/Unable to parse symbol/i)).toBeVisible();
	});

	test('admin can toggle scope and resolve errors', async ({ page }) => {
		await page.goto('/dashboard/logs');
		await page.getByLabel(/Scope/i).selectOption('all');
		await page.getByLabel(/User ID/i).fill('1');
		await expect(page.getByRole('button', { name: /Resolve/i })).toBeVisible();
		page.once('dialog', async (dialog) => {
			await dialog.accept('Resolved in e2e');
		});
		await page.getByRole('button', { name: /Resolve/i }).click();
	});
});
