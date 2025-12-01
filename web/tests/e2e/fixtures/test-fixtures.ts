import { test as base, Page } from '@playwright/test';
import { LoginPage, DashboardPage, SignupPage } from '../pages';
import { TestConfig } from '../config/test-config';
import { TestDataTracker, cleanupAllTestData } from '../utils/test-cleanup';

/**
 * Extended test fixtures
 * Provides page objects and helper methods to all tests
 */

type TestFixtures = {
	loginPage: LoginPage;
	dashboardPage: DashboardPage;
	signupPage: SignupPage;
	authenticatedPage: Page; // Pre-authenticated page
	testDataTracker: TestDataTracker; // Track test data for cleanup
	page: Page; // Regular page (still available for auth tests)
};

export const test = base.extend<TestFixtures>({
	// Test Data Tracker fixture
	testDataTracker: async ({ page }, use, testInfo) => {
		const tracker = new TestDataTracker();
		await use(tracker);
		// Cleanup after test - ONLY cleans up tracked data
		try {
			await tracker.cleanup(page);
		} catch (error) {
			// Log cleanup errors but don't fail the test
			console.warn(`Cleanup warning in ${testInfo.title}:`, error);
		}
	},

	// Login Page fixture
	loginPage: async ({ page }, use) => {
		const loginPage = new LoginPage(page);
		await use(loginPage);
	},

	// Dashboard Page fixture
	dashboardPage: async ({ page }, use) => {
		const dashboardPage = new DashboardPage(page);
		await use(dashboardPage);
	},

	// Signup Page fixture
	signupPage: async ({ page }, use) => {
		const signupPage = new SignupPage(page);
		await use(signupPage);
	},

	// Authenticated Page fixture (auto-login)
	authenticatedPage: async ({ page }, use) => {
		const loginPage = new LoginPage(page);
		await loginPage.loginAsAdmin();
		// Verify we're on dashboard (authentication successful)
		await page.waitForURL(/\/dashboard/, { timeout: 30000 });
		await page.waitForLoadState('networkidle');
		// Wait a bit more to ensure session is fully established
		await page.waitForTimeout(500);
		await use(page);
	},
});

export { expect } from '@playwright/test';
