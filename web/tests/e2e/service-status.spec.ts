import { test, expect } from '@playwright/test';

test.describe('Service Status Page', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page.getByText(/Overview|Buying Zone/i)).toBeVisible();
	});

	test('navigates to service status page', async ({ page }) => {
		await page.getByRole('link', { name: /Service Status/i }).click();
		await expect(page.getByText(/Service Status/i)).toBeVisible();
		await expect(page.getByText(/Service Health/i)).toBeVisible();
	});

	test('displays service status information', async ({ page }) => {
		await page.getByRole('link', { name: /Service Status/i }).click();
		await expect(page.getByText(/Service Health/i)).toBeVisible();
		await expect(page.getByText(/Last Heartbeat/i)).toBeVisible();
		await expect(page.getByText(/Last Task Execution/i)).toBeVisible();
		await expect(page.getByText(/Error Count/i)).toBeVisible();
	});

	test('displays task execution history section', async ({ page }) => {
		await page.getByRole('link', { name: /Service Status/i }).click();
		await expect(page.getByText(/Task Execution History/i)).toBeVisible();
	});

	test('displays service logs section', async ({ page }) => {
		await page.getByRole('link', { name: /Service Status/i }).click();
		await expect(page.getByText(/Recent Service Logs/i)).toBeVisible();
	});

	test('has start and stop service buttons', async ({ page }) => {
		await page.getByRole('link', { name: /Service Status/i }).click();
		await expect(page.getByRole('button', { name: /Start Service/i })).toBeVisible();
		await expect(page.getByRole('button', { name: /Stop Service/i })).toBeVisible();
	});

	test('toggles auto-refresh checkbox', async ({ page }) => {
		await page.getByRole('link', { name: /Service Status/i }).click();
		const checkbox = page.getByLabel(/Auto-refresh/i);
		await expect(checkbox).toBeChecked();
		await checkbox.click();
		await expect(checkbox).not.toBeChecked();
		await checkbox.click();
		await expect(checkbox).toBeChecked();
	});
});
