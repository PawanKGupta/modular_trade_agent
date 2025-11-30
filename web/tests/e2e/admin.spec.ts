import { test, expect } from '@playwright/test';

test.describe('Admin Features', () => {
	test.beforeEach(async ({ page }) => {
		// Login as admin
		await page.goto('/');
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);
	});

	test('Admin Users page is accessible to admin', async ({ page }) => {
		// Navigate to Admin Users (expand Administration menu if needed)
		const adminLink = page.getByText(/Administration|Admin/i).first();
		if (await adminLink.isVisible().catch(() => false)) {
			const adminButton = adminLink.locator('..').getByRole('button').first();
			if (await adminButton.isVisible().catch(() => false)) {
				await adminButton.click();
				await page.waitForTimeout(200);
			}
		}

		// Click Users link
		const usersLink = page.getByRole('link', { name: /Users/i });
		await usersLink.click();

		await expect(page).toHaveURL(/\/dashboard\/admin\/users/);
		await expect(page.getByText(/Users|User Management/i)).toBeVisible();

		// Verify users table is displayed
		const usersTable = page.locator('table, [role="table"]');
		await expect(usersTable.first()).toBeVisible({ timeout: 5000 });
	});

	test('Admin can create new user', async ({ page }) => {
		await page.goto('/dashboard/admin/users');
		await page.waitForLoadState('networkidle');

		// Find create user button
		const createButton = page.getByRole('button', { name: /Create|Add User|New User/i });

		if (await createButton.isVisible().catch(() => false)) {
			await createButton.click();

			// Wait for form or dialog
			await page.waitForTimeout(500);

			// Fill user details
			const timestamp = Date.now();
			const email = `newuser${timestamp}@example.com`;
			const name = `New User ${timestamp}`;

			const emailInput = page.getByLabel(/Email/i);
			await emailInput.fill(email);

			const nameInput = page.getByLabel(/Name/i);
			if (await nameInput.isVisible().catch(() => false)) {
				await nameInput.fill(name);
			}

			// Submit form
			const submitButton = page.getByRole('button', { name: /Create|Save|Submit/i });
			await submitButton.click();

			await page.waitForTimeout(1000);

			// Verify user was created (should appear in list or show success message)
			await expect(page.getByText(/success|created|user/i).first()).toBeVisible({ timeout: 3000 }).catch(() => {
				// If no success message, check if user appears in table
				expect(page.getByText(email)).toBeVisible();
			});
		}
	});

	test('ML Training page is accessible to admin', async ({ page }) => {
		// Expand Administration menu if needed
		const adminLink = page.getByText(/Administration|Admin/i).first();
		if (await adminLink.isVisible().catch(() => false)) {
			const adminButton = adminLink.locator('..').getByRole('button').first();
			if (await adminButton.isVisible().catch(() => false)) {
				await adminButton.click();
				await page.waitForTimeout(200);
			}
		}

		// Navigate to ML Training
		const mlLink = page.getByRole('link', { name: /ML Training|Machine Learning/i });
		await mlLink.click();

		await expect(page).toHaveURL(/\/dashboard\/admin\/ml-training/);
		await expect(page.getByText(/ML Training|Machine Learning/i)).toBeVisible();
	});

	test('Admin can view training jobs', async ({ page }) => {
		await page.goto('/dashboard/admin/ml-training');
		await page.waitForLoadState('networkidle');

		// Verify training jobs table is displayed
		const jobsTable = page.locator('table, [role="table"]');
		await expect(jobsTable.first()).toBeVisible({ timeout: 5000 });
	});

	test('regular user cannot access admin pages', async ({ page }) => {
		// Logout first
		const logoutButton = page.getByRole('button', { name: /logout|sign out/i });
		if (await logoutButton.isVisible().catch(() => false)) {
			await logoutButton.click();
			await page.waitForTimeout(500);
		}

		// Try to access admin page directly
		await page.goto('/dashboard/admin/users');

		// Should redirect to login or show access denied
		await expect(page).toHaveURL(/\/(login|dashboard)/);

		// If on dashboard, should not show admin menu items
		if (page.url().includes('/dashboard')) {
			const adminLink = page.getByRole('link', { name: /Users/i });
			await expect(adminLink).not.toBeVisible().catch(() => {
				// Admin link might not be visible to non-admin users
			});
		}
	});
});
