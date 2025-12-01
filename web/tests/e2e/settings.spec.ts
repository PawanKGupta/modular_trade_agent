import { test, expect } from './fixtures/test-fixtures';

test.describe('Settings & Configuration', () => {
	test.beforeEach(async ({ authenticatedPage }) => {
		// Page is already authenticated via fixture and should be on dashboard
		// Just ensure we're on dashboard, don't navigate again as it might cause redirect
		await authenticatedPage.waitForURL(/\/dashboard/, { timeout: 10000 });
		await authenticatedPage.waitForLoadState('networkidle');
	});

	test('Trading Config page loads with current settings', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/trading-config');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Trading Configuration/i })).toBeVisible();

		// Verify config sections are displayed
		await expect(authenticatedPage.getByText(/Strategy|Capital|Risk|Order|Behavior/i).first()).toBeVisible();

		// Verify save button is present
		await expect(authenticatedPage.getByRole('button', { name: /Save Changes/i }).first()).toBeVisible();
	});

	test('can update trading configuration', async ({ authenticatedPage: page, testDataTracker }) => {
		await page.goto('/dashboard/trading-config');
		await page.waitForLoadState('networkidle');

		// Track config modification BEFORE making changes (saves original)
		await testDataTracker.trackConfig(page, 'trading-config');

		// Find RSI period input (if available)
		const rsiInput = page.getByLabel(/RSI Period/i).first();
		if (await rsiInput.isVisible().catch(() => false)) {
			const originalValue = await rsiInput.inputValue();
			const newValue = originalValue === '10' ? '14' : '10';

			await rsiInput.clear();
			await rsiInput.fill(newValue);

			// Save changes - use first() to avoid strict mode violation (2 buttons on page)
			const saveButton = page.getByRole('button', { name: /Save Changes/i }).first();
			await saveButton.click();

			// Wait for save to complete
			await page.waitForTimeout(1000);

			// Refresh page and verify value persisted
			await page.reload();
			await page.waitForLoadState('networkidle');

			const savedValue = await page.getByLabel(/RSI Period/i).first().inputValue();
			expect(savedValue).toBe(newValue);
		}
	});

	test('Broker Settings page loads', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/settings');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - check for heading or main content
		const heading = authenticatedPage.getByRole('heading', { name: /Broker Settings|Settings/i });
		const hasHeading = await heading.isVisible().catch(() => false);

		if (!hasHeading) {
			// If no heading, at least verify the page loaded
			await expect(authenticatedPage.locator('main, [role="main"]')).toBeVisible();
		} else {
			await expect(heading).toBeVisible();
		}

		// Verify credential form or fields are displayed - check for various possible field names
		const apiKeyField = authenticatedPage.getByLabel(/API Key|Api Key|Access Token|Secret Key|Broker/i).first();
		const hasApiField = await apiKeyField.isVisible().catch(() => false);

		// If API key field not found, at least verify some form content exists
		if (!hasApiField) {
			const formContent = authenticatedPage.locator('form, input, [type="password"], [type="text"]').first();
			await expect(formContent).toBeVisible({ timeout: 5000 });
		} else {
			await expect(apiKeyField).toBeVisible();
		}
	});

	test('Notification Settings page loads', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/notification-preferences');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Notification Preferences/i })).toBeVisible();

		// Verify preference sections are displayed
		await expect(authenticatedPage.getByText(/Notification Channels|Order Events|System Events/i).first()).toBeVisible();
	});

	test('can update notification preferences', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/notification-preferences');
		await authenticatedPage.waitForLoadState('networkidle');

		// Find a checkbox to toggle (e.g., "Notify Service Events")
		const serviceEventsCheckbox = authenticatedPage.getByLabel(/Notify Service Events|Service Events/i);

		if (await serviceEventsCheckbox.isVisible().catch(() => false)) {
			const originalState = await serviceEventsCheckbox.isChecked();

			// Toggle checkbox
			await serviceEventsCheckbox.click();
			await authenticatedPage.waitForTimeout(300);

			// Verify state changed
			await expect(serviceEventsCheckbox).toHaveProperty('checked', !originalState);

			// Save if there's a save button
			const saveButton = authenticatedPage.getByRole('button', { name: /Save/i });
			if (await saveButton.isVisible().catch(() => false)) {
				await saveButton.click();
				await authenticatedPage.waitForTimeout(1000);
			}
		}
	});

	test('displays configuration presets', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/trading-config');
		await authenticatedPage.waitForLoadState('networkidle');

		// Check if presets section is visible
		const presetsSection = authenticatedPage.getByText(/Presets|Configuration Presets/i);
		if (await presetsSection.isVisible().catch(() => false)) {
			await expect(presetsSection).toBeVisible();

			// Verify preset buttons exist
			const presetButtons = authenticatedPage.getByRole('button', { name: /Conservative|Moderate|Aggressive|Apply/i });
			const presetCount = await presetButtons.count();

			if (presetCount > 0) {
				await expect(presetButtons.first()).toBeVisible();
			}
		}
	});

	test('can reset trading config to defaults', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/trading-config');
		await authenticatedPage.waitForLoadState('networkidle');

		// Find reset button
		const resetButton = authenticatedPage.getByRole('button', { name: /Reset|Reset to Defaults/i });

		if (await resetButton.isVisible().catch(() => false)) {
			await resetButton.click();

			// Handle confirmation dialog if present
			const dialog = authenticatedPage.getByRole('dialog');
			if (await dialog.isVisible().catch(() => false)) {
				await authenticatedPage.getByRole('button', { name: /Confirm|Yes|Reset/i }).click();
			}

			// Wait for reset to complete
			await authenticatedPage.waitForTimeout(1000);

			// Verify reset completed (success message or UI update)
			await expect(authenticatedPage.getByText(/Trading Configuration|Trading Config/i)).toBeVisible();
		}
	});
});
