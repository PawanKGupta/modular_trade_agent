import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
	});

	test('user can sign up with valid credentials', async ({ page }) => {
		// Navigate to signup if there's a link, or directly
		const signupLink = page.getByRole('link', { name: /sign up|register/i });
		if (await signupLink.isVisible().catch(() => false)) {
			await signupLink.click();
		} else {
			await page.goto('/signup');
		}

		// Generate unique email
		const timestamp = Date.now();
		const email = `testuser${timestamp}@example.com`;
		const password = 'TestPassword123!';
		const name = `Test User ${timestamp}`;

		// Fill signup form
		await page.getByLabel(/email/i).fill(email);
		await page.getByLabel(/password/i).fill(password);
		if (await page.getByLabel(/name/i).isVisible().catch(() => false)) {
			await page.getByLabel(/name/i).fill(name);
		}

		// Submit form
		await page.getByRole('button', { name: /sign up|register|create account/i }).click();

		// Should redirect to dashboard
		await expect(page).toHaveURL(/\/dashboard/);
		await expect(page.getByText(/Overview|Dashboard/i)).toBeVisible();
	});

	test('user can login with correct credentials', async ({ page }) => {
		// Fill login form
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();

		// Should redirect to dashboard
		await expect(page).toHaveURL(/\/dashboard/);
		await expect(page.getByText(/Overview|Dashboard/i)).toBeVisible();

		// Verify user is logged in (check for user email or profile)
		const userEmail = page.getByText(/admin@example.com/i);
		await expect(userEmail).toBeVisible();
	});

	test('login fails with invalid password', async ({ page }) => {
		// Fill login form with wrong password
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('WrongPassword123!');
		await page.getByRole('button', { name: /login/i }).click();

		// Should show error message
		await expect(page.getByText(/invalid|incorrect|wrong|error/i)).toBeVisible();

		// Should remain on login page
		await expect(page).toHaveURL(/\//);
	});

	test('session persists after page refresh', async ({ page }) => {
		// Login first
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);

		// Refresh page
		await page.reload();

		// Should still be logged in
		await expect(page).toHaveURL(/\/dashboard/);
		await expect(page.getByText(/Overview|Dashboard/i)).toBeVisible();
	});

	test('user can logout and session is cleared', async ({ page }) => {
		// Login first
		await page.getByRole('textbox', { name: /email/i }).fill('admin@example.com');
		await page.getByLabel(/password/i).fill('Admin@123');
		await page.getByRole('button', { name: /login/i }).click();
		await expect(page).toHaveURL(/\/dashboard/);

		// Find and click logout button (usually in user menu or sidebar)
		const logoutButton = page.getByRole('button', { name: /logout|sign out/i });
		await expect(logoutButton).toBeVisible();
		await logoutButton.click();

		// Should redirect to login page
		await expect(page).toHaveURL(/\//);
		await expect(page.getByRole('button', { name: /login/i })).toBeVisible();

		// Try to access protected route - should redirect to login
		await page.goto('/dashboard');
		await expect(page).toHaveURL(/\//);
	});
});
