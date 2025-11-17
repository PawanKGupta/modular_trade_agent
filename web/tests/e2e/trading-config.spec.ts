import { test, expect } from '@playwright/test';

test.describe('Trading Configuration Page', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page.getByText(/Overview|Buying Zone/i)).toBeVisible();
	});

	test('navigates to trading configuration page', async ({ page }) => {
		// Navigate to trading config (assuming there's a link in the navigation)
		await page.goto('/dashboard/trading-config');
		await expect(page.getByText(/Trading Configuration/i)).toBeVisible();
	});

	test('displays all configuration sections', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await expect(page.getByText(/Strategy Parameters/i)).toBeVisible();
		await expect(page.getByText(/Capital & Position Management/i)).toBeVisible();
		await expect(page.getByText(/Risk Management/i)).toBeVisible();
		await expect(page.getByText(/Order Defaults/i)).toBeVisible();
		await expect(page.getByText(/Behavior Settings/i)).toBeVisible();
	});

	test('displays save and reset buttons', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await expect(page.getByRole('button', { name: /Save Changes/i })).toBeVisible();
		await expect(page.getByRole('button', { name: /Reset to Defaults/i })).toBeVisible();
	});

	test('modifies RSI period and shows unsaved changes', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		// Find and modify RSI period
		const rsiPeriodInput = page.getByLabel(/RSI Period/i);
		await rsiPeriodInput.clear();
		await rsiPeriodInput.fill('15');

		// Should show unsaved changes indicator
		await expect(page.getByText(/Unsaved changes/i)).toBeVisible();
	});

	test('saves configuration changes', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		// Modify a field
		const rsiPeriodInput = page.getByLabel(/RSI Period/i);
		await rsiPeriodInput.clear();
		await rsiPeriodInput.fill('15');

		// Click save
		const saveButton = page.getByRole('button', { name: /Save Changes/i });
		await saveButton.click();

		// Should show success message or update UI
		await expect(page.getByText(/Unsaved changes/i)).not.toBeVisible();
	});

	test('displays configuration presets', async ({ page }) => {
		await page.goto('/dashboard/trading-config');
		await expect(page.getByText(/Configuration Presets/i)).toBeVisible();
		await expect(page.getByText(/Conservative/i)).toBeVisible();
		await expect(page.getByText(/Moderate/i)).toBeVisible();
		await expect(page.getByText(/Aggressive/i)).toBeVisible();
	});

	test('applies configuration preset', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		// Find and click a preset button
		const presetButtons = page.getByRole('button', { name: /Apply Preset/i });
		const firstPreset = presetButtons.first();
		await firstPreset.click();

		// Should show unsaved changes
		await expect(page.getByText(/Unsaved changes/i)).toBeVisible();
	});

	test('toggles chart quality filter', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		const chartQualityCheckbox = page.getByLabel(/Enable Chart Quality Filter/i);
		const isChecked = await chartQualityCheckbox.isChecked();

		await chartQualityCheckbox.click();

		await expect(chartQualityCheckbox).toHaveProperty('checked', !isChecked);
	});

	test('toggles news sentiment enabled', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		const newsSentimentCheckbox = page.getByLabel(/Enable News Sentiment Analysis/i);
		const isChecked = await newsSentimentCheckbox.isChecked();

		await newsSentimentCheckbox.click();

		await expect(newsSentimentCheckbox).toHaveProperty('checked', !isChecked);

		// If enabled, should show additional fields
		if (!isChecked) {
			await expect(page.getByLabel(/Lookback Days/i)).toBeVisible();
		}
	});

	test('toggles ML enabled', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		const mlCheckbox = page.getByLabel(/Enable ML Predictions/i);
		const isChecked = await mlCheckbox.isChecked();

		await mlCheckbox.click();

		await expect(mlCheckbox).toHaveProperty('checked', !isChecked);

		// If enabled, should show additional fields
		if (!isChecked) {
			await expect(page.getByLabel(/ML Model Version/i)).toBeVisible();
		}
	});

	test('modifies multiple fields and saves', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		// Modify RSI period
		const rsiPeriodInput = page.getByLabel(/RSI Period/i);
		await rsiPeriodInput.clear();
		await rsiPeriodInput.fill('15');

		// Modify capital
		const capitalInput = page.getByLabel(/Capital per Trade/i);
		await capitalInput.clear();
		await capitalInput.fill('250000');

		// Modify portfolio size
		const portfolioSizeInput = page.getByLabel(/Max Portfolio Size/i);
		await portfolioSizeInput.clear();
		await portfolioSizeInput.fill('8');

		// Should show unsaved changes
		await expect(page.getByText(/Unsaved changes/i)).toBeVisible();

		// Save
		const saveButton = page.getByRole('button', { name: /Save Changes/i });
		await saveButton.click();

		// Should clear unsaved changes indicator
		await expect(page.getByText(/Unsaved changes/i)).not.toBeVisible();
	});

	test('cancels unsaved changes', async ({ page }) => {
		await page.goto('/dashboard/trading-config');

		// Modify a field
		const rsiPeriodInput = page.getByLabel(/RSI Period/i);
		await rsiPeriodInput.clear();
		await rsiPeriodInput.fill('15');

		// Wait for sticky bar to appear
		await expect(page.getByText(/You have unsaved changes/i)).toBeVisible();

		// Click cancel
		const cancelButton = page.getByRole('button', { name: /Cancel/i });
		await cancelButton.click();

		// Should clear unsaved changes indicator
		await expect(page.getByText(/You have unsaved changes/i)).not.toBeVisible();
	});
});
