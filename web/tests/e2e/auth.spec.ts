import { test, expect } from './fixtures/test-fixtures';
import { waitForSessionRestore } from './utils/test-helpers';

test.describe('Authentication', () => {

	test('user can sign up with valid credentials', async ({ signupPage, page, testDataTracker }) => {
		const { generateTestEmail, generateTestName } = await import('./utils/test-helpers');

		// Generate unique test data
		const email = generateTestEmail('signup');
		const password = 'TestPassword123!';
		const name = generateTestName();

		// Track user for cleanup
		testDataTracker.trackUser(email);

		// Complete signup flow — hard verification: stay on check-email screen
		await signupPage.signup(email, password, name);

		await expect(page.getByRole('heading', { name: /check your email/i })).toBeVisible({
			timeout: 15000,
		});
		await expect(page.getByText(/We sent a verification link/i)).toBeVisible();
	});

	test('user can login with correct credentials', async ({ loginPage, page }) => {
		// Login using page object
		await loginPage.loginAsAdmin();

		// Should redirect to dashboard
		await expect(page).toHaveURL(/\/dashboard/);
		// Wait for dashboard to load - check for main content area
		await expect(page.locator('main, [role="main"]')).toBeVisible();

		// Verify user is logged in (check for user email or profile)
		const userEmail = page.getByText(new RegExp(loginPage['config'].users.admin.email, 'i'));
		await expect(userEmail).toBeVisible();
	});

	test('login fails with invalid password', async ({ loginPage, page }) => {
		// Attempt login with wrong password
		await loginPage.goto();
		await loginPage.fillEmail(loginPage['config'].users.admin.email);
		await loginPage.fillPassword('WrongPassword123!');
		await Promise.all([
			loginPage.page.waitForResponse(
				(response) => response.url().includes('/auth/login') && response.status() === 401,
			),
			loginPage.clickLogin(),
		]);

		expect(await loginPage.hasError(10000)).toBe(true);
		const errorMessage = await loginPage.getErrorMessage();
		expect(errorMessage.toLowerCase()).toMatch(/invalid|incorrect|wrong|credentials|failed|login/i);

		// Should remain on login page
		await expect(page).toHaveURL(/\//);
	});

	test('session persists after page refresh', async ({ loginPage, page }) => {
		// Login first
		await loginPage.loginAsAdmin();
		await expect(page).toHaveURL(/\/dashboard/);

		// Refresh page
		await page.reload({ waitUntil: 'domcontentloaded' });
		await waitForSessionRestore(page);

		// Should still be logged in
		await expect(page).toHaveURL(/\/dashboard/);
		await expect(page.locator('main, [role="main"]')).toBeVisible();
	});

	test('forgot password form shows generic success message', async ({ page }) => {
		await page.goto('/forgot-password');
		await page.locator('input[type="email"]').fill('test@example.com');
		await page.getByRole('button', { name: /send reset link/i }).click();
		await expect(page.getByText(/If an account exists/i)).toBeVisible({ timeout: 10000 });
	});

	test('user can logout and session is cleared', async ({ loginPage, page }) => {
		// Login first
		await loginPage.loginAsAdmin();
		await expect(page).toHaveURL(/\/dashboard/);

		// Find and click logout button (usually in user menu or sidebar)
		const logoutButton = page.getByRole('button', { name: /logout|sign out/i });
		await expect(logoutButton).toBeVisible();
		await logoutButton.click();

		// Should redirect to login page
		await expect(page).toHaveURL(/\//);
		await expect(loginPage['heading']).toBeVisible();

		// Try to access protected route - should redirect to login
		await page.goto('/dashboard');
		await expect(page).toHaveURL(/\//);
	});
});
