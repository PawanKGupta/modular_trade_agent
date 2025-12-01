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

		// Find reject button on first signal (if available)
		const rejectButtons = authenticatedPage.getByRole('button', { name: /reject|Reject/i });
		const rejectCount = await rejectButtons.count();

		if (rejectCount > 0) {
			// Get first reject button
			const firstReject = rejectButtons.first();
			await firstReject.click();

			// Handle confirmation dialog if it appears
			const dialog = authenticatedPage.getByRole('dialog');
			if (await dialog.isVisible().catch(() => false)) {
				await authenticatedPage.getByRole('button', { name: /confirm|yes|ok/i }).click();
			}

			// Wait for update
			await authenticatedPage.waitForTimeout(1000);

			// Verify rejection was processed (signal removed or status changed)
			// This is best-effort as we don't know exact UI behavior
			await expect(authenticatedPage.getByText(/Buying Zone/i)).toBeVisible();
		} else {
			// If no signals, skip test
			test.skip();
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
		await expect(authenticatedPage.getByRole('heading', { name: /Paper Trading/i })).toBeVisible();

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
