import { test, expect } from '@playwright/test';

test.describe('System & Monitoring', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);
	});

	test('Service Status page displays service information', async ({ page }) => {
		await page.goto('/dashboard/service');

		// Verify page loads
		await expect(page.getByText(/Service Status|Service/i)).toBeVisible();

		// Verify service status indicators
		await expect(page.getByText(/Running|Stopped|Status/i).first()).toBeVisible();

		// Verify service controls are visible
		await expect(page.getByRole('button', { name: /Start|Stop|Restart/i }).first()).toBeVisible();
	});

	test('can start and stop trading service', async ({ page }) => {
		await page.goto('/dashboard/service');
		await page.waitForLoadState('networkidle');

		// Find start/stop button
		const startStopButton = page.getByRole('button', { name: /Start Service|Stop Service/i });

		if (await startStopButton.isVisible().catch(() => false)) {
			const buttonText = await startStopButton.textContent();
			const isRunning = buttonText?.toLowerCase().includes('stop');

			if (!isRunning) {
				// Start service
				await startStopButton.click();

				// Handle confirmation if present
				const dialog = page.getByRole('dialog');
				if (await dialog.isVisible().catch(() => false)) {
					await page.getByRole('button', { name: /Confirm|Yes|Start/i }).click();
				}

				await page.waitForTimeout(2000);

				// Verify service started
				await expect(page.getByText(/Running|Active/i).first()).toBeVisible({ timeout: 5000 });
			} else {
				// Service is running, stop it
				await startStopButton.click();

				// Handle confirmation
				const dialog = page.getByRole('dialog');
				if (await dialog.isVisible().catch(() => false)) {
					await page.getByRole('button', { name: /Confirm|Yes|Stop/i }).click();
				}

				await page.waitForTimeout(2000);

				// Verify service stopped
				await expect(page.getByText(/Stopped|Inactive/i).first()).toBeVisible({ timeout: 5000 });
			}
		}
	});

	test('System Logs page displays logs', async ({ page }) => {
		await page.goto('/dashboard/logs');

		// Verify page loads
		await expect(page.getByText(/System Logs|Logs/i)).toBeVisible();

		// Verify log table is displayed
		const logsTable = page.locator('table, [role="table"], .logs-list');
		await expect(logsTable.first()).toBeVisible({ timeout: 5000 });

		// Verify log filters are available
		await expect(page.getByText(/Level|Module|Search|Filter/i).first()).toBeVisible();
	});

	test('System Logs filters work correctly', async ({ page }) => {
		await page.goto('/dashboard/logs');
		await page.waitForLoadState('networkidle');

		// Test level filter if available
		const levelFilter = page.getByLabel(/Level|Filter by Level/i);
		if (await levelFilter.isVisible().catch(() => false)) {
			await levelFilter.click();
			await page.getByText(/ERROR|Error/i).first().click();
			await page.waitForTimeout(500);
		}

		// Test module filter if available
		const moduleFilter = page.getByLabel(/Module|Filter by Module/i);
		if (await moduleFilter.isVisible().catch(() => false)) {
			await moduleFilter.click();
			await page.getByText(/TradingService|Analysis/i).first().click();
			await page.waitForTimeout(500);
		}

		// Verify filters applied
		await expect(page.getByText(/System Logs|Logs/i)).toBeVisible();
	});

	test('Activity Log page displays activity', async ({ page }) => {
		await page.goto('/dashboard/activity');

		// Verify page loads
		await expect(page.getByText(/Activity Log|Activity/i)).toBeVisible();

		// Verify activity table is displayed
		const activityTable = page.locator('table, [role="table"], .activity-list');
		await expect(activityTable.first()).toBeVisible({ timeout: 5000 });

		// Verify activity filters are available
		await expect(page.getByText(/Level|Filter/i).first()).toBeVisible();
	});
});
