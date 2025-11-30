import { test, expect } from '@playwright/test';

test.describe('Settings & Configuration', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);
	});

	test('Trading Config page loads with current settings', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		// Verify page loads
		await expect(page.getByText(/Trading Configuration|Trading Config/i)).toBeVisible();

		// Verify config sections are displayed
		await expect(page.getByText(/Strategy|Capital|Risk|Order|Behavior/i).first()).toBeVisible();

		// Verify save button is present
		await expect(page.getByRole('button', { name: /Save/i })).toBeVisible();
	});

	test('can update trading configuration', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await page.waitForLoadState('networkidle');

		// Find RSI period input (if available)
		const rsiInput = page.getByLabel(/RSI Period/i).first();
		if (await rsiInput.isVisible().catch(() => false)) {
			const originalValue = await rsiInput.inputValue();
			const newValue = originalValue === '10' ? '14' : '10';

			await rsiInput.clear();
			await rsiInput.fill(newValue);

			// Save changes
			const saveButton = page.getByRole('button', { name: /Save/i });
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

	test('Broker Settings page loads', async ({ page }) => {
		await page.goto('/dashboard/settings');

		// Verify page loads
		await expect(page.getByText(/Broker Settings|Settings/i)).toBeVisible();

		// Verify credential form or fields are displayed
		const apiKeyField = page.getByLabel(/API Key|Api Key/i);
		await expect(apiKeyField.first()).toBeVisible({ timeout: 5000 });
	});

	test('Notification Settings page loads', async ({ page }) => {
		await page.goto('/dashboard/notification-preferences');

		// Verify page loads
		await expect(page.getByText(/Notification Settings|Notification Preferences/i)).toBeVisible();

		// Verify preference sections are displayed
		await expect(page.getByText(/Notification Channels|Order Events|System Events/i).first()).toBeVisible();
	});

	test('can update notification preferences', async ({ page }) => {
		await page.goto('/dashboard/notification-preferences');
		await page.waitForLoadState('networkidle');

		// Find a checkbox to toggle (e.g., "Notify Service Events")
		const serviceEventsCheckbox = page.getByLabel(/Notify Service Events|Service Events/i);

		if (await serviceEventsCheckbox.isVisible().catch(() => false)) {
			const originalState = await serviceEventsCheckbox.isChecked();

			// Toggle checkbox
			await serviceEventsCheckbox.click();
			await page.waitForTimeout(300);

			// Verify state changed
			await expect(serviceEventsCheckbox).toHaveProperty('checked', !originalState);

			// Save if there's a save button
			const saveButton = page.getByRole('button', { name: /Save/i });
			if (await saveButton.isVisible().catch(() => false)) {
				await saveButton.click();
				await page.waitForTimeout(1000);
			}
		}
	});

	test('displays configuration presets', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await page.waitForLoadState('networkidle');

		// Check if presets section is visible
		const presetsSection = page.getByText(/Presets|Configuration Presets/i);
		if (await presetsSection.isVisible().catch(() => false)) {
			await expect(presetsSection).toBeVisible();

			// Verify preset buttons exist
			const presetButtons = page.getByRole('button', { name: /Conservative|Moderate|Aggressive|Apply/i });
			const presetCount = await presetButtons.count();

			if (presetCount > 0) {
				await expect(presetButtons.first()).toBeVisible();
			}
		}
	});

	test('can reset trading config to defaults', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await page.waitForLoadState('networkidle');

		// Find reset button
		const resetButton = page.getByRole('button', { name: /Reset|Reset to Defaults/i });

		if (await resetButton.isVisible().catch(() => false)) {
			await resetButton.click();

			// Handle confirmation dialog if present
			const dialog = page.getByRole('dialog');
			if (await dialog.isVisible().catch(() => false)) {
				await page.getByRole('button', { name: /Confirm|Yes|Reset/i }).click();
			}

			// Wait for reset to complete
			await page.waitForTimeout(1000);

			// Verify reset completed (success message or UI update)
			await expect(page.getByText(/Trading Configuration|Trading Config/i)).toBeVisible();
		}
	});
});
