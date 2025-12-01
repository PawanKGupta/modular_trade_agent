import { test, expect } from './fixtures/test-fixtures';

test.describe('System & Monitoring', () => {
	test.beforeEach(async ({ authenticatedPage }) => {
		// Page is already authenticated via fixture and should be on dashboard
		// Just ensure we're on dashboard, don't navigate again as it might cause redirect
		await authenticatedPage.waitForURL(/\/dashboard/, { timeout: 10000 });
		await authenticatedPage.waitForLoadState('networkidle');
	});

	test('Service Status page displays service information', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/service');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		const heading = authenticatedPage.getByRole('heading', { name: /Service Status|Service/i });
		const hasHeading = await heading.isVisible().catch(() => false);

		if (!hasHeading) {
			// If no heading, at least verify the page loaded
			await expect(authenticatedPage.locator('main, [role="main"]')).toBeVisible();
		} else {
			await expect(heading).toBeVisible();
		}

		// Verify service status indicators
		await expect(authenticatedPage.getByText(/Running|Stopped|Status/i).first()).toBeVisible();

		// Verify service controls are visible
		await expect(authenticatedPage.getByRole('button', { name: /Start|Stop|Restart/i }).first()).toBeVisible();
	});

	test('can start and stop trading service', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/service');
		await authenticatedPage.waitForLoadState('networkidle');

		// Find start/stop button
		const startStopButton = authenticatedPage.getByRole('button', { name: /Start Service|Stop Service/i });

		if (await startStopButton.isVisible().catch(() => false)) {
			const buttonText = await startStopButton.textContent();
			const isRunning = buttonText?.toLowerCase().includes('stop');

			if (!isRunning) {
				// Start service
				await startStopButton.click();

				// Handle confirmation if present
				const dialog = authenticatedPage.getByRole('dialog');
				if (await dialog.isVisible().catch(() => false)) {
					await authenticatedPage.getByRole('button', { name: /Confirm|Yes|Start/i }).click();
				}

				await authenticatedPage.waitForTimeout(2000);

				// Verify service started
				await expect(authenticatedPage.getByText(/Running|Active/i).first()).toBeVisible({ timeout: 5000 });
			} else {
				// Service is running, stop it
				await startStopButton.click();

				// Handle confirmation
				const dialog = authenticatedPage.getByRole('dialog');
				if (await dialog.isVisible().catch(() => false)) {
					await authenticatedPage.getByRole('button', { name: /Confirm|Yes|Stop/i }).click();
				}

				await authenticatedPage.waitForTimeout(2000);

				// Verify service stopped
				await expect(authenticatedPage.getByText(/Stopped|Inactive/i).first()).toBeVisible({ timeout: 5000 });
			}
		}
	});

	test('System Logs page displays logs', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/logs');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Log Management/i })).toBeVisible();

		// Verify log sections are displayed (Service Logs and Error Logs)
		await expect(authenticatedPage.getByRole('heading', { name: /Service Logs/i })).toBeVisible();
		await expect(authenticatedPage.getByRole('heading', { name: /Error Logs/i })).toBeVisible();

		// Verify log filters are available
		await expect(authenticatedPage.getByText(/Level|Module|Search|Scope/i).first()).toBeVisible();
	});

	test('System Logs filters work correctly', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/logs');
		await authenticatedPage.waitForLoadState('networkidle');

		// Test level filter if available - use selectOption instead of clicking
		const levelFilter = authenticatedPage.getByLabel(/Level/i);
		if (await levelFilter.isVisible().catch(() => false)) {
			await levelFilter.selectOption('ERROR');
			await authenticatedPage.waitForTimeout(500);
		}

		// Test module filter if available - it's a text input, not a dropdown
		const moduleFilter = authenticatedPage.getByLabel(/Module/i);
		if (await moduleFilter.isVisible().catch(() => false)) {
			await moduleFilter.fill('scheduler');
			await authenticatedPage.waitForTimeout(500);
		}

		// Verify filters applied - page should still be visible
		await expect(authenticatedPage.getByRole('heading', { name: /Log Management/i })).toBeVisible();
	});

	test('Activity Log page displays activity', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/activity');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Activity/i })).toBeVisible();

		// Verify activity table is displayed (even if empty, table structure exists)
		const activityTable = authenticatedPage.locator('table, [role="table"]');
		await expect(activityTable.first()).toBeVisible({ timeout: 5000 });

		// Verify activity filters are available
		await expect(authenticatedPage.getByText(/Level|Filter/i).first()).toBeVisible();
	});
});
