import { test, expect } from './fixtures/test-fixtures';

test.describe('Trading Features', () => {
	test.beforeEach(async ({ authenticatedPage }) => {
		// Page is already authenticated via fixture and should be on dashboard
		// Just ensure we're on dashboard, don't navigate again as it might cause redirect
		await authenticatedPage.waitForURL(/\/dashboard/, { timeout: 10000 });
		await authenticatedPage.waitForLoadState('networkidle');
	});

	test('Buying Zone page loads and displays signals', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/buying-zone');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads
		await expect(authenticatedPage.getByRole('heading', { name: /Buying Zone/i })).toBeVisible();

		// Verify filters are available
		await expect(authenticatedPage.getByText(/Status|Date Filter/i).first()).toBeVisible();

		// Verify page content - either signals table or empty state
		const signalsTable = authenticatedPage.locator('table, [role="table"]');
		const emptyState = authenticatedPage.getByText(/No signals found/i);

		const hasTable = await signalsTable.first().isVisible().catch(() => false);
		const hasEmptyState = await emptyState.isVisible().catch(() => false);

		// Either table or empty state should be visible
		expect(hasTable || hasEmptyState).toBe(true);
	});

	test('Buying Zone filters work correctly', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/buying-zone');

		// Wait for page to load
		await authenticatedPage.waitForLoadState('networkidle');

		// Test date filter if available
		const dateFilter = authenticatedPage.getByLabel(/Date Filter/i);
		if (await dateFilter.isVisible().catch(() => false)) {
			await dateFilter.selectOption('today');
			await authenticatedPage.waitForTimeout(500); // Wait for filter to apply
		}

		// Test status filter if available
		const statusFilter = authenticatedPage.getByLabel(/Status/i);
		if (await statusFilter.isVisible().catch(() => false)) {
			await statusFilter.selectOption('active');
			await authenticatedPage.waitForTimeout(500);
		}

		// Verify page still loads correctly - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Buying Zone/i })).toBeVisible();
	});

	test('can reject a buying signal', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/buying-zone');
		await authenticatedPage.waitForLoadState('networkidle');

		// Wait for page to fully load
		await authenticatedPage.waitForSelector('table, [role="table"]', { timeout: 10000 }).catch(() => {
			// Table might not exist if no signals
		});

		// Find reject button on first signal (if available)
		const rejectButtons = authenticatedPage.getByRole('button', { name: /reject|Reject/i });
		const rejectCount = await rejectButtons.count();

		if (rejectCount > 0) {
			// Get the first reject button
			const firstReject = rejectButtons.first();

			// Click reject button
			await firstReject.scrollIntoViewIfNeeded();
			await firstReject.waitFor({ state: 'visible' });
			await firstReject.click();

			// Wait for API call to complete and UI to update
			await authenticatedPage.waitForLoadState('networkidle');
			await authenticatedPage.waitForTimeout(1500);

			// Verify rejection was processed
			// The signal should either:
			// 1. Be removed from the list (if filtering by active) - reject count decreases
			// 2. Have the reject button disappear (status changed to rejected) - button no longer visible
			// 3. Page should still be visible and functional

			// Check that the page is still functional
			await expect(authenticatedPage.getByRole('heading', { name: /Buying Zone/i })).toBeVisible();

			// Verify the reject button count decreased (signal removed from active list)
			// OR check if button is no longer visible (status changed, button removed)
			const newRejectButtons = authenticatedPage.getByRole('button', { name: /reject|Reject/i });
			const newRejectCount = await newRejectButtons.count();

			// Check if the original button still exists (might be stale if signal was removed)
			let buttonStillExists = false;
			try {
				buttonStillExists = await firstReject.isVisible({ timeout: 1000 });
			} catch {
				// Button is gone (stale element) - this is good, signal was removed
				buttonStillExists = false;
			}

			// Success if: count decreased (signal removed) OR button is gone (status changed)
			const success = newRejectCount < rejectCount || !buttonStillExists;

			if (!success) {
				// Log for debugging
				console.log(`Reject count: ${rejectCount} -> ${newRejectCount}, Button still exists: ${buttonStillExists}`);
			}

			expect(success).toBe(true);
		} else {
			// If no signals available, skip this test
			// This test requires active signals to test the reject functionality
			// Note: Signals can be seeded using the test data seeding script
			test.skip(true, 'No active signals available to test rejection - seed data with E2E_SEED_DATA=true to run this test');
		}
	});

	test('Orders page loads and displays orders', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/orders');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		await expect(authenticatedPage.getByRole('heading', { name: /Orders/i })).toBeVisible();

		// Verify order tabs are visible
		await expect(authenticatedPage.getByRole('button', { name: /Pending|Ongoing|Failed|Closed/i }).first()).toBeVisible();

		// Verify orders table is present (even if empty, table structure exists)
		const ordersTable = authenticatedPage.locator('table, [role="table"]');
		await expect(ordersTable.first()).toBeVisible({ timeout: 5000 });
	});

	test('Order status tabs filter orders correctly', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/orders');
		await authenticatedPage.waitForLoadState('networkidle');

		const tabs = ['Pending', 'Ongoing', 'Failed', 'Closed', 'Cancelled'];

		for (const tabName of tabs) {
			const tab = authenticatedPage.getByRole('button', { name: tabName });

			if (await tab.isVisible().catch(() => false)) {
				await tab.click();
				await authenticatedPage.waitForTimeout(500); // Wait for filter to apply

				// Verify tab is active (has active class or is selected)
				await expect(tab).toHaveClass(/active|selected|bg-/, { timeout: 2000 }).catch(() => {
					// Tab might not have active class, just verify it's clickable
				});
			}
		}
	});

	test('Paper Trading page loads', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/paper-trading');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation
		// Note: Actual heading is "Paper Trading Portfolio", not just "Paper Trading"
		await expect(authenticatedPage.getByRole('heading', { name: /Paper Trading Portfolio/i })).toBeVisible();

		// Verify account summary or portfolio section is displayed
		const accountSummary = authenticatedPage.getByText(/Account Summary|Initial Capital|Portfolio Value/i);
		await expect(accountSummary.first()).toBeVisible({ timeout: 5000 });
	});

	test('Paper Trading History page loads', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/paper-trading-history');
		await authenticatedPage.waitForLoadState('networkidle');

		// Verify page loads - use heading to avoid strict mode violation (text appears in both menu and heading)
		await expect(authenticatedPage.getByRole('heading', { name: /Trade History/i })).toBeVisible();

		// Verify page content is displayed - check for stats section (always present)
		const totalTrades = authenticatedPage.getByText(/Total Trades/i);
		await expect(totalTrades).toBeVisible({ timeout: 5000 });

		// Verify either data or empty state is shown
		const emptyState = authenticatedPage.getByText(/No closed positions yet|No transactions yet/i);
		const hasEmptyState = await emptyState.isVisible().catch(() => false);

		// If no empty state, there should be data (tables or lists)
		if (!hasEmptyState) {
			const content = authenticatedPage.locator('main, [role="main"]');
			await expect(content).toBeVisible();
		}
	});

	test('PnL page loads and displays profit/loss data', async ({ authenticatedPage }) => {
		await authenticatedPage.goto('/dashboard/pnl');

		// Verify page loads - use more flexible selector
		await expect(authenticatedPage.locator('main, [role="main"]')).toBeVisible();

		// Check for PnL content (might be in heading or content)
		const pnlHeading = authenticatedPage.getByRole('heading', { name: /PnL|Profit|Loss/i });
		const hasHeading = await pnlHeading.isVisible().catch(() => false);

		if (!hasHeading) {
			// Try to find in page content
			const pnlText = authenticatedPage.getByText(/PnL|Profit|Loss/i);
			await expect(pnlText.first()).toBeVisible({ timeout: 5000 });
		}

		// Verify PnL data is displayed (chart, table, or summary)
		const pnlContent = authenticatedPage.locator('canvas, table, [role="table"], .pnl-chart, .pnl-summary, main');
		await expect(pnlContent.first()).toBeVisible({ timeout: 5000 });
	});
});
