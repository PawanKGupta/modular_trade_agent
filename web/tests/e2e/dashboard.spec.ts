import { test, expect } from './fixtures/test-fixtures';

test.describe('Dashboard & Navigation', () => {
	test.beforeEach(async ({ authenticatedPage }) => {
		// Page is already authenticated via fixture and should be on dashboard
		// Just ensure we're on dashboard, don't navigate again as it might cause redirect
		await authenticatedPage.waitForURL(/\/dashboard/, { timeout: 10000 });
		await authenticatedPage.waitForLoadState('networkidle');
	});

	test('dashboard overview loads correctly', async ({ authenticatedPage }) => {
		// Navigate to dashboard (should already be there from beforeEach)
		await authenticatedPage.goto('/dashboard');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify navigation menu is visible - check for Overview category button
		const overviewButton = authenticatedPage.getByRole('button', { name: /Overview/i });
		await expect(overviewButton).toBeVisible();

		// Verify key sections are present
		const dashboardContent = authenticatedPage.locator('main, [role="main"]');
		await expect(dashboardContent).toBeVisible();
	});

	test('all menu items navigate correctly', async ({ authenticatedPage }) => {
		// Test each major menu item with their category
		const menuItems = [
			{ category: null, name: /Dashboard/i, url: /\/dashboard$/ },
			{ category: /Trading/i, name: /Buying Zone/i, url: /\/dashboard\/buying-zone/ },
			{ category: /Trading/i, name: /Orders/i, url: /\/dashboard\/orders/ },
			{ category: /Trading/i, name: /Paper Trading/i, url: /\/dashboard\/paper-trading/ },
			{ category: /Trading/i, name: /PnL/i, url: /\/dashboard\/pnl/ },
			{ category: /Trading/i, name: /Targets/i, url: /\/dashboard\/targets/ },
			{ category: /System/i, name: /Service Status/i, url: /\/dashboard\/service/ },
			{ category: /Settings/i, name: /Trading Config/i, url: /\/dashboard\/trading-config/ },
			{ category: /Settings/i, name: /Broker Settings/i, url: /\/dashboard\/settings/ },
			{ category: /Settings/i, name: /Notification Settings/i, url: /\/dashboard\/notification-preferences/ },
			{ category: /Logs/i, name: /System Logs/i, url: /\/dashboard\/logs/ },
			{ category: /Logs/i, name: /Activity Log/i, url: /\/dashboard\/activity/ },
			{ category: /Notifications/i, name: /Notifications/i, url: /\/dashboard\/notifications/ },
		];

		for (const item of menuItems) {
			// Expand category if needed
			if (item.category) {
				const categoryButton = authenticatedPage.getByRole('button', { name: item.category });

				// Check if category is expanded by checking if menu items are visible
				const menuLink = authenticatedPage.getByRole('link', { name: item.name });
				const isExpanded = await menuLink.isVisible().catch(() => false);

				if (!isExpanded) {
					await categoryButton.click();
					// Wait for menu items to appear after expanding
					await menuLink.waitFor({ state: 'visible', timeout: 5000 });
				}
			}

			// Find and click menu item
			const menuLink = authenticatedPage.getByRole('link', { name: item.name });
			await menuLink.click();

			// Verify navigation
			await expect(authenticatedPage).toHaveURL(item.url);
			await authenticatedPage.waitForLoadState('networkidle');

			// Navigate back to dashboard for next test
			await authenticatedPage.goto('/dashboard');
			await authenticatedPage.waitForLoadState('networkidle');
		}
	});

	test('menu categories can be expanded and collapsed', async ({ authenticatedPage }) => {
		// Find Trading category button
		const categoryButton = authenticatedPage.getByRole('button', { name: /Trading/i });
		await expect(categoryButton).toBeVisible();

		// Check initial state - Trading is collapsed by default
		const buyingZoneLink = authenticatedPage.getByRole('link', { name: /Buying Zone/i });
		const isInitiallyVisible = await buyingZoneLink.isVisible().catch(() => false);

		// Trading should be collapsed initially (items not visible)
		expect(isInitiallyVisible).toBe(false);

		// Click to expand
		await categoryButton.click();
		await authenticatedPage.waitForTimeout(300);

		// Verify Trading items are now visible
		await expect(buyingZoneLink).toBeVisible();

		// Click again to collapse
		await categoryButton.click();
		await authenticatedPage.waitForTimeout(300);

		// Verify Trading items are hidden again
		await expect(buyingZoneLink).not.toBeVisible();
	});

	test('active menu item is highlighted', async ({ authenticatedPage }) => {
		// Expand Trading category first (it's collapsed by default)
		const tradingButton = authenticatedPage.getByRole('button', { name: /Trading/i });
		await tradingButton.click();
		await authenticatedPage.waitForTimeout(300);

		// Now find and click Buying Zone link
		const buyingZoneLink = authenticatedPage.getByRole('link', { name: /Buying Zone/i });
		await buyingZoneLink.click();
		await expect(authenticatedPage).toHaveURL(/\/dashboard\/buying-zone/);
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify active state (check for active class or highlighted style)
		const activeLink = authenticatedPage.getByRole('link', { name: /Buying Zone/i });
		await expect(activeLink).toHaveClass(/active|bg-\[var\(--accent\)\]/);
	});
});
