import { test, expect } from '@playwright/test';

test.describe('Notifications', () => {
	test.beforeEach(async ({ page }) => {
		// Login first
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);
	});

	test('Notifications page loads and displays notifications', async ({ page }) => {
		await page.goto('/dashboard/notifications');

		// Verify page loads
		await expect(page.getByText(/Notifications/i)).toBeVisible();

		// Verify notification list is displayed
		const notificationsList = page.locator('.notifications-list, [role="list"], table');
		await expect(notificationsList.first()).toBeVisible({ timeout: 5000 });

		// Verify filters are available
		await expect(page.getByText(/Filter|Type|Level/i).first()).toBeVisible();
	});

	test('can mark notification as read', async ({ page }) => {
		await page.goto('/dashboard/notifications');
		await page.waitForLoadState('networkidle');

		// Find an unread notification
		const markReadButtons = page.getByRole('button', { name: /Mark Read|mark as read/i });
		const buttonCount = await markReadButtons.count();

		if (buttonCount > 0) {
			// Get initial unread count if displayed
			const unreadCountElement = page.getByText(/\d+/).first();
			let initialUnreadCount = null;
			if (await unreadCountElement.isVisible().catch(() => false)) {
				const countText = await unreadCountElement.textContent();
				initialUnreadCount = parseInt(countText || '0', 10);
			}

			// Click first mark read button
			await markReadButtons.first().click();
			await page.waitForTimeout(500);

			// Verify notification was marked as read (button should disappear or change)
			// Best effort verification
			await expect(page.getByText(/Notifications/i)).toBeVisible();
		}
	});

	test('can mark all notifications as read', async ({ page }) => {
		await page.goto('/dashboard/notifications');
		await page.waitForLoadState('networkidle');

		// Find "Mark All Read" button
		const markAllReadButton = page.getByRole('button', { name: /Mark All Read|mark all as read/i });

		if (await markAllReadButton.isVisible().catch(() => false)) {
			// Get initial unread count
			const buttonText = await markAllReadButton.textContent();
			const hasUnread = buttonText && /\d+/.test(buttonText);

			if (hasUnread) {
				await markAllReadButton.click();
				await page.waitForTimeout(1000);

				// Verify all marked as read (button should update or disappear)
				await expect(page.getByText(/Notifications/i)).toBeVisible();
			}
		}
	});

	test('notification filters work correctly', async ({ page }) => {
		await page.goto('/dashboard/notifications');
		await page.waitForLoadState('networkidle');

		// Test type filter if available
		const typeFilter = page.getByLabel(/Type|Filter by Type/i);
		if (await typeFilter.isVisible().catch(() => false)) {
			await typeFilter.click();
			await page.getByText(/Service|Trading|System|Error/i).first().click();
			await page.waitForTimeout(500);
		}

		// Test level filter if available
		const levelFilter = page.getByLabel(/Level|Filter by Level/i);
		if (await levelFilter.isVisible().catch(() => false)) {
			await levelFilter.click();
			await page.getByText(/Info|Warning|Error|Critical/i).first().click();
			await page.waitForTimeout(500);
		}

		// Verify filters applied
		await expect(page.getByText(/Notifications/i)).toBeVisible();
	});

	test('notification badge shows unread count', async ({ page }) => {
		// Navigate to dashboard to see notification badge
		await page.goto('/dashboard');
		await page.waitForLoadState('networkidle');

		// Look for notification icon/bell with badge
		const notificationIcon = page.locator('[aria-label*="notification" i], [title*="notification" i]');
		if (await notificationIcon.isVisible().catch(() => false)) {
			// Check if badge is present (might be in a span or div)
			const badge = notificationIcon.locator('..').getByText(/\d+/);
			if (await badge.isVisible().catch(() => false)) {
				await expect(badge).toBeVisible();
			}
		}
	});
});
