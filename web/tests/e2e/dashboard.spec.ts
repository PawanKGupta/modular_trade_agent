import { test, expect } from '@playwright/test';

test.describe('Dashboard & Navigation', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);
	});

	test('dashboard overview loads correctly', async ({ page }) => {
		await page.goto('/dashboard');

		// Verify dashboard page loads
		await expect(page.getByText(/Dashboard|Overview/i)).toBeVisible();

		// Verify navigation menu is visible
		await expect(page.getByText(/Overview/i).first()).toBeVisible();

		// Verify key sections are present (if any)
		const dashboardContent = page.locator('main, [role="main"]');
		await expect(dashboardContent).toBeVisible();
	});

	test('all menu items navigate correctly', async ({ page }) => {
		// Test each major menu item
		const menuItems = [
			{ name: /Dashboard/i, url: /\/dashboard$/ },
			{ name: /Buying Zone/i, url: /\/dashboard\/buying-zone/ },
			{ name: /Orders/i, url: /\/dashboard\/orders/ },
			{ name: /Paper Trading/i, url: /\/dashboard\/paper-trading/ },
			{ name: /PnL/i, url: /\/dashboard\/pnl/ },
			{ name: /Targets/i, url: /\/dashboard\/targets/ },
			{ name: /Service Status/i, url: /\/dashboard\/service/ },
			{ name: /Trading Config/i, url: /\/dashboard\/trading-config/ },
			{ name: /Broker Settings/i, url: /\/dashboard\/settings/ },
			{ name: /Notification Settings/i, url: /\/dashboard\/notification-preferences/ },
			{ name: /System Logs/i, url: /\/dashboard\/logs/ },
			{ name: /Activity Log/i, url: /\/dashboard\/activity/ },
			{ name: /Notifications/i, url: /\/dashboard\/notifications/ },
		];

		for (const item of menuItems) {
			// Find and click menu item
			const menuLink = page.getByRole('link', { name: item.name });

			// Check if menu category needs to be expanded
			const parentButton = menuLink.locator('..').locator('..').getByRole('button').first();
			if (await parentButton.count() > 0 && await parentButton.isVisible().catch(() => false)) {
				await parentButton.click();
				await page.waitForTimeout(200); // Wait for animation
			}

			// Click the menu item
			await menuLink.click();

			// Verify navigation
			await expect(page).toHaveURL(item.url);
			await page.waitForLoadState('networkidle');

			// Navigate back to dashboard for next test
			await page.goto('/dashboard');
		}
	});

	test('menu categories can be expanded and collapsed', async ({ page }) => {
		// Find Trading category button
		const tradingButton = page.getByText(/Trading/i).first();
		await expect(tradingButton).toBeVisible();

		// Get the button element (category header)
		const categoryButton = tradingButton.locator('..').getByRole('button').first();

		// Check if Trading items are visible
		const buyingZoneLink = page.getByRole('link', { name: /Buying Zone/i });
		const isInitiallyVisible = await buyingZoneLink.isVisible().catch(() => false);

		// Click to toggle
		await categoryButton.click();
		await page.waitForTimeout(300);

		// Verify state changed
		if (isInitiallyVisible) {
			await expect(buyingZoneLink).not.toBeVisible();
		} else {
			await expect(buyingZoneLink).toBeVisible();
		}

		// Click again to toggle back
		await categoryButton.click();
		await page.waitForTimeout(300);

		// Verify back to original state
		if (isInitiallyVisible) {
			await expect(buyingZoneLink).toBeVisible();
		} else {
			await expect(buyingZoneLink).not.toBeVisible();
		}
	});

	test('active menu item is highlighted', async ({ page }) => {
		// Navigate to Buying Zone
		const buyingZoneLink = page.getByRole('link', { name: /Buying Zone/i });

		// Expand Trading category if needed
		const tradingButton = page.getByText(/Trading/i).first().locator('..').getByRole('button').first();
		if (await tradingButton.isVisible().catch(() => false)) {
			await tradingButton.click();
			await page.waitForTimeout(200);
		}

		await buyingZoneLink.click();
		await expect(page).toHaveURL(/\/dashboard\/buying-zone/);

		// Verify active state (check for active class or highlighted style)
		const activeLink = page.getByRole('link', { name: /Buying Zone/i });
		await expect(activeLink).toHaveClass(/active|bg-\[var\(--accent\)\]/);
	});
});
