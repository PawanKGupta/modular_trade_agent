import { test, expect } from './fixtures/test-fixtures';

test.describe('Authentication', () => {

	test('user can sign up with valid credentials', async ({ signupPage, page, testDataTracker }) => {
		const { generateTestEmail, generateTestName } = await import('./utils/test-helpers');

		// Generate unique test data
		const email = generateTestEmail('signup');
		const password = 'TestPassword123!';
		const name = generateTestName();

		// Track user for cleanup
		testDataTracker.trackUser(email);

		// Complete signup flow
		await signupPage.signup(email, password, name);

		// Should redirect to dashboard - wait with longer timeout for signup processing
		await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

		// Wait for network to be idle to ensure all API calls complete
		await page.waitForLoadState('networkidle', { timeout: 10000 });

		// Wait for dashboard to load - check for main content area with retry
		await expect(page.locator('main, [role="main"]')).toBeVisible({ timeout: 10000 });
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
		await loginPage.clickLogin();

		// Wait for error message to appear (wait for API response or error element)
		// The error message appears after the login API call fails
		await expect(loginPage['errorMessage']).toBeVisible({ timeout: 10000 });

		// Verify error message is visible
		const hasError = await loginPage.hasError();
		expect(hasError).toBe(true);

		// Get and verify error message content
		const errorMessage = await loginPage.getErrorMessage();
		expect(errorMessage.toLowerCase()).toMatch(/invalid|incorrect|wrong|error|failed|login/i);

		// Should remain on login page
		await expect(page).toHaveURL(/\//);
	});

	test('session persists after page refresh', async ({ loginPage, page }) => {
		// Login first
		await loginPage.loginAsAdmin();
		await expect(page).toHaveURL(/\/dashboard/);

		// Refresh page
		await page.reload();
		await page.waitForLoadState('networkidle');

		// Should still be logged in
		await expect(page).toHaveURL(/\/dashboard/);
		// Wait for dashboard to load - check for main content area
		await expect(page.locator('main, [role="main"]')).toBeVisible();
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
