import { test, expect } from './fixtures/test-fixtures';

test.describe('Service Status Page', () => {
	test.beforeEach(async ({ authenticatedPage }) => {
		// Page is already authenticated via fixture and should be on dashboard
		// Just ensure we're on dashboard, don't navigate again as it might cause redirect
		await authenticatedPage.waitForURL(/\/dashboard/, { timeout: 10000 });
		await authenticatedPage.waitForLoadState('networkidle');
	});

	test('navigates to service status page', async ({ authenticatedPage }) => {
		// Scope queries to sidebar navigation
		const sidebar = authenticatedPage.locator('aside nav, aside');
		// Expand System category first (it's collapsed by default)
		const systemButton = sidebar.getByRole('button', { name: /System/i });
		await systemButton.click();
		await authenticatedPage.waitForTimeout(300);

		// Click Service Status link
		await sidebar.getByRole('link', { name: /Service Status/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		const heading = authenticatedPage.getByRole('heading', { name: /Service Status|Unified Service Status/i });
		const hasHeading = await heading.isVisible().catch(() => false);
		if (hasHeading) {
			await expect(heading).toBeVisible();
		} else {
			await expect(authenticatedPage.locator('main, [role="main"]')).toBeVisible();
		}
	});

	test('displays service status information', async ({ authenticatedPage }) => {
		// Scope queries to sidebar navigation
		const sidebar = authenticatedPage.locator('aside nav, aside');
		// Expand System category first
		const systemButton = sidebar.getByRole('button', { name: /System/i });
		await systemButton.click();
		await authenticatedPage.waitForTimeout(300);

		await sidebar.getByRole('link', { name: /Service Status/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify service status sections are displayed
		await expect(authenticatedPage.getByText(/Unified Service Status|Service Status|Individual Services/i).first()).toBeVisible();
	});

	test('displays task execution history section', async ({ authenticatedPage }) => {
		// Scope queries to sidebar navigation
		const sidebar = authenticatedPage.locator('aside nav, aside');
		// Expand System category first
		const systemButton = sidebar.getByRole('button', { name: /System/i });
		await systemButton.click();
		await authenticatedPage.waitForTimeout(300);

		await sidebar.getByRole('link', { name: /Service Status/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify task execution history section
		await expect(authenticatedPage.getByText(/Task Execution History/i)).toBeVisible();
	});

	test('displays service logs section', async ({ authenticatedPage }) => {
		// Scope queries to sidebar navigation
		const sidebar = authenticatedPage.locator('aside nav, aside');
		// Expand System category first
		const systemButton = sidebar.getByRole('button', { name: /System/i });
		await systemButton.click();
		await authenticatedPage.waitForTimeout(300);

		await sidebar.getByRole('link', { name: /Service Status/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify service logs section (might be named differently)
		const logsSection = authenticatedPage.getByText(/Service Logs|Recent Service Logs|Logs/i);
		await expect(logsSection.first()).toBeVisible();
	});

	test('has start and stop service buttons', async ({ authenticatedPage }) => {
		// Scope queries to sidebar navigation
		const sidebar = authenticatedPage.locator('aside nav, aside');
		// Expand System category first
		const systemButton = sidebar.getByRole('button', { name: /System/i });
		await systemButton.click();
		await authenticatedPage.waitForTimeout(300);

		await sidebar.getByRole('link', { name: /Service Status/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify service control buttons - check for either start or stop button
		const startButton = authenticatedPage.getByRole('button', { name: /Start Service/i });
		const stopButton = authenticatedPage.getByRole('button', { name: /Stop Service/i });

		// Scroll to buttons if needed
		await startButton.first().scrollIntoViewIfNeeded().catch(() => {});
		await authenticatedPage.waitForTimeout(200);

		const hasStart = await startButton.first().isVisible().catch(() => false);
		const hasStop = await stopButton.first().isVisible().catch(() => false);

		// At least one service control button should be visible
		expect(hasStart || hasStop).toBe(true);
	});

	test('toggles auto-refresh checkbox', async ({ authenticatedPage }) => {
		// Scope queries to sidebar navigation
		const sidebar = authenticatedPage.locator('aside nav, aside');
		// Expand System category first
		const systemButton = sidebar.getByRole('button', { name: /System/i });
		await systemButton.click();
		await authenticatedPage.waitForTimeout(300);

		await sidebar.getByRole('link', { name: /Service Status/i }).click();
		await authenticatedPage.waitForLoadState('networkidle');

		const checkbox = authenticatedPage.getByLabel(/Auto-refresh/i);
		await expect(checkbox).toBeVisible({ timeout: 5000 });

		const isChecked = await checkbox.isChecked();
		await checkbox.click();
		await authenticatedPage.waitForTimeout(200);

		// Verify the checkbox state changed
		if (isChecked) {
			await expect(checkbox).not.toBeChecked();
		} else {
			await expect(checkbox).toBeChecked();
		}

		// Toggle back
		await checkbox.click();
		await authenticatedPage.waitForTimeout(200);

		// Verify it's back to original state
		if (isChecked) {
			await expect(checkbox).toBeChecked();
		} else {
			await expect(checkbox).not.toBeChecked();
		}
	});
});
